"""Validate editor-pasted raster data URLs and register them as canonical assets."""
import base64
import binascii
import hashlib
import io
from pathlib import Path
import re
import warnings
from bs4 import BeautifulSoup
from PIL import Image
from app.services.html.service import safe_asset


def import_embedded_images(source: str, folder: Path, assets: list[dict]) -> str:
    soup=BeautifulSoup(source,'html.parser')
    known={}
    for asset in assets:
        relative=asset.get('path','')
        path=(folder/relative).resolve()
        if safe_asset(relative) and path.is_relative_to(folder.resolve()) and path.is_file():
            known[hashlib.sha256(path.read_bytes()).hexdigest()]=relative
    for node in soup.find_all('img'):
        src=str(node.get('src',''))
        if not src.startswith('data:'):continue
        matched=re.fullmatch(r'data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/=\s]+)',src)
        if not matched or len(src)>10_000_000:raise ValueError('Only PNG, JPEG or WebP base64 images up to 10 MB are supported.')
        try:
            raw=base64.b64decode(re.sub(r'\s','',matched[2]),validate=True)
            with warnings.catch_warnings():
                warnings.simplefilter('error',Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(raw)) as image:
                    if image.format not in ('PNG','JPEG','WEBP') or image.width*image.height>20_000_000:raise ValueError('Unsupported or oversized raster image.')
                    image.verify()
        except (OSError,binascii.Error,Image.DecompressionBombError,Image.DecompressionBombWarning) as exc:
            raise ValueError('The embedded image is invalid or too large.') from exc
        checksum=hashlib.sha256(raw).hexdigest()
        if checksum in known:
            node['src']=known[checksum];continue
        name='pasted-'+checksum[:20]+'.png'
        target=folder/'assets'/name;target.parent.mkdir(parents=True,exist_ok=True)
        with Image.open(io.BytesIO(raw)) as image:
            image.convert('RGBA').save(target,format='PNG')
        relative='assets/'+name
        assets.append({'assetId':name,'path':relative,'source':'editor'})
        known[checksum]=relative;node['src']=relative
    return str(soup)
