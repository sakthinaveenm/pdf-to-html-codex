"""One engine per subprocess: isolates models, cancellation and memory reclamation."""
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from app.config.settings import settings
from app.schemas.document import Document, Options
from app.services.pdf_inspector.service import PDFInspectionService
from app.services.converters.lightweight import LightweightConverter
from app.services.html.service import HTMLGenerationService, CSS
from app.services.validation.service import DocumentQualityService

def write_json(path: Path, value) -> None:
    temp = path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    temp.replace(path)

def main() -> None:
    job_id, engine_name = sys.argv[1:3]
    request = json.loads((settings.storage/'tmp'/f'{job_id}.request.json').read_text())
    options = Options.model_validate(request['options'])
    path = settings.storage/'originals'/f'{job_id}.pdf'
    output = settings.storage/'tmp'/f'{job_id}-{engine_name}'
    output.mkdir(parents=True,exist_ok=True); (output/'assets').mkdir(exist_ok=True)
    stage = settings.storage/'tmp'/f'{job_id}.stage.json'
    write_json(stage,{'status':'INSPECTING','progress':10})
    started = time.monotonic()
    report = PDFInspectionService().inspect(path)
    write_json(stage,{'status':'OCR_PROCESSING' if options.force_ocr or any(p['classification']=='SCANNED_IMAGE' for p in report['pages']) else 'CONVERTING','progress':25,'report':report})
    doc = Document(documentId=job_id,sourceFileName=request['filename'],sourceChecksum=hashlib.sha256(path.read_bytes()).hexdigest(),
                   title=Path(request['filename']).stem,language=options.language,pages=report['pages'],warnings=report['warnings'])
    if engine_name == 'MARKER':
        os.environ['TORCH_DEVICE'] = settings.device
        from app.services.converters.heavy import MarkerConverter
        converter = MarkerConverter()
    elif engine_name == 'DOCLING':
        from app.services.converters.heavy import DoclingConverter
        converter = DoclingConverter()
    else: converter = LightweightConverter()
    doc = converter.convert(path,doc,options,output)
    write_json(stage,{'status':'NORMALIZING','progress':80})
    result = HTMLGenerationService().generate(doc)
    write_json(stage,{'status':'VALIDATING','progress':90})
    quality = DocumentQualityService().validate(doc,output)
    if quality['category']=='FAILED': raise ValueError('Conversion produced no usable selectable text.')
    if engine_name != 'LIGHTWEIGHT' and quality['inspectionCharacters'] > 100 and quality['selectableCharacters'] < quality['inspectionCharacters']*.5:
        raise ValueError('Engine output contains less than half the inspected text; trying a fallback is safer.')
    import psutil
    peak = None
    try:
        import resource
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if sys.platform != 'darwin': peak *= 1024
    except ImportError: pass
    doc.metadata.update({'engine':engine_name,'durationSeconds':time.monotonic()-started,'ocrLanguages':options.languages,
                         'processRSSBytesAtCompletion':psutil.Process().memory_info().rss,'processPeakRSSBytes':peak,'gpuPeakBytes':None})
    (output/'document.html').write_text(result,encoding='utf-8')
    (output/'reader.css').write_text(CSS,encoding='utf-8')
    write_json(output/'document.json',doc.model_dump())
    write_json(output/'metadata.json',doc.metadata)
    write_json(output/'quality-report.json',quality)

if __name__ == '__main__':
    main()
