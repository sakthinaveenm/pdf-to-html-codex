from bs4 import BeautifulSoup
from app.schemas.document import Document
from app.services.html.service import document_text, safe_asset

class DocumentQualityService:
    def validate(self, doc: Document, output) -> dict:
        text = document_text(doc)
        warnings = list(doc.warnings)
        if '\ufffd' in text: warnings.append('Replacement characters found in extracted text.')
        unmapped = sum(b.sourcePage is None for b in doc.blocks)
        if unmapped: warnings.append(f'{unmapped} blocks lack source page mappings.')
        empty = [p['page'] for p in doc.pages if not any(b.sourcePage==p['page'] for b in doc.blocks)]
        if empty: warnings.append(f'Pages with no mapped content: {empty}')
        expected = sum(p['characters'] for p in doc.pages)
        if expected and len(text) < expected*.7:
            warnings.append(f'Extracted character count {len(text)} is substantially below inspection count {expected}; review for omitted content.')
        broken = []
        for block in doc.blocks:
            soup = BeautifulSoup(block.content,'html.parser')
            for img in soup.find_all('img'):
                src = str(img.get('src',''))
                if not safe_asset(src) or not (output/src).is_file(): broken.append(src)
        if broken: warnings.append('Missing local assets: '+', '.join(broken))
        return {'category':'FAILED' if not text.strip() else 'REQUIRES_REVIEW' if warnings else 'PASS',
                'selectableCharacters':len(text),'inspectionCharacters':expected,'blockCount':len(doc.blocks),
                'pageCount':len(doc.pages),'unmappedBlocks':unmapped,'missingAssets':broken,
                'warnings':list(dict.fromkeys(warnings)),
                'limits':['Reading order and OCR accuracy cannot be proven by these structural diagnostics.','External link reachability is not checked offline.']}
