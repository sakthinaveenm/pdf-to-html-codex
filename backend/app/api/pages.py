import io
import json
from pathlib import Path
import zipfile
from typing import Literal
from fastapi import APIRouter,HTTPException,Query
from fastapi.responses import HTMLResponse,Response,FileResponse
from pydantic import BaseModel,Field
from sqlalchemy import select,text
from app.config.settings import settings
from app.db.database import Session,Job,BookPage,PageRevision,now
from app.schemas.document import Document,RevisionInput
from app.services.documents.pages import ensure_pages,get_page,page_document,page_json,page_folder,save_page_revision,aggregate_book
from app.services.export.pages import editor_snippet,page_zip,write_page
from app.services.export.standalone import standalone_html
from app.services.html.service import HTMLNormalizationService,safe_asset
from app.services.html.embedded import import_embedded_images
from app.services.html.typography import FONT_DIR

router=APIRouter(prefix='/api/v1')

class ReconvertInput(BaseModel):
    overwriteEdits: bool=False

@router.get('/books/{book}/pages')
@router.get('/documents/{book}/pages')
def list_pages(book: str):
    with Session.begin() as db:
        db.execute(text('BEGIN IMMEDIATE'));ensure_pages(db,book)
        records=list(db.scalars(select(BookPage).where(BookPage.book_id==book).order_by(BookPage.number)))
        job=db.get(Job,book)
        return {'bookId':book,'filename':job.filename,'status':job.status,'total':len(records),'completed':sum(page.status=='COMPLETED' for page in records),'failed':sum(page.status=='FAILED' for page in records),'items':[page_json(page) for page in records]}

@router.get('/books/{book}/pages/{number}')
def page(book: str,number: int):
    with Session.begin() as db:return page_json(get_page(db,book,number),True)

@router.get('/books/{book}/pages/{number}/html')
def page_html(book: str,number: int,format: Literal['snippet','standalone']='snippet',image_mode: Literal['embedded','url']='embedded',asset_base_url: str | None=None):
    with Session.begin() as db:doc=page_document(get_page(db,book,number))
    folder=page_folder(book,number)
    try:html=editor_snippet(doc,folder,image_mode=image_mode,asset_base_url=asset_base_url) if format=='snippet' else standalone_html(doc,folder)
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc
    return HTMLResponse(html,headers={'Content-Security-Policy':"default-src 'none'; img-src data: https: http:; font-src data:; style-src 'unsafe-inline'"})

@router.get('/books/{book}/pages/{number}/assets/{asset}')
def page_asset(book: str,number: int,asset: str):
    with Session.begin() as db:doc=page_document(get_page(db,book,number))
    if not safe_asset('assets/'+asset) or not any(item['assetId']==asset for item in doc.assets):raise HTTPException(404,'Asset not found')
    path=page_folder(book,number)/'assets'/asset
    if not path.is_file():raise HTTPException(404,'Asset is missing')
    return FileResponse(path,headers={'X-Content-Type-Options':'nosniff'})

@router.put('/books/{book}/pages/{number}/revisions')
def save_page(book: str,number: int,request: RevisionInput):
    with Session.begin() as db:
        db.execute(text('BEGIN IMMEDIATE'));record=get_page(db,book,number);doc=page_document(record)
        if record.status not in ('COMPLETED','FAILED','CANCELED'):raise HTTPException(409,'Wait for this page to stop converting before saving corrections.')
        if request.baseRevision!=record.revision:raise HTTPException(409,'Page revision changed; refresh before saving.')
        try:source=import_embedded_images(request.html,page_folder(book,number),doc.assets)
        except ValueError as exc:raise HTTPException(422,str(exc)) from exc
        previous={block.blockId:block for block in doc.blocks}
        blocks=HTMLNormalizationService().blocks(source,book,number,'editor',doc.language)
        for block in blocks:
            block.sourcePage=number
            if block.blockId in previous:block.provenance=previous[block.blockId].provenance
        retained={block.blockId for block in blocks}
        for old in doc.blocks:
            if old.blockType in ('equation','caption') and old.blockId not in retained:old.readingOrder=len(blocks);blocks.append(old);doc.warnings.append(f'Editor cannot fully represent {old.blockType}; preserved at the end for review.')
        doc.blocks=blocks;save_page_revision(db,record,doc,edited=True)
        aggregate_book(db,book)
        return page_json(record,True)

@router.post('/books/{book}/pages/{number}/reset')
def reset_page(book: str,number: int):
    with Session.begin() as db:
        db.execute(text('BEGIN IMMEDIATE'));record=get_page(db,book,number)
        if not record.generated_ast:raise HTTPException(409,'No converted baseline is available for this page.')
        if record.status not in ('COMPLETED','FAILED','CANCELED'):raise HTTPException(409,'This page is converting.')
        doc=Document.model_validate_json(record.generated_ast);save_page_revision(db,record,doc,edited=False);aggregate_book(db,book)
        return page_json(record,True)

@router.post('/books/{book}/pages/{number}/retry')
@router.post('/books/{book}/pages/{number}/reconvert')
def retry_page(book: str,number: int,request: ReconvertInput | None=None):
    from app.workers.queue import queue
    with Session.begin() as db:
        db.execute(text('BEGIN IMMEDIATE'));record=get_page(db,book,number)
        if record.edited and not (request and request.overwriteEdits):raise HTTPException(409,'This page has manual corrections. Explicit overwriteEdits=true is required to replace them.')
        if record.status not in ('COMPLETED','FAILED','CANCELED'):raise HTTPException(409,'This page is already queued or converting.')
        record.status='QUEUED';record.progress=0;record.error=None;record.overwrite_edits=bool(request and request.overwriteEdits)
        job=db.get(Job,book)
        if book not in queue.active_ids:job.status='QUEUED';job.error=None;job.updated_at=now()
        return page_json(record)

@router.get('/books/{book}/pages/{number}/export')
def export_page(book: str,number: int,format: Literal['html','snippet','zip']='html',image_mode: Literal['embedded','url']='embedded',asset_base_url: str | None=None):
    with Session.begin() as db:doc=page_document(get_page(db,book,number))
    folder=page_folder(book,number)
    try:
        content=page_zip(doc,folder,image_mode,asset_base_url) if format=='zip' else editor_snippet(doc,folder,image_mode=image_mode,asset_base_url=asset_base_url) if format=='snippet' else standalone_html(doc,folder)
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc
    return Response(content,media_type='application/zip' if format=='zip' else 'text/html',headers={'Content-Disposition':f'attachment; filename="page-{number:04d}.{ "zip" if format=="zip" else "html"}"'})

@router.get('/books/{book}/export')
def export_book(book: str,pages: str | None=None,image_mode: Literal['embedded','url']='embedded',asset_base_url: str | None=None):
    with Session.begin() as db:
        ensure_pages(db,book);job=db.get(Job,book)
        records=list(db.scalars(select(BookPage).where(BookPage.book_id==book).order_by(BookPage.number)))
        selected=None
        if pages:
            try:selected={int(value) for value in pages.split(',')}
            except ValueError as exc:raise HTTPException(422,'Use comma-separated page numbers.') from exc
            if not selected or not selected.issubset({page.number for page in records}):raise HTTPException(422,'Selected page numbers are outside this book.')
        included=[record for record in records if selected is None or record.number in selected]
        if not any(record.ast for record in included):raise HTTPException(409,'No selected pages are ready to export.')
        output=io.BytesIO()
        try:
            with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
                manifest={'schemaVersion':1,'bookId':book,'sourceFileName':job.filename,'sourceChecksum':job.checksum,'pageCount':len(records),'exportedPages':[record.number for record in included if record.ast],'imageMode':image_mode,'assetBaseURL':asset_base_url,'pages':[page_json(record) for record in included]}
                archive.writestr('book.json',json.dumps(manifest,ensure_ascii=False,indent=2))
                archive.writestr('quality-report.json',json.dumps({'pages':[{'page':record.number,'status':record.status,'quality':json.loads(record.quality) if record.quality else None} for record in included]},ensure_ascii=False,indent=2))
                for record in included:
                    prefix=f'pages/{record.number:04d}/'
                    if record.ast:write_page(archive,prefix,page_document(record),page_folder(book,record.number),image_mode,asset_base_url)
                    else:archive.writestr(prefix+'metadata.json',json.dumps(page_json(record),ensure_ascii=False,indent=2))
                for file in FONT_DIR.glob('*.woff2'):archive.write(file,'shared-assets/fonts/'+file.name)
                for file in FONT_DIR.glob('*-OFL.txt'):archive.write(file,'shared-assets/fonts/'+file.name)
        except ValueError as exc:raise HTTPException(422,str(exc)) from exc
    return Response(output.getvalue(),media_type='application/zip',headers={'Content-Disposition':'attachment; filename="book-pages.zip"'})
