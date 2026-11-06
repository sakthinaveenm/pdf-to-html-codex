import hashlib
import json
import re
import shutil
import uuid
from pathlib import Path
from typing import Annotated
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, Response
from sqlalchemy import select, func, update
from app.config.settings import settings
from app.db.database import Session, Job, Revision, Annotation, BookPage, now
from app.schemas.document import Options, Document, RevisionInput, Highlight, HighlightPatch
from app.services.html.service import HTMLGenerationService, HTMLNormalizationService, safe_asset, document_text
from app.services.annotations.service import resolve
from app.services.export.service import archive
from app.services.export.standalone import standalone_html
from app.services.converters.heavy import MarkerConverter, DoclingConverter
from app.services.ocr.service import OCRService
from app.workers.convert import write_json

router=APIRouter(prefix='/api/v1')

def get_job(db, identity: str) -> Job:
    value=db.get(Job,identity)
    if value is None: raise HTTPException(404,'Job not found')
    return value

def get_doc(db, identity: str) -> Document:
    row=db.scalar(select(Revision).where(Revision.document_id==identity).order_by(Revision.number.desc()).limit(1))
    if row is None: raise HTTPException(404,'Converted document not found')
    return Document.model_validate_json(row.ast)

def job_json(job: Job) -> dict:
    return {'id':job.id,'filename':job.filename,'status':job.status,'progress':job.progress,'engine':job.engine,
            'options':json.loads(job.options),'error':job.error,'inspection':json.loads(job.report) if job.report else None,
            'createdAt':job.created_at,'updatedAt':job.updated_at,'durationSeconds':job.duration}

@router.get('/health')
def health(): return {'status':'ok','version':'0.1.0'}

@router.get('/capabilities')
def capabilities():
    import subprocess
    gpu=False; details=None
    try:
        result=subprocess.run(['nvidia-smi','--query-gpu=name,memory.total','--format=csv,noheader'],capture_output=True,text=True,timeout=3,check=True)
        gpu=True; details=result.stdout.strip()
    except (OSError,subprocess.SubprocessError): pass
    return {'features':{'deleteDocuments':True},'converters':[MarkerConverter().get_capabilities(),DoclingConverter().get_capabilities(),{'name':'LIGHTWEIGHT','installed':True}],
            'ocr':{'engine':'tesseract','languages':OCRService.languages()},'gpu':{'available':gpu,'details':details},
            'settings':{'workers':settings.workers,'device':settings.device,'memoryMB':settings.memory_mb,'maxUploadMB':settings.max_upload_mb,'maxPages':settings.max_pages,'timeoutSeconds':settings.timeout_seconds}}

@router.post('/jobs',status_code=201)
async def upload(files: Annotated[list[UploadFile],File()], options: Annotated[str,Form()]='{}'):
    if not 1<=len(files)<=20: raise HTTPException(422,'Upload 1 to 20 PDFs per batch.')
    try: parsed=Options.model_validate_json(options)
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    results=[]
    for file in files:
        identity=uuid.uuid4().hex; target=settings.storage/'originals'/f'{identity}.pdf'
        name=Path((file.filename or 'document.pdf').replace('\\','/')).name[:240]
        try:
            if not name.lower().endswith('.pdf') or file.content_type not in ('application/pdf','application/octet-stream'):
                raise ValueError('Only application/pdf files with a .pdf extension are accepted.')
            size=0; checksum=hashlib.sha256()
            with target.open('wb') as output:
                while chunk:=await file.read(1024*1024):
                    size+=len(chunk)
                    if size>settings.max_upload_mb*1024**2: raise ValueError('PDF exceeds upload size limit.')
                    if size==len(chunk) and not chunk.startswith(b'%PDF-'): raise ValueError('Invalid PDF signature.')
                    output.write(chunk); checksum.update(chunk)
            if not size: raise ValueError('Empty file.')
            with Session.begin() as db:
                job=Job(id=identity,filename=name,checksum=checksum.hexdigest(),options=parsed.model_dump_json())
                db.add(job); db.flush(); results.append({'job':job_json(job)})
        except (ValueError,OSError) as exc:
            target.unlink(missing_ok=True); results.append({'filename':name,'error':str(exc)})
        finally: await file.close()
    return {'results':results}

@router.get('/jobs')
def jobs(offset: int=Query(0,ge=0),limit: int=Query(50,ge=1,le=200)):
    with Session() as db:
        counts=dict(db.execute(select(Job.status,func.count()).group_by(Job.status)).all())
        return {'items':[job_json(j) for j in db.scalars(select(Job).order_by(Job.created_at.desc()).offset(offset).limit(limit))],
                'total':sum(counts.values()),'counts':counts}

@router.get('/jobs/{identity}')
def job(identity: str):
    with Session() as db: return job_json(get_job(db,identity))

@router.delete('/jobs/{identity}',status_code=204)
@router.delete('/documents/{identity}',status_code=204)
def remove_document(identity: str):
    from app.services.documents.deletion import delete_document
    try:delete_document(identity)
    except OSError as exc:raise HTTPException(500,'Could not delete document files. Close any programs using them and try again.') from exc

@router.post('/jobs/{identity}/cancel')
def cancel(identity: str):
    with Session.begin() as db:
        # Acquire writer lock before reading so a completion cannot race cancellation.
        db.execute(update(Job).where(Job.id==identity).values(updated_at=now()))
        value=get_job(db,identity)
        if value.status in ('COMPLETED','PARTIAL','FAILED','CANCELED'): raise HTTPException(409,'Job is already finished.')
        value.status='CANCELED'; value.error='Canceled by user.'
        db.execute(update(BookPage).where(BookPage.book_id==identity,BookPage.status!='COMPLETED').values(status='CANCELED'))
        return job_json(value)

@router.post('/jobs/{identity}/retry')
def retry(identity: str):
    from app.workers.queue import queue
    if identity in queue.active_ids: raise HTTPException(409,'Worker is still stopping this job; retry in a moment.')
    with Session.begin() as db:
        value=get_job(db,identity)
        if value.status not in ('FAILED','PARTIAL','CANCELED'): raise HTTPException(409,'Only partial, failed or canceled jobs may be retried.')
        db.execute(update(BookPage).where(BookPage.book_id==identity,BookPage.status!='COMPLETED').values(status='QUEUED',progress=0))
        value.status='QUEUED'; value.progress=0; value.error=None; value.updated_at=now()
        return job_json(value)

@router.get('/jobs/{identity}/original')
def original(identity: str):
    with Session() as db: get_job(db,identity)
    return FileResponse(settings.storage/'originals'/f'{identity}.pdf',media_type='application/pdf',headers={'Content-Security-Policy':"sandbox"})

@router.get('/documents/{identity}')
@router.get('/documents/{identity}/ast')
def document(identity: str):
    with Session() as db: return get_doc(db,identity)

@router.get('/documents/{identity}/html')
def document_html(identity: str, fragment: bool=False, standalone: bool=False):
    with Session() as db: doc=get_doc(db,identity)
    if standalone:
        try:
            result=standalone_html(doc,settings.storage/'documents'/identity,fragment=fragment)
        except ValueError as exc:
            raise HTTPException(409,str(exc)) from exc
        return HTMLResponse(result,headers={'Content-Security-Policy':"default-src 'none'; style-src 'unsafe-inline'; font-src data:; img-src data:"})
    generator=HTMLGenerationService()
    return HTMLResponse(generator.article(doc) if fragment else generator.generate(doc),headers={'Content-Security-Policy':"default-src 'none'; style-src 'unsafe-inline'; font-src data:; img-src 'self'"})

@router.get('/documents/{identity}/quality')
def quality(identity: str):
    with Session() as db: get_doc(db,identity)
    return json.loads((settings.storage/'documents'/identity/'quality-report.json').read_text())

@router.get('/documents/{identity}/assets/{asset_id}')
def asset(identity: str, asset_id: str):
    with Session() as db:
        doc=get_doc(db,identity)
    if not safe_asset('assets/'+asset_id) or not any(a['assetId']==asset_id for a in doc.assets): raise HTTPException(404,'Asset not found')
    path=settings.storage/'documents'/identity/'assets'/asset_id
    if not path.is_file(): raise HTTPException(404,'Asset file missing')
    return FileResponse(path,headers={'X-Content-Type-Options':'nosniff'})

@router.put('/documents/{identity}/revisions')
def revision(identity: str, request: RevisionInput):
    with Session.begin() as db:
        db.execute(update(Job).where(Job.id==identity).values(updated_at=now()))
        doc=get_doc(db,identity)
        if doc.revision!=request.baseRevision: raise HTTPException(409,'Revision conflict; reload before saving.')
        previous={b.blockId:b for b in doc.blocks}
        from app.services.html.embedded import import_embedded_images
        try:
            editor_html=import_embedded_images(request.html,settings.storage/'documents'/identity,doc.assets)
        except ValueError as exc: raise HTTPException(422,str(exc)) from exc
        blocks=HTMLNormalizationService().blocks(editor_html,identity,None,'editor',doc.language)
        for block in blocks:
            if block.blockId in previous:
                old=previous[block.blockId]; block.sourcePage=old.sourcePage; block.provenance=old.provenance
        retained={b.blockId for b in blocks}
        for old in doc.blocks:
            if old.blockType in ('equation','caption') and old.blockId not in retained:
                old.readingOrder=len(blocks); blocks.append(old)
                doc.warnings.append(f'Editor could not represent {old.blockType} {old.blockId}; preserved in canonical content at the end for review.')
        doc.blocks=blocks; doc.revision+=1
        from app.services.documents.pages import sync_combined_revision
        sync_combined_revision(db,doc)
        doc.warnings.append('Edited revision: highlights are re-anchored conservatively. New blocks may have no source page.')
        db.add(Revision(document_id=identity,number=doc.revision,ast=doc.model_dump_json()))
        for row in db.scalars(select(Annotation).where(Annotation.document_id==identity)):
            row.data=resolve(Highlight.model_validate_json(row.data),doc).model_dump_json()
        # SQLite revisions are authoritative; exports render the latest revision.
        folder=settings.storage/'documents'/identity
        write_json(folder/'revisions'/f'revision-{doc.revision:03}.json',doc.model_dump())
        write_json(folder/'document.json',doc.model_dump())
        (folder/'document.html').write_text(HTMLGenerationService().generate(doc),encoding='utf-8')
        from app.services.validation.service import DocumentQualityService
        write_json(folder/'quality-report.json',DocumentQualityService().validate(doc,folder))
    return doc

@router.post('/documents/{identity}/highlights',status_code=201)
def add_highlight(identity: str, value: Highlight):
    with Session.begin() as db:
        doc=get_doc(db,identity)
        if value.documentId!=identity or value.revision!=doc.revision: raise HTTPException(409,'Annotation document or revision mismatch.')
        if value.position.end<=value.position.start or document_text(doc)[value.position.start:value.position.end]!=value.quote.exact:
            raise HTTPException(422,'Quote and Unicode codepoint position do not match document text.')
        if not set(value.blockIds).issubset({b.blockId for b in doc.blocks}): raise HTTPException(422,'Unknown block IDs.')
        if db.get(Annotation,(identity,value.id)): raise HTTPException(409,'Highlight ID already exists.')
        db.add(Annotation(document_id=identity,id=value.id,data=value.model_dump_json()))
    return value

@router.get('/documents/{identity}/highlights')
def highlights(identity: str):
    with Session() as db:
        get_doc(db,identity)
        return [json.loads(a.data) for a in db.scalars(select(Annotation).where(Annotation.document_id==identity))]

@router.patch('/documents/{identity}/highlights/{highlight_id}')
def patch_highlight(identity: str, highlight_id: str, request: HighlightPatch):
    with Session.begin() as db:
        row=db.get(Annotation,(identity,highlight_id))
        if row is None: raise HTTPException(404,'Highlight not found')
        data=json.loads(row.data); data['color']=request.color; row.data=json.dumps(data)
        return data

@router.delete('/documents/{identity}/highlights/{highlight_id}',status_code=204)
def delete_highlight(identity: str, highlight_id: str):
    with Session.begin() as db:
        row=db.get(Annotation,(identity,highlight_id))
        if row is None: raise HTTPException(404,'Highlight not found')
        db.delete(row)

@router.get('/documents/{identity}/export')
def export(identity: str, format: str=Query('zip',pattern='^(zip|html|json|assets|quality)$')):
    with Session() as db:
        doc=get_doc(db,identity)
        annotations=[json.loads(a.data) for a in db.scalars(select(Annotation).where(Annotation.document_id==identity))]
    folder=settings.storage/'documents'/identity
    if format in ('zip','assets'):
        return Response(archive(doc,folder,annotations,format=='assets'),media_type='application/zip',headers={'Content-Disposition':f'attachment; filename="{identity}-{format}.zip"'})
    if format=='html':
        try: payload=standalone_html(doc,folder)
        except ValueError as exc: raise HTTPException(409,str(exc)) from exc
        mime='text/html'
    elif format=='json': payload=doc.model_dump_json(indent=2); mime='application/json'
    else: payload=(folder/'quality-report.json').read_text(); mime='application/json'
    from urllib.parse import quote
    filename=Path(doc.sourceFileName).stem+'.html' if format=='html' else identity+'.json'
    return Response(payload,media_type=mime,headers={'Content-Disposition':"attachment; filename*=UTF-8''"+quote(filename,safe='')})
