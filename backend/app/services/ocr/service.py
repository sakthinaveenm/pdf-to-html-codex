import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from PIL import ImageOps

# Used only when a script pack is unavailable; explicit codes remain unrestricted.
SCRIPT_LANGUAGES = {
 'Latin':['eng','fra','deu','spa','por','ita','vie'], 'Tamil':['tam'],
 'Devanagari':['hin','mar','san','nep'], 'Telugu':['tel'], 'Malayalam':['mal'],
 'Kannada':['kan'], 'Bengali':['ben','asm'], 'Gujarati':['guj'], 'Gurmukhi':['pan'],
 'Arabic':['ara','urd','fas'], 'Han':['chi_sim'], 'Japanese':['jpn'],
 'Hangul':['kor'], 'Cyrillic':['rus','ukr'], 'Hebrew':['heb'], 'Thai':['tha'],
 'Greek':['ell'], 'Sinhala':['sin'], 'Myanmar':['mya'], 'Khmer':['khm'],
}

class OCRService:
    @staticmethod
    def languages() -> list[str]:
        if not shutil.which('tesseract'): return []
        try:
            output = subprocess.run(['tesseract','--list-langs'],capture_output=True,text=True,timeout=10,check=True)
            return [s.strip() for s in output.stdout.splitlines()[1:] if re.fullmatch(r'[\w/]+',s.strip())]
        except (subprocess.SubprocessError,OSError): return []

    def resolve_languages(self,image,requested: list[str],hint: str | None=None) -> tuple[list[str],str | None]:
        if 'auto' not in requested:return requested,None
        installed=set(self.languages())
        if not installed:raise ValueError('Tesseract is not installed or no OCR packs are available.')
        if hint:
            if hint not in installed:raise ValueError(f'The PDF uses legacy {hint} glyphs, but its OCR language pack is not installed: {hint}.')
            return [hint]+(['eng'] if hint!='eng' and 'eng' in installed else []),None
        script=None
        if 'osd' in installed:
            with tempfile.TemporaryDirectory(prefix='pdf-script-') as tmp:
                path=Path(tmp)/'page.png';image.save(path)
                try:
                    result=subprocess.run(['tesseract',str(path),'stdout','--psm','0','-l','osd'],capture_output=True,text=True,timeout=30,check=True)
                    match=re.search(r'^Script:\s*(\S+)',result.stdout,re.MULTILINE)
                    if match:script=match[1]
                except (subprocess.SubprocessError,OSError):pass
        if script:
            candidates=[f'script/{script}',script]
            if script=='Han':candidates=['script/HanS','chi_sim','chi_tra']
            for candidate in candidates:
                if candidate in installed:return [candidate],None
            selected=[code for code in SCRIPT_LANGUAGES.get(script,[]) if code in installed]
            if selected:return selected,f'Automatic OCR detected {script}; using available packs: {", ".join(selected)}.'
        # Small or mixed-script pages can defeat script detection. Report a bounded,
        # real fallback rather than loading every installed language or claiming certainty.
        fallback=[code for code in ('eng','tam','hin') if code in installed]
        if not fallback:fallback=sorted(code for code in installed if code not in ('osd','equ'))[:1]
        if not fallback:raise ValueError('No usable OCR text language packs are installed.')
        return fallback,'Automatic script detection was uncertain; using '+', '.join(fallback)+'. Choose explicit OCR languages if text is incorrect.'

    def recognize(self,image,languages: list[str]) -> str:
        if any(not re.fullmatch(r'(?:script/)?[A-Za-z0-9_]+',lang) for lang in languages):raise ValueError('Invalid Tesseract language code.')
        missing=set(languages)-set(self.languages())
        if missing:raise ValueError(f'Missing Tesseract language packs: {", ".join(sorted(missing))}. See MULTILINGUAL_OCR.md.')
        with tempfile.TemporaryDirectory(prefix='pdf-ocr-') as tmp:
            path=Path(tmp)/'page.png';ImageOps.autocontrast(image.convert('L')).save(path)
            result=subprocess.run(['tesseract',str(path),'stdout','-l','+'.join(languages),'--psm','3'],capture_output=True,text=True,encoding='utf-8',timeout=180,check=True)
            return result.stdout

    def recognize_layout(self,image,languages: list[str],scale: float,*,model_dir: Path | None=None):
        from app.services.ocr.layout import parse_tsv
        if any(not re.fullmatch(r'(?:script/)?[A-Za-z0-9_]+',code) for code in languages):raise ValueError('Invalid Tesseract language code.')
        missing=set(languages)-set(self.languages())
        if missing:raise ValueError('Missing OCR packs: '+', '.join(sorted(missing)))
        with tempfile.TemporaryDirectory(prefix='pdf-ocr-layout-') as tmp:
            path=Path(tmp)/'page.png';ImageOps.autocontrast(image.convert('L')).save(path)
            command=['tesseract',str(path.resolve()),'stdout','-l','+'.join(languages),'--oem','1','--psm','3']
            if model_dir:command+=['--tessdata-dir',str(model_dir.resolve())]
            result=subprocess.run(command+['-c','tessedit_create_tsv=1'],capture_output=True,text=True,encoding='utf-8',timeout=180,check=True)
            return parse_tsv(result.stdout,scale)
