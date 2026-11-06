import copy
import io
import json
from pathlib import Path
from urllib.parse import urlsplit,quote
import zipfile
from bs4 import BeautifulSoup
from app.schemas.document import Document
from app.services.html.service import HTMLGenerationService
from app.services.html.typography import FONT_DIR,FONT_STACKS
from app.services.export.standalone import standalone_html


def editor_snippet(doc: Document,folder: Path,*,image_mode: str='embedded',asset_base_url: str | None=None) -> str:
    if image_mode not in ('embedded','url'):raise ValueError('Image mode must be embedded or url.')
    if image_mode=='embedded':source=standalone_html(doc,folder,fragment=True)
    else:
        if not asset_base_url or urlsplit(asset_base_url).scheme not in ('http','https') or not urlsplit(asset_base_url).netloc:
            raise ValueError('Provide an absolute HTTP(S) asset base URL for destination-hosted images.')
        if urlsplit(asset_base_url).query or urlsplit(asset_base_url).fragment:raise ValueError('Asset base URL cannot include query strings or fragments.')
        source=HTMLGenerationService().article(doc)
    soup=BeautifulSoup(source,'html.parser');article=soup.find('article');section=soup.new_tag('section')
    page=int(doc.metadata.get('pageNumber',doc.pages[0]['page'] if doc.pages else 1))
    section['data-page']=str(page);section['data-document-id']=doc.documentId;section['lang']=doc.language;section['dir']='auto'
    section['style']=f'display: flow-root; position: relative; min-height: {doc.metadata.get("pageBackground",{}).get("height",0)/16:.4f}em; font-family: {FONT_STACKS["serif"]}; font-size: 16px; line-height: 1.65; max-width: 100%; overflow-wrap: anywhere; box-sizing: border-box'
    if article:
        for child in list(article.find_all('section',recursive=False)):
            for node in list(child.children):section.append(node)
    for node in section.find_all(True):
        style=str(node.get('style',''))
        if node.name in ('p','h1','h2','h3','h4','h5','h6','li','td','th','figcaption'):
            defaults=f'font-family: {FONT_STACKS["serif"]}; '
            if 'font-size:' not in style:
                defaults+='font-size: '+{'h1':'2.5em','h2':'1.75em','h3':'1.3em','figcaption':'.8em'}.get(node.name,'1em')+'; '
            if 'line-height:' not in style:defaults+='line-height: 1.25; ' if node.name.startswith('h') else 'line-height: 1.65; '
            if 'margin-block-start:' not in style and node.name in ('p','h1','h2','h3'):defaults+='margin-block-start: 0.7rem; margin-block-end: 0.7rem; '
            node['style']=defaults+style
        if node.name=='figure':node['style']='margin: 1rem 0; '+style
        if node.name=='img' and node.get('data-layer')!='background':
            node['style']='max-width: 100%; height: auto; display: block; margin-left: auto; margin-right: auto; '+style
        if node.name=='img':
            if image_mode=='url':
                src=str(node.get('src',''));registered={asset['path'] for asset in doc.assets}
                if src not in registered:raise ValueError('Unregistered image reference in page HTML.')
                node['src']=asset_base_url.rstrip('/')+'/'+quote(f'p{page:04d}-'+Path(src).name)
        if node.name=='table':node['style']='border-collapse: collapse; max-width: 100%; '+style
        if node.name in ('td','th') and not node.find_parent('table',attrs={'data-layout':'columns'}):node['style']='border: 1px solid #ccd2cc; padding: .45em .65em; vertical-align: top; '+str(node.get('style',''))
    return str(section)


def page_zip(doc: Document,folder: Path,image_mode='embedded',asset_base_url=None) -> bytes:
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as archive:
        write_page(archive,'',doc,folder,image_mode,asset_base_url)
        for license in FONT_DIR.glob('*-OFL.txt'):archive.write(license,'licenses/'+license.name)
    return buffer.getvalue()


def write_page(archive,prefix,doc,folder,image_mode='embedded',asset_base_url=None):
    archive.writestr(prefix+'paste.html',editor_snippet(doc,folder,image_mode=image_mode,asset_base_url=asset_base_url))
    archive.writestr(prefix+'standalone.html',standalone_html(doc,folder))
    archive.writestr(prefix+'metadata.json',doc.model_dump_json(indent=2))
    archive.writestr(prefix+'asset-manifest.json',json.dumps({'page':doc.metadata.get('pageNumber'),'imageMode':image_mode,'assetBaseURL':asset_base_url,'assets':[{**asset,'destinationFileName':f'p{int(doc.metadata.get("pageNumber",1)):04d}-'+Path(asset['path']).name} for asset in doc.assets],'fontDependencies':doc.metadata.get('fontDependencies',[])},ensure_ascii=False,indent=2))
    from app.services.html.service import safe_asset
    for asset in doc.assets:
        if safe_asset(asset['path']) and (folder/asset['path']).is_file():archive.write(folder/asset['path'],prefix+asset['path'])
    if (folder/'quality-report.json').is_file():archive.write(folder/'quality-report.json',prefix+'quality-report.json')
