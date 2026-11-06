"""Remove only a terminal job's own records and files; never follow asset paths."""
import logging
from pathlib import Path
import re
import shutil
import uuid
from fastapi import HTTPException
from sqlalchemy import delete, text
from app.config.settings import settings
from app.db.database import Session, Job, Revision, Annotation, BookPage, PageRevision

log=logging.getLogger(__name__)


def purge_deleted_files() -> None:
    import json
    for folder in (settings.storage/'tmp').glob('deleted-*'):
        if not re.fullmatch(r'deleted-[a-f0-9]{32}',folder.name):continue
        try:
            if folder.is_symlink():
                folder.unlink();continue
            manifest=folder/'manifest.json'
            if manifest.is_file():
                state=json.loads(manifest.read_text())
                identity=state['jobId']
                if not re.fullmatch(r'[a-f0-9]{32}',identity):raise ValueError('Invalid staged document ID')
                with Session() as db:exists=db.get(Job,identity) is not None
                if exists:
                    for entry in state['files']:
                        relative=entry['original']
                        allowed=(relative in (f'originals/{identity}.pdf',f'documents/{identity}') or re.fullmatch(r'tmp/'+identity+r'(?:\.[A-Za-z0-9.-]+|-[A-Za-z0-9_-]+)',relative))
                        if not allowed or not str(entry['staged']).isdigit():raise ValueError('Invalid staged file path')
                        source=folder/entry['staged'];target=settings.storage/relative
                        if source.exists() or source.is_symlink():
                            if target.exists() or target.is_symlink():raise OSError('Recovery target already exists')
                            target.parent.mkdir(parents=True,exist_ok=True);source.replace(target)
            shutil.rmtree(folder)
        except (OSError,ValueError,KeyError,TypeError):
            # Preserve uncertain stages rather than deleting potentially recoverable data.
            log.exception('Could not recover/clean deleted-document staging directory %s',folder.name)


def delete_document(identity: str) -> None:
    from app.workers.queue import queue
    if not re.fullmatch(r'[a-f0-9]{32}',identity):raise HTTPException(404,'Document not found')
    staged: list[tuple[Path,Path]]=[]
    quarantine=settings.storage/'tmp'/('deleted-'+uuid.uuid4().hex)
    try:
        with Session.begin() as db:
            db.execute(text('BEGIN IMMEDIATE'))
            job=db.get(Job,identity)
            if job is None:raise HTTPException(404,'Document not found')
            if job.status not in ('COMPLETED','PARTIAL','FAILED','CANCELED') or identity in queue.active_ids:
                raise HTTPException(409,'Cancel the conversion and wait for it to stop before deleting this document.')
            candidates=[settings.storage/'originals'/f'{identity}.pdf',settings.storage/'documents'/identity]
            candidates.extend((settings.storage/'tmp').glob(f'{identity}.*'))
            candidates.extend((settings.storage/'tmp').glob(f'{identity}-*'))
            existing=[path for path in candidates if path.exists() or path.is_symlink()]
            quarantine.mkdir()
            import json
            entries=[{'original':str(path.relative_to(settings.storage)),'staged':str(index)} for index,path in enumerate(existing)]
            (quarantine/'manifest.json').write_text(json.dumps({'jobId':identity,'files':entries}),encoding='utf-8')
            for index,path in enumerate(existing):
                target=quarantine/str(index);path.replace(target);staged.append((path,target))
            db.execute(delete(PageRevision).where(PageRevision.book_id==identity))
            db.execute(delete(BookPage).where(BookPage.book_id==identity))
            db.execute(delete(Annotation).where(Annotation.document_id==identity))
            db.execute(delete(Revision).where(Revision.document_id==identity))
            db.delete(job)
    except Exception:
        for original,target in reversed(staged):
            if target.exists() or target.is_symlink():target.replace(original)
        if quarantine.exists():shutil.rmtree(quarantine,ignore_errors=True)
        raise
    # Records and public paths are gone. Retry interrupted OS cleanup at next startup.
    try:shutil.rmtree(quarantine)
    except OSError:log.exception('Deletion committed; staged file cleanup will retry at startup: %s',quarantine.name)
