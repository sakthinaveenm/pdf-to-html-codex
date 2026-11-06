"""One model process converts selected pages and publishes each result atomically."""
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import traceback
from pypdf import PdfReader,PdfWriter
from app.config.settings import settings
from app.schemas.document import Document,Options
from app.services.converters.lightweight import LightweightConverter
from app.services.html.source_typography import apply_source_typography
from app.services.validation.service import DocumentQualityService
from app.workers.convert import write_json


def main():
    book,engine=sys.argv[1:3]
    request=json.loads((settings.storage/'tmp'/f'{book}.request.json').read_text())
    options=Options.model_validate(request['options']);source=settings.storage/'originals'/f'{book}.pdf'
    reader=PdfReader(source);checksum=request.get('checksum') or hashlib.sha256(source.read_bytes()).hexdigest()
    root=settings.storage/'tmp'/f'{book}-{engine}'
    if engine=='MARKER':
        os.environ['TORCH_DEVICE']=settings.device
        from app.services.converters.heavy import MarkerConverter
        converter=MarkerConverter()
    elif engine=='DOCLING':
        from app.services.converters.heavy import DoclingConverter
        converter=DoclingConverter()
    else:converter=LightweightConverter()
    info_by_page={info['page']:info for info in request['inspection']['pages']}
    for number in request['pages']:
        folder=root/'pages'/f'{number:04d}';(folder/'assets').mkdir(parents=True,exist_ok=True)
        stage=settings.storage/'tmp'/f'{book}.stage.json'
        info=dict(info_by_page[number]);local={**info,'page':1};started=time.monotonic()
        write_json(stage,{'page':number,'status':'OCR_PROCESSING' if info.get('requiresOCR') or options.force_ocr else 'CONVERTING','progress':25})
        try:
            path=folder/'source.pdf';writer=PdfWriter();writer.add_page(reader.pages[number-1])
            with path.open('wb') as output:writer.write(output)
            doc=Document(documentId=book,sourceFileName=request['filename'],sourceChecksum=checksum,title=Path(request['filename']).stem,language=options.language,pages=[local],metadata={'pageNumber':number,'pageId':f'{book}:page:{number}'},warnings=list(request['inspection'].get('warnings',[])))
            # Deterministic IDs must distinguish identical text on different source pages.
            doc.documentId=f'{book}-page-{number}'
            doc=converter.convert(path,doc,options,folder)
            doc.metadata['fontMapping']=options.font_mapping
            doc=apply_source_typography(doc,path,folder,1,recover_cover=True)
            doc.documentId=book;doc.pages[0]['page']=number
            for block in doc.blocks:block.sourcePage=number
            for asset in doc.assets:asset['sourcePage']=number
            if doc.metadata.get('pageBackground'):doc.metadata['pageBackground']['page']=number
            doc.metadata.update({'engine':engine,'pageNumber':number,'pageId':f'{book}:page:{number}','durationSeconds':time.monotonic()-started})
            quality=DocumentQualityService().validate(doc,folder)
            if quality['category']=='FAILED' and (info.get('characters',0)>0 or info.get('imageCount',0)>0):raise ValueError('Page conversion produced no selectable text.')
            if quality['category']=='FAILED':quality.update({'category':'WARNING','warnings':['Original PDF page is blank.']});doc.metadata['blankPage']=True
            from app.services.documents.pages import materialize
            materialize(doc,folder,quality)
            path.unlink(missing_ok=True)
            write_json(folder/'_complete.json',{'durationSeconds':time.monotonic()-started})
        except Exception as exc:
            traceback.print_exc()
            write_json(folder/'_error.json',{'message':str(exc),'engine':engine,'page':number})
    reader.close()

if __name__=='__main__':main()
