import io
import json
import zipfile
from pathlib import Path
from app.schemas.document import Document
from app.services.html.service import HTMLGenerationService, CSS

ROOT=Path(__file__).resolve().parents[4]

def archive(doc: Document, folder: Path, annotations: list[dict], assets_only: bool=False) -> bytes:
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as archive:
        for asset in doc.assets:
            name=asset['path']
            from app.services.html.service import safe_asset
            if safe_asset(name) and (folder/name).is_file(): archive.write(folder/name,name)
        if not assets_only:
            archive.writestr('document.json',doc.model_dump_json(indent=2))
            archive.writestr('reader.css',CSS)
            archive.writestr('highlights.json',json.dumps(annotations,ensure_ascii=False))
            archive.writestr('document.html',HTMLGenerationService().generate(doc))
            reader=ROOT/'frontend'/'public'/'reader.js'
            if reader.exists():
                archive.write(reader,'reader.js')
                state='window.__readerConfig='+json.dumps({'documentId':doc.documentId,'revision':doc.revision})+';window.__readerInitialAnnotations='+json.dumps(annotations,ensure_ascii=False)+';'
                archive.writestr('reader-state.js',state.replace('<','\\u003c'))
                html=HTMLGenerationService().generate(doc).replace('</body>','<script src="reader-state.js"></script><script src="reader.js"></script></body>')
                archive.writestr('reader.html',html)
                archive.writestr('README.txt','Open document.html for plain editable HTML. reader.html includes the offline Reader API. Use Reader.restore with highlights.json. Browser file:// access may restrict fetch: pass parsed annotations from your host. See REACT_NATIVE_WEBVIEW.md.')
            report=folder/'quality-report.json'
            if report.exists(): archive.write(report,'quality-report.json')
    return buffer.getvalue()
