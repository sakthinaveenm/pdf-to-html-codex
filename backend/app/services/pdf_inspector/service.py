import re
import unicodedata
from pathlib import Path
import pdfplumber
from pypdf import PdfReader
from app.config.settings import settings

class PDFInspectionService:
    def inspect(self, path: Path) -> dict:
        reader = PdfReader(path, strict=False)
        if reader.is_encrypted:
            raise ValueError('Password-protected PDFs are not supported; upload an unlocked copy.')
        if not 0 < len(reader.pages) <= settings.max_pages:
            raise ValueError(f'PDF must contain 1 to {settings.max_pages} pages.')
        pages = []
        with pdfplumber.open(path) as pdf:
            for index, page in enumerate(pdf.pages):
                text = page.extract_text() or ''
                suspicious = sum(c == '\ufffd' or unicodedata.category(c) in ('Co','Cs') for c in text)
                suspicious += len(re.findall(r'\(cid:\d+\)', text))
                area = max(1, float(page.width * page.height))
                images = sum(max(0, float(i['x1']-i['x0'])) * max(0, float(i['bottom']-i['top'])) for i in page.images)
                glyph_area = sum(float(c['width'] * c['height']) for c in page.chars)
                classification = 'DIGITAL_TEXT'
                if suspicious or re.search(r'(\S)\1{15,}', text):
                    classification = 'TEXT_ENCODING_PROBLEM'
                elif not text.strip():
                    classification = 'SCANNED_IMAGE' if page.images else 'UNKNOWN'
                elif images / area > .15:
                    classification = 'MIXED_CONTENT'
                pages.append({'page':index+1, 'classification':classification, 'width':float(page.width),
                    'height':float(page.height), 'orientation':'landscape' if page.width > page.height else 'portrait',
                    'characters':len(text), 'suspiciousCharacters':suspicious, 'imageAreaRatio':min(1, images/area),
                    'textAreaRatio':min(1, glyph_area/area), 'imageCount':len(page.images)})
                page.close()
        return {'pageCount':len(pages), 'pages':pages, 'metadata':{str(k):str(v) for k,v in (reader.metadata or {}).items()},
                'warnings':['Page classification and reading order are heuristic; review complex layouts.']}
