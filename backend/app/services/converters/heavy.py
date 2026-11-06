from app.helpers.runtime import interpreter_path
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
                result = subprocess.run([interpreter_path(settings.marker_python),'-c',
                    'import importlib.util; raise SystemExit(0 if importlib.util.find_spec("marker") else 1)'],
                    capture_output=True, timeout=5)
                return result.returncode == 0
            except (OSError, subprocess.SubprocessError): return False
        return importlib.util.find_spec('marker') is not None
    def convert(self, path: Path, document: Document, options: Options, output: Path) -> Document:
        from marker.converters.pdf import PdfConverter
        from marker.models import create_model_dict
        from app.config.settings import settings
        force=options.force_ocr or any(p['classification']=='TEXT_ENCODING_PROBLEM' for p in document.pages)
        key=(settings.device,force)
        if not hasattr(self,'_models'):self._models=create_model_dict(device=settings.device)
        if getattr(self,'_converter_key',None)!=key:
            self._converter=PdfConverter(artifact_dict=self._models,renderer='marker.renderers.html.HTMLRenderer',config={'use_llm':False,'force_ocr':force,'paginate_output':True})
            self._converter_key=key
        converter=self._converter
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
        pipeline.do_ocr = options.force_ocr or any(p.get('requiresOCR',False) or p['classification'] in ('SCANNED_IMAGE','TEXT_ENCODING_PROBLEM') for p in document.pages)
        ocr_languages=options.languages
        if 'auto' in ocr_languages:
            ocr_languages=['eng']
            if pipeline.do_ocr:
                import pypdfium2 as pdfium
                from app.services.ocr.service import OCRService
                detected=[]
                pdf=pdfium.PdfDocument(path)
                try:
                    for info in document.pages:
                        if not options.force_ocr and not info.get('requiresOCR',False) and info['classification'] not in ('SCANNED_IMAGE','TEXT_ENCODING_PROBLEM'):continue
                        image=pdf[info['page']-1].render(scale=options.dpi/72).to_pil()
                        try:codes,warning=OCRService().resolve_languages(image,['auto'],info.get('ocrLanguageHint'))
                        finally:image.close()
                        detected.extend(code for code in codes if code not in detected)
                        info['ocrLanguages']=codes
                        if warning:document.warnings.append(f"Page {info['page']}: {warning}")
                finally:pdf.close()
                if detected:ocr_languages=detected
        pipeline.ocr_options = TesseractCliOcrOptions(lang=ocr_languages,force_full_page_ocr=options.force_ocr or any(p['classification']=='TEXT_ENCODING_PROBLEM' for p in document.pages))
        from app.config.settings import settings
        pipeline.accelerator_options = AcceleratorOptions(device=AcceleratorDevice.CUDA if settings.device=='cuda' else AcceleratorDevice.CPU)
        pipeline.generate_picture_images = True
        key=(tuple(ocr_languages),pipeline.do_ocr,pipeline.ocr_options.force_full_page_ocr,settings.device)
        if getattr(self,'_converter_key',None)!=key:
            self._converter=DocumentConverter(format_options={InputFormat.PDF:PdfFormatOption(pipeline_options=pipeline)})
            self._converter_key=key
        converted = self._converter.convert(path)
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
            page_info=next((page for page in document.pages if page['page']==page_no),{})
            visible=source.get_text(' ',strip=True)
            hint=page_info.get('ocrLanguageHint')
            expected_range=(0x900,0x97f) if hint in ('hin','nep') else (0xb80,0xbff) if hint=='tam' else None
            missing_script=bool(expected_range and sum(expected_range[0]<=ord(char)<=expected_range[1] for char in visible)<5)
            if page_info.get('requiresOCR') and (len(visible)<8 or missing_script):
                # Layout models can classify a decorative title page as one picture.
                # Recover its actual text instead of presenting the picture as selectable HTML.
                import pypdfium2 as pdfium
                import html
                from app.services.ocr.service import OCRService
                pdf=pdfium.PdfDocument(path)
                try:
                    image=pdf[page_no-1].render(scale=max(options.dpi,300)/72).to_pil()
                    try:
                        codes,warning=OCRService().resolve_languages(image,options.languages,hint)
                        regions=OCRService().recognize_layout(image,codes,max(options.dpi,300)/72)
                    finally:image.close()
                finally:pdf.close()
                import pdfplumber
                from app.services.html.source_layout import is_title_page,cover_html
                from app.services.ocr.layout import region_markup,align_regions_to_page
                with pdfplumber.open(path) as pdf:
                    original=pdf.pages[page_no-1]
                    regions=align_regions_to_page(regions,original)
                    title_page=is_title_page(original)
                    paragraphs=cover_html(original,regions,path,output,document.assets) if title_page else ''.join(region_markup(region,original,cover=False) for region in regions)
                if title_page:
                    source=BeautifulSoup('','html.parser')
                for node in list(source.select('p,h1,h2,h3,h4,h5,h6,ul,ol,table,blockquote,pre')):
                    if node.parent is not None and not node.find('img'):node.decompose()
                source=BeautifulSoup(paragraphs+str(source),'html.parser')
                page_info['textSource']='ocr-recovery'
                page_info['ocrLanguages']=codes
                document.warnings.append(f'Page {page_no}: recovered selectable text from a region classified as an image; review reading order.')
                if warning:document.warnings.append(f'Page {page_no}: {warning}')
            document.blocks.extend(HTMLNormalizationService().blocks(str(source),document.documentId,page_no,self.name,options.language,len(document.blocks)))
        referenced={str(image.get('src','')) for block in document.blocks for image in BeautifulSoup(block.content,'html.parser').find_all('img')}
        document.assets=[asset for asset in document.assets if asset['path'] in referenced]
        return document
