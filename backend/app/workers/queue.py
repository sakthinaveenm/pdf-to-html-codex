import json
import logging
import os
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from sqlalchemy import select, update
import psutil
from app.config.settings import settings
from app.db.database import Session, Job, Revision, now
from app.services.converters.heavy import MarkerConverter, DoclingConverter
from app.workers.convert import write_json

log = logging.getLogger(__name__)
ACTIVE = ('INSPECTING','CONVERTING','OCR_PROCESSING','NORMALIZING','VALIDATING')

class Queue:
    def __init__(self):
        self.stop = threading.Event()
        self.thread = None
        self.active_ids = set()
        self.model_lock = threading.Lock()
    def start(self):
        with Session.begin() as db:
            for job in db.scalars(select(Job).where(Job.status.in_(ACTIVE))):
                job.status='QUEUED'; job.progress=0; job.error='Recovered interrupted conversion.'
        self.thread = threading.Thread(target=self.run,daemon=True); self.thread.start()
    def close(self):
        self.stop.set()
        if self.thread: self.thread.join(timeout=10)
    def run(self):
        futures = set()
        with ThreadPoolExecutor(max_workers=settings.workers) as pool:
            while not self.stop.wait(.4):
                futures = {f for f in futures if not f.done()}
                if len(futures) >= settings.workers: continue
                with Session.begin() as db:
                    job = db.scalar(select(Job).where(Job.status=='QUEUED').order_by(Job.created_at).limit(1))
                    if job is None: continue
                    job.status='INSPECTING'; job.updated_at=now()
                    identity = job.id
                self.active_ids.add(identity)
                futures.add(pool.submit(self.process,identity))
    def process(self, identity: str):
        started=time.monotonic(); failures=[]
        with Session() as db:
            job=db.get(Job,identity); options=json.loads(job.options); filename=job.filename
        write_json(settings.storage/'tmp'/f'{identity}.request.json',{'options':options,'filename':filename})
        requested=options['engine']
        engines=([c.name for c in (MarkerConverter(),DoclingConverter()) if c.check_availability()]+['LIGHTWEIGHT']) if requested=='AUTO' else [requested]
        try:
            for chosen in engines:
                stage=settings.storage/'tmp'/f'{identity}.stage.json'; stage.unlink(missing_ok=True)
                logpath=settings.storage/'tmp'/f'{identity}.log'
                env={**os.environ,'PDF_STORAGE':str(settings.storage),'PDF_DEVICE':settings.device,'OMP_NUM_THREADS':'4','TOKENIZERS_PARALLELISM':'false'}
                with self.model_lock if chosen != "LIGHTWEIGHT" else nullcontext():
                    with logpath.open('w') as logfile:
                        interpreter=str(__import__('pathlib').Path(settings.marker_python).resolve()) if chosen=='MARKER' and settings.marker_python else sys.executable
                        process=subprocess.Popen([interpreter,'-m','app.workers.convert',identity,chosen],stdout=logfile,stderr=logfile,env=env)
                        reason=None
                        while process.poll() is None:
                            with Session() as db: current=db.get(Job,identity)
                            if current.status=='CANCELED': reason='Canceled by user.'
                            elif self.stop.is_set(): reason='Worker stopped; retry after restart.'
                            elif time.monotonic()-started > settings.timeout_seconds: reason='Conversion timeout exceeded.'
                            else:
                                try:
                                    proc=psutil.Process(process.pid)
                                    rss=proc.memory_info().rss+sum(p.memory_info().rss for p in proc.children(recursive=True))
                                    if rss > settings.memory_mb*1024**2: reason='Conversion exceeded configured memory limit.'
                                except psutil.Error: pass
                            if reason:
                                try:
                                    parent=psutil.Process(process.pid)
                                    for child in parent.children(recursive=True): child.kill()
                                    parent.kill()
                                except psutil.Error: pass
                                process.wait(); break
                            if stage.exists():
                                try:
                                    state=json.loads(stage.read_text())
                                    with Session.begin() as db:
                                        current=db.get(Job,identity)
                                        if current.status!='CANCELED':
                                            current.status=state['status']; current.progress=state['progress']; current.engine=chosen; current.updated_at=now()
                                            if 'report' in state: current.report=json.dumps(state['report'])
                                except (ValueError,OSError): pass
                            time.sleep(.25)
                if reason: raise RuntimeError(reason)
                if process.returncode:
                    error=logpath.read_text()[-4000:]
                    failures.append(f'{chosen}: {error}')
                    log.warning('Conversion %s with %s failed: %s',identity,chosen,error)
                    continue
                output=settings.storage/'tmp'/f'{identity}-{chosen}'
                data=json.loads((output/'document.json').read_text())
                if failures:
                    data['warnings'].extend([f'Fallback after {f.split(":",1)[0]} failure; details in server logs.' for f in failures])
                    write_json(output/'document.json',data)
                    quality=json.loads((output/'quality-report.json').read_text())
                    quality['warnings'].extend(data['warnings']); write_json(output/'quality-report.json',quality)
                destination=settings.storage/'documents'/identity
                # Commit result and completion together under SQLite's writer lock; cancellation wins if already committed.
                with Session.begin() as db:
                    db.execute(update(Job).where(Job.id==identity).values(updated_at=now()))
                    current=db.get(Job,identity)
                    if current.status=='CANCELED': return
                    if destination.exists(): shutil.rmtree(destination)
                    shutil.move(str(output),destination)
                    (destination/'revisions').mkdir(exist_ok=True)
                    write_json(destination/'revisions'/'revision-001.json',data)
                    existing=db.get(Revision,(identity,1))
                    if existing: db.delete(existing); db.flush()
                    db.add(Revision(document_id=identity,number=1,ast=json.dumps(data,ensure_ascii=False)))
                    current.status='COMPLETED'; current.progress=100; current.engine=chosen; current.error=None; current.duration=time.monotonic()-started
                return
            raise RuntimeError('\n'.join(failures))
        except Exception as exc:
            log.exception('Job %s failed',identity)
            with Session.begin() as db:
                current=db.get(Job,identity)
                if current.status!='CANCELED': current.status='FAILED'; current.error=str(exc)[-5000:]; current.updated_at=now()
        finally:
            self.active_ids.discard(identity)
            for folder in (settings.storage/'tmp').glob(f'{identity}-*'):
                if folder.is_dir(): shutil.rmtree(folder,ignore_errors=True)
            for suffix in ('request.json','stage.json'):
                (settings.storage/'tmp'/f'{identity}.{suffix}').unlink(missing_ok=True)

queue = Queue()
