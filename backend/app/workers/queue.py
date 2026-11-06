from app.helpers.runtime import interpreter_path
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from sqlalchemy import select,text
import psutil
from app.config.settings import settings
from app.db.database import Session,Job,BookPage,PageRevision,now
from app.services.converters.heavy import MarkerConverter,DoclingConverter
from app.workers.convert import write_json

log=logging.getLogger(__name__)
ACTIVE=('INSPECTING','CONVERTING','OCR_PROCESSING','NORMALIZING','VALIDATING')

class Queue:
    def __init__(self):
        self.stop=threading.Event();self.thread=None;self.active_ids=set();self.model_lock=threading.Lock()
    def start(self):
        self.stop.clear()
        with Session.begin() as db:
            db.execute(text('BEGIN IMMEDIATE'))
            for job in db.scalars(select(Job).where(Job.status.in_(ACTIVE))):job.status='QUEUED';job.error='Recovered interrupted book conversion.'
            for page in db.scalars(select(BookPage).where(BookPage.status.in_(ACTIVE))):page.status='QUEUED';page.progress=0
        self.thread=threading.Thread(target=self.run,daemon=True);self.thread.start()
    def close(self):
        self.stop.set()
        if self.thread:self.thread.join(timeout=12)
    def run(self):
        futures=set()
        with ThreadPoolExecutor(max_workers=settings.workers) as pool:
            while not self.stop.wait(.3):
                futures={future for future in futures if not future.done()}
                if len(futures)>=settings.workers:continue
                with Session.begin() as db:
                    db.execute(text('BEGIN IMMEDIATE'))
                    job=db.scalar(select(Job).where(Job.status=='QUEUED').order_by(Job.created_at).limit(1))
                    if job is None:continue
                    job.status='INSPECTING';job.updated_at=now();identity=job.id;self.active_ids.add(identity)
                futures.add(pool.submit(self.process,identity))
    def publish(self,identity,engine,root):
        from app.services.documents.pages import page_folder,page_document,page_json
        from app.schemas.document import Document
        with Session.begin() as db:
            db.execute(text('BEGIN IMMEDIATE'))
            job=db.get(Job,identity)
            if job is None or job.status=='CANCELED':return
            records=list(db.scalars(select(BookPage).where(BookPage.book_id==identity)))
            for record in records:
                folder=root/'pages'/f'{record.number:04d}'
                if (folder/'_complete.json').is_file():
                    data=Document.model_validate_json((folder/'document.json').read_text())
                    record.generated_ast=data.model_dump_json()
                    if not record.edited or record.overwrite_edits:
                        destination=page_folder(identity,record.number)
                        # Edited page history may still refer to prior assets; retain them.
                        if destination.exists():shutil.copytree(folder,destination,dirs_exist_ok=True);shutil.rmtree(folder)
                        else:destination.parent.mkdir(parents=True,exist_ok=True);shutil.move(str(folder),destination)
                        (destination/'_complete.json').unlink(missing_ok=True)
                        record.revision=record.revision+1 if record.ast else 1;data.revision=record.revision;record.ast=data.model_dump_json();record.edited=False;record.overwrite_edits=False
                        db.add(PageRevision(book_id=identity,page=record.number,number=record.revision,ast=record.ast))
                        record.quality=(destination/'quality-report.json').read_text();record.engine=engine;record.duration=data.metadata.get('durationSeconds')
                        from app.services.documents.pages import materialize
                        materialize(data,destination,json.loads(record.quality))
                    record.status='COMPLETED';record.progress=100;record.error=None;record.updated_at=now()
                elif (folder/'_error.json').is_file() and record.status not in ('COMPLETED',):
                    record.status='FAILED';record.progress=0;record.error=json.loads((folder/'_error.json').read_text())['message'];record.engine=engine
            complete=sum(record.status=='COMPLETED' for record in records)
            job.progress=int(complete/max(1,len(records))*100);job.engine=engine;job.updated_at=now()
    def child(self,identity,engine,request,*,inspection=False):
        write_json(settings.storage/'tmp'/f'{identity}.request.json',request)
        stage=settings.storage/'tmp'/f'{identity}.stage.json';stage.unlink(missing_ok=True)
        root=settings.storage/'tmp'/f'{identity}-{engine}'
        env={**os.environ,'PDF_STORAGE':str(settings.storage),'PDF_DEVICE':settings.device,'OMP_NUM_THREADS':'4','TOKENIZERS_PARALLELISM':'false'}
        interpreter=interpreter_path(settings.marker_python) if engine=='MARKER' and settings.marker_python else sys.executable
        module='app.workers.convert' if inspection else 'app.workers.book_convert'
        with (self.model_lock if engine in ('MARKER','DOCLING') else nullcontext()):
            with (settings.storage/'tmp'/f'{identity}.log').open('a') as output:
                process=subprocess.Popen([interpreter,'-m',module,identity,engine],stdout=output,stderr=output,env=env)
                started=time.monotonic();current_page=None
                while process.poll() is None:
                    reason=None
                    with Session() as db:job=db.get(Job,identity)
                    if job is None or job.status=='CANCELED':reason='Canceled by user.'
                    elif self.stop.is_set():reason='Worker stopped; conversion will recover after restart.'
                    elif time.monotonic()-started>settings.timeout_seconds:reason='Page conversion timeout exceeded.'
                    try:
                        parent=psutil.Process(process.pid);rss=parent.memory_info().rss+sum(child.memory_info().rss for child in parent.children(recursive=True))
                        if rss>settings.memory_mb*1024**2:reason='Configured memory limit exceeded.'
                    except psutil.Error:pass
                    if reason:
                        try:
                            parent=psutil.Process(process.pid)
                            for child in parent.children(recursive=True):child.kill()
                            parent.kill()
                        except psutil.Error:pass
                        process.wait()
                        if not inspection:self.publish(identity,engine,root)
                        return reason
                    if stage.is_file():
                        try:
                            state=json.loads(stage.read_text())
                            if state.get('page')!=current_page:current_page=state.get('page');started=time.monotonic()
                            with Session.begin() as db:
                                db.execute(text('BEGIN IMMEDIATE'))
                                job=db.get(Job,identity)
                                if job and job.status!='CANCELED':
                                    job.status=state['status'];job.updated_at=now()
                                    record=db.get(BookPage,(identity,state.get('page'))) if state.get('page') else None
                                    if record and record.status not in ('COMPLETED','FAILED'):record.status=state['status'];record.progress=state['progress']
                        except (ValueError,OSError):pass
                    if not inspection:self.publish(identity,engine,root)
                    time.sleep(.2)
                if not inspection:self.publish(identity,engine,root)
                if process.returncode:return (settings.storage/'tmp'/f'{identity}.log').read_text()[-3000:]
        return None
    def process(self,identity):
        started=time.monotonic()
        try:
            with Session() as db:
                job=db.get(Job,identity);options=json.loads(job.options);filename=job.filename;checksum=job.checksum;inspection=json.loads(job.report) if job.report else None
            request={'options':options,'filename':filename,'checksum':checksum}
            if inspection is None:
                error=self.child(identity,'INSPECT',request,inspection=True)
                if error:raise RuntimeError(error)
                inspection=json.loads((settings.storage/'tmp'/f'{identity}-INSPECT'/'inspection.json').read_text())
            with Session.begin() as db:
                db.execute(text('BEGIN IMMEDIATE'))
                job=db.get(Job,identity)
                if job.status=='CANCELED':return
                job.report=json.dumps(inspection)
                for info in inspection['pages']:
                    if db.get(BookPage,(identity,info['page'])) is None:db.add(BookPage(book_id=identity,number=info['page']))
            heavy=[converter.name for converter in (MarkerConverter(),DoclingConverter()) if converter.check_availability()]
            legacy=any(page.get('legacyFonts') for page in inspection['pages'])
            engines=([name for name in heavy if name=='DOCLING']+['LIGHTWEIGHT']+[name for name in heavy if name=='MARKER']) if legacy else heavy+['LIGHTWEIGHT']
            if options['engine']!='AUTO':engines=[options['engine']]
            for engine in engines:
                with Session.begin() as db:
                    db.execute(text('BEGIN IMMEDIATE'))
                    job=db.get(Job,identity)
                    if job.status=='CANCELED':return
                    pending=list(db.scalars(select(BookPage).where(BookPage.book_id==identity,BookPage.status!='COMPLETED')))
                    numbers=[page.number for page in pending]
                    for page in pending:page.status='QUEUED';page.error=None
                if not numbers:break
                request.update({'inspection':inspection,'pages':numbers})
                error=self.child(identity,engine,request)
                if self.stop.is_set():
                    with Session.begin() as db:
                        db.execute(text('BEGIN IMMEDIATE'))
                        db.get(Job,identity).status='QUEUED'
                        for page in db.scalars(select(BookPage).where(BookPage.book_id==identity,BookPage.status!='COMPLETED')):page.status='QUEUED'
                    return
                if error:
                    log.warning('Book %s engine %s: %s',identity,engine,error)
                    with Session.begin() as db:
                        db.execute(text('BEGIN IMMEDIATE'))
                        job=db.get(Job,identity)
                        if job.status=='CANCELED':return
                        for page in db.scalars(select(BookPage).where(BookPage.book_id==identity,BookPage.status!='COMPLETED')):page.status='FAILED';page.error=error
            with Session.begin() as db:
                db.execute(text('BEGIN IMMEDIATE'))
                job=db.get(Job,identity)
                if job.status=='CANCELED':return
                records=list(db.scalars(select(BookPage).where(BookPage.book_id==identity)))
                if any(page.status=='QUEUED' for page in records):
                    job.status='QUEUED';return
                successes=sum(page.status=='COMPLETED' for page in records);failures=len(records)-successes
                from app.services.documents.pages import aggregate_book
                if successes:aggregate_book(db,identity)
                job.status='PARTIAL' if successes and failures else 'COMPLETED' if successes else 'FAILED';job.progress=100;job.duration=time.monotonic()-started;job.updated_at=now();job.error=f'{failures} page(s) failed; retry them individually.' if failures else None
        except Exception as exc:
            log.exception('Book %s failed',identity)
            with Session.begin() as db:
                db.execute(text('BEGIN IMMEDIATE'))
                job=db.get(Job,identity)
                if job and job.status!='CANCELED':job.status='FAILED';job.error=str(exc)[-5000:]
        finally:
            self.active_ids.discard(identity)
            for folder in (settings.storage/'tmp').glob(f'{identity}-*'):
                if folder.is_dir():shutil.rmtree(folder,ignore_errors=True)
            for suffix in ('request.json','stage.json'):(settings.storage/'tmp'/f'{identity}.{suffix}').unlink(missing_ok=True)

queue=Queue()
