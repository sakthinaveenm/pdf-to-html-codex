import copy
import json
from pathlib import Path
import shutil
from bs4 import BeautifulSoup
from fastapi import HTTPException
from sqlalchemy import select
from app.config.settings import settings
from app.db.database import Session,Job,Revision,BookPage,PageRevision,now
from app.schemas.document import Document
from app.services.html.service import HTMLGenerationService
from app.services.html.source_typography import apply_source_typography
from app.services.validation.service import DocumentQualityService
from app.workers.convert import write_json


def page_folder(book: str,number: int) -> Path:
    return settings.storage/'documents'/book/'pages'/f'{number:04d}'


def ensure_pages(db,book: str) -> None:
    job=db.get(Job,book)
    if job is None:raise HTTPException(404,'Book not found')
    if db.scalar(select(BookPage).where(BookPage.book_id==book).limit(1)):return
    row=db.scalar(select(Revision).where(Revision.document_id==book).order_by(Revision.number.desc()).limit(1))
    if row is None:return
    whole=Document.model_validate_json(row.ast)
    root=settings.storage/'documents'/book
    for info in whole.pages:
        number=info['page'];doc=whole.model_copy(deep=True);doc.pages=[dict(info)];doc.blocks=[block.model_copy(deep=True) for block in whole.blocks if block.sourcePage==number]
        doc.revision=1;doc.metadata.update({'pageNumber':number,'pageId':f'{book}:page:{number}'})
        if number==1:
            for block in whole.blocks:
                if block.sourcePage is None:doc.blocks.append(block.model_copy(deep=True))
            if any(block.sourcePage is None for block in doc.blocks):doc.warnings.append('Some imported blocks lack original page mappings; assigned to page 1 for review.')
        refs={str(img.get('src','')) for block in doc.blocks for img in BeautifulSoup(block.content,'html.parser').find_all('img')}
        doc.assets=[dict(asset) for asset in whole.assets if asset['path'] in refs]
        folder=page_folder(book,number);(folder/'assets').mkdir(parents=True,exist_ok=True)
        for asset in doc.assets:
            if (root/asset['path']).is_file():shutil.copyfile(root/asset['path'],folder/asset['path'])
        try:doc=apply_source_typography(doc,settings.storage/'originals'/f'{book}.pdf',folder,number,recover_cover=row.number==1)
        except Exception as exc:doc.warnings.append(f'Source typography requires review: {type(exc).__name__}')
        for block in doc.blocks:block.sourcePage=number
        quality=DocumentQualityService().validate(doc,folder)
        status='COMPLETED' if doc.blocks or info.get('characters',0)==0 else 'FAILED'
        baseline=doc.model_copy(deep=True)
        if row.number>1:
            original=db.get(Revision,(book,1))
            if original:
                original_doc=Document.model_validate_json(original.ast)
                baseline.blocks=[block.model_copy(deep=True) for block in original_doc.blocks if block.sourcePage==number or (number==1 and block.sourcePage is None)]
                for block in baseline.blocks:block.sourcePage=number
                refs={str(img.get('src','')) for block in baseline.blocks for img in BeautifulSoup(block.content,'html.parser').find_all('img')}
                baseline.assets=[dict(asset) for asset in original_doc.assets if asset['path'] in refs]
                for asset in baseline.assets:
                    if (root/asset['path']).is_file() and not (folder/asset['path']).exists():shutil.copyfile(root/asset['path'],folder/asset['path'])
        record=BookPage(book_id=book,number=number,status=status,progress=100,engine=job.engine,ast=doc.model_dump_json(),generated_ast=baseline.model_dump_json(),quality=json.dumps(quality),revision=1,edited=row.number>1)
        db.add(record);db.add(PageRevision(book_id=book,page=number,number=1,ast=doc.model_dump_json()))
        materialize(doc,folder,quality)
    db.flush()


def get_page(db,book: str,number: int) -> BookPage:
    ensure_pages(db,book)
    page=db.get(BookPage,(book,number))
    if page is None:raise HTTPException(404,'Page not found')
    return page


def page_document(record: BookPage) -> Document:
    if not record.ast:raise HTTPException(409,'This page has not finished conversion.')
    return Document.model_validate_json(record.ast)


def page_json(record: BookPage,include_document: bool=False) -> dict:
    result={'bookId':record.book_id,'pageNumber':record.number,'status':record.status,'progress':record.progress,'engine':record.engine,'error':record.error,'revision':record.revision,'edited':record.edited,'durationSeconds':record.duration,'quality':json.loads(record.quality) if record.quality else None}
    if include_document:result['document']=json.loads(record.ast) if record.ast else None
    return result


def materialize(doc: Document,folder: Path,quality: dict) -> None:
    from app.services.export.pages import editor_snippet
    from app.services.export.standalone import standalone_html
    folder.mkdir(parents=True,exist_ok=True)
    write_json(folder/'document.json',doc.model_dump())
    write_json(folder/'metadata.json',doc.metadata)
    write_json(folder/'quality-report.json',quality)
    (folder/'paste.html').write_text(editor_snippet(doc,folder),encoding='utf-8')
    (folder/'standalone.html').write_text(standalone_html(doc,folder),encoding='utf-8')


def save_page_revision(db,record: BookPage,doc: Document,*,edited: bool) -> None:
    record.revision+=1;doc.revision=record.revision;record.ast=doc.model_dump_json();record.edited=edited;record.updated_at=now()
    db.add(PageRevision(book_id=record.book_id,page=record.number,number=record.revision,ast=record.ast))
    quality=DocumentQualityService().validate(doc,page_folder(record.book_id,record.number));record.quality=json.dumps(quality)
    materialize(doc,page_folder(record.book_id,record.number),quality)


def aggregate_book(db,book: str) -> Document | None:
    job=db.get(Job,book);records=list(db.scalars(select(BookPage).where(BookPage.book_id==book).order_by(BookPage.number)))
    ready=[record for record in records if record.ast]
    if not ready:return None
    doc=Document(documentId=book,sourceFileName=job.filename,sourceChecksum=job.checksum,title=Path(job.filename).stem,pages=[json.loads(record.ast)['pages'][0] for record in ready],metadata={'pageCount':len(records),'completedPages':len(ready),'failedPages':[r.number for r in records if r.status=='FAILED']})
    folder=settings.storage/'documents'/book;(folder/'assets').mkdir(parents=True,exist_ok=True)
    for record in ready:
        page=page_document(record);mapping={}
        for asset in page.assets:
            name=f'p{record.number:04d}-'+Path(asset['path']).name
            mapping[asset['path']]='assets/'+name
            source=page_folder(book,record.number)/asset['path']
            if source.is_file():shutil.copyfile(source,folder/'assets'/name)
            doc.assets.append({**asset,'assetId':name,'path':'assets/'+name,'sourcePage':record.number})
        for block in page.blocks:
            clone=block.model_copy(deep=True);soup=BeautifulSoup(clone.content,'html.parser')
            for image in soup.find_all('img'):
                if image.get('src') in mapping:image['src']=mapping[image['src']]
            clone.content=str(soup);clone.sourcePage=record.number;clone.readingOrder=len(doc.blocks);doc.blocks.append(clone)
        doc.warnings.extend(page.warnings)
    doc.warnings=list(dict.fromkeys(doc.warnings))
    previous=db.scalar(select(Revision).where(Revision.document_id==book).order_by(Revision.number.desc()).limit(1))
    doc.revision=(previous.number+1) if previous else 1
    db.add(Revision(document_id=book,number=doc.revision,ast=doc.model_dump_json()))
    write_json(folder/'document.json',doc.model_dump());(folder/'document.html').write_text(HTMLGenerationService().generate(doc),encoding='utf-8')
    write_json(folder/'quality-report.json',DocumentQualityService().validate(doc,folder))
    (folder/'revisions').mkdir(exist_ok=True);write_json(folder/'revisions'/f'revision-{doc.revision:03}.json',doc.model_dump())
    return doc


def sync_combined_revision(db,whole: Document) -> None:
    """Keep legacy whole-document editing interoperable with indexed page records."""
    records=list(db.scalars(select(BookPage).where(BookPage.book_id==whole.documentId)))
    root=settings.storage/'documents'/whole.documentId
    for record in records:
        if not record.ast:continue
        current=page_document(record);updated=current.model_copy(deep=True)
        updated.blocks=[block.model_copy(deep=True) for block in whole.blocks if block.sourcePage==record.number or (record.number==1 and block.sourcePage is None)]
        mapping={f'assets/p{record.number:04d}-'+Path(asset['path']).name:asset['path'] for asset in current.assets}
        refs=set()
        for index,block in enumerate(updated.blocks):
            block.sourcePage=record.number;block.readingOrder=index;soup=BeautifulSoup(block.content,'html.parser')
            for image in soup.find_all('img'):
                old=str(image.get('src',''));image['src']=mapping.get(old,old);refs.add(old)
            block.content=str(soup)
        updated.assets=[]
        folder=page_folder(whole.documentId,record.number)
        for asset in whole.assets:
            if asset['path'] not in refs:continue
            local=mapping.get(asset['path'],asset['path'])
            if (root/asset['path']).is_file():shutil.copyfile(root/asset['path'],folder/local)
            updated.assets.append({**asset,'path':local,'assetId':Path(local).name,'sourcePage':record.number})
        old_contents=[block.content for block in current.blocks]
        if old_contents!=[block.content for block in updated.blocks]:save_page_revision(db,record,updated,edited=True)
