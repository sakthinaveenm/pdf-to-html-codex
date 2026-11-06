"""Portable HTML for copying into an editor or downloading as one file."""
import base64
from pathlib import Path
from bs4 import BeautifulSoup
from app.schemas.document import Document
from app.services.html.service import HTMLGenerationService, safe_asset
from app.services.html.typography import font_faces,DOCUMENT_CSS

MIME_TYPES = {'.png':'image/png', '.jpg':'image/jpeg', '.jpeg':'image/jpeg', '.webp':'image/webp'}


def standalone_html(doc: Document, folder: Path, *, fragment: bool = False) -> str:
    generator = HTMLGenerationService()
    # Sanitize canonical content first. Data URLs are introduced only from registered
    # local raster files, never accepted from arbitrary uploaded HTML.
    source = generator.article(doc) if fragment else generator.generate(doc)
    soup = BeautifulSoup(source, 'html.parser')
    registered = {asset['path'] for asset in doc.assets}
    root = folder.resolve()
    for image in soup.find_all('img'):
        relative = str(image.get('src', ''))
        if not safe_asset(relative) or relative not in registered:
            raise ValueError('An image is not a registered document asset; cannot create portable HTML.')
        path = (folder / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError(f'Image asset is missing: {relative}. Cannot create complete single-file HTML.')
        encoded = base64.b64encode(path.read_bytes()).decode('ascii')
        image['src'] = f'data:{MIME_TYPES[path.suffix.lower()]};base64,{encoded}'
    if not fragment:
        csp = soup.find('meta', attrs={'http-equiv':'Content-Security-Policy'})
        if csp:
            csp['content'] = "default-src 'none'; img-src data:; font-src data:; style-src 'unsafe-inline'"
    result=str(soup)
    if fragment:result='<style>'+font_faces()+DOCUMENT_CSS+'</style>'+result
    return result
