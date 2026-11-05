import importlib.util
from pathlib import Path
from bs4 import BeautifulSoup
from app.schemas.document import Document, Options
from app.services.converters.base import PDFConverter
from app.services.html.service import HTMLNormalizationService

class MarkerConverter(PDFConverter):
    name = 'MARKER'
    def check_availability(self) -> bool:
        from app.config.settings import settings
        if settings.marker_python:
            import subprocess
            try:
                result = subprocess.run([str(Path(settings.marker_python).resolve()),'-c',
                    'import importlib.util; raise SystemExit(0 if importlib.util.find_spec("marker") else 1)'],
                    capture_output=True, timeout=5)
                return result.returncode == 0
            except (OSError, subprocess.SubprocessError): return False
        return importlib.util.find_spec('marker') is not None
    def convert(self, path: Path, document: Document, options: Options, output: Path) -> Document:
        from marker.converters.pdf import PdfConverter
        from marker.models import create_model_dict
        from app.config.settings import settings
        converter = PdfConverter(artifact_dict=create_model_dict(device=settings.device), renderer='marker.renderers.html.HTMLRenderer',
                                 config={'use_llm':False,'force_ocr':options.force_ocr,'paginate_output':True})
        rendered = converter(str(path))
        source = BeautifulSoup(rendered.html,'html.parser')
        for index, (name,image) in enumerate(rendered.images.items()):
            asset = f'image-{index+1}.png'; image.save(output/'assets'/asset)
            for node in source.find_all('img',src=name): node['src'] = 'assets/'+asset
            document.assets.append({'assetId':asset,'path':'assets/'+asset})
        # Marker pagination emits div.page with data-page-id (zero based).
        containers = source.find_all(attrs={'data-page-id':True})
        if containers:
            for index,node in enumerate(containers):
                page = int(str(node.get('data-page-id',index)))+1
                document.blocks.extend(HTMLNormalizationService().blocks(str(node),document.documentId,page,self.name,options.language,len(document.blocks)))
        else:
            document.blocks = HTMLNormalizationService().blocks(str(source),document.documentId,None,self.name,options.language)
            document.warnings.append('Marker output has no page containers; source page mappings are unknown.')
        document.metadata['converterMetadata'] = rendered.metadata
        document.warnings.append('Marker uses its own multilingual OCR models; requested Tesseract packs apply only to the lightweight engine.')
        return document

class DoclingConverter(PDFConverter):
    name = 'DOCLING'
    def check_availability(self) -> bool:
        return importlib.util.find_spec('docling') is not None
    def convert(self, path: Path, document: Document, options: Options, output: Path) -> Document:
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions, TesseractCliOcrOptions
        from docling.datamodel.accelerator_options import AcceleratorOptions, AcceleratorDevice
        from docling_core.types.doc import ImageRefMode
        pipeline = PdfPipelineOptions()
        pipeline.do_ocr = options.force_ocr or any(p['classification'] in ('SCANNED_IMAGE','TEXT_ENCODING_PROBLEM') for p in document.pages)
        pipeline.ocr_options = TesseractCliOcrOptions(lang=options.languages,force_full_page_ocr=options.force_ocr)
        from app.config.settings import settings
        pipeline.accelerator_options = AcceleratorOptions(device=AcceleratorDevice.CUDA if settings.device=='cuda' else AcceleratorDevice.CPU)
        pipeline.generate_picture_images = True
        converted = DocumentConverter(format_options={InputFormat.PDF:PdfFormatOption(pipeline_options=pipeline)}).convert(path)
        # Page-filtered serialization preserves native text, tables and provenance.
        import base64
        import io
        from PIL import Image
        for page_no in sorted(converted.document.pages):
            source = BeautifulSoup(converted.document.export_to_html(page_no=page_no, image_mode=ImageRefMode.EMBEDDED), 'html.parser')
            for node in source.find_all('img'):
                src = str(node.get('src',''))
                if not src.startswith('data:image/') or ';base64,' not in src: continue
                raw = base64.b64decode(src.split(';base64,',1)[1],validate=True)
                asset = f'image-{len(document.assets)+1}.png'
                with Image.open(io.BytesIO(raw)) as image: image.save(output/'assets'/asset)
                node['src'] = 'assets/'+asset
                document.assets.append({'assetId':asset,'path':'assets/'+asset,'sourcePage':page_no})
            document.blocks.extend(HTMLNormalizationService().blocks(str(source),document.documentId,page_no,self.name,options.language,len(document.blocks)))
        return document
