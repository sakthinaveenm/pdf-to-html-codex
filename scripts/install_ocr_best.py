"""Install the pinned optional high-accuracy Hindi OCR model for local conversion."""
import hashlib
from pathlib import Path
import tempfile
import urllib.request
import json
ROOT=Path(__file__).resolve().parents[1]
URL='https://raw.githubusercontent.com/tesseract-ocr/tessdata_best/4.1.0/'
SHA='bd2e65a2184af08a167b0be2439e91fa5edbc4394399ca2f692b843ae26e78d6'

def install(folder):
    folder.mkdir(parents=True,exist_ok=True);target=folder/'hin.traineddata'
    if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest()!=SHA:
        with tempfile.NamedTemporaryFile(dir=folder,delete=False) as handle:path=Path(handle.name)
        try:
            with urllib.request.urlopen(URL+'hin.traineddata',timeout=120) as response:path.write_bytes(response.read())
            if hashlib.sha256(path.read_bytes()).hexdigest()!=SHA:raise ValueError('OCR model checksum mismatch')
            path.replace(target)
        finally:path.unlink(missing_ok=True)
    with urllib.request.urlopen(URL+'LICENSE',timeout=30) as response:(folder/'LICENSE').write_bytes(response.read())
    (folder/'manifest.json').write_text(json.dumps({'source':URL+'hin.traineddata','version':'4.1.0','sha256':SHA,'license':'Apache-2.0'},indent=2))
    print(f'Verified high-accuracy Hindi OCR model: {target}')

if __name__=='__main__':
    import sys
    install(Path(sys.argv[1]).expanduser().resolve() if len(sys.argv)>1 else ROOT/'storage'/'models'/'tessdata_best')
