import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from PIL import ImageOps

class OCRService:
    @staticmethod
    def languages() -> list[str]:
        if not shutil.which('tesseract'):
            return []
        try:
            output = subprocess.run(['tesseract','--list-langs'], capture_output=True, text=True, timeout=10, check=True)
            return [s.strip() for s in output.stdout.splitlines()[1:] if re.fullmatch(r'[\w/]+', s.strip())]
        except (subprocess.SubprocessError, OSError):
            return []

    def recognize(self, image, languages: list[str]) -> str:
        if any(not re.fullmatch(r'[A-Za-z0-9_]+', lang) for lang in languages):
            raise ValueError('Invalid Tesseract language code.')
        missing = set(languages) - set(self.languages())
        if missing:
            raise ValueError(f'Missing Tesseract language packs: {", ".join(sorted(missing))}. See MULTILINGUAL_OCR.md.')
        with tempfile.TemporaryDirectory(prefix='pdf-ocr-') as tmp:
            path = Path(tmp) / 'page.png'
            ImageOps.autocontrast(image.convert('L')).save(path)
            result = subprocess.run(['tesseract', str(path), 'stdout', '-l', '+'.join(languages), '--psm', '3'],
                                    capture_output=True, text=True, encoding='utf-8', timeout=180, check=True)
            return result.stdout
