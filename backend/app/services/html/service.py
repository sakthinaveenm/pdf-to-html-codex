import hashlib
import html
import re
import unicodedata
from urllib.parse import urlsplit
from bs4 import BeautifulSoup, Tag
import nh3
from app.schemas.document import Block, Document
from app.services.html.typography import clean_style, DOCUMENT_CSS, font_faces

TAGS = {'article','section','h1','h2','h3','h4','h5','h6','p','span','strong','em','b','i','u','s','sub','sup','br','ul','ol','li','table','thead','tbody','tfoot','tr','th','td','figure','img','figcaption','blockquote','pre','code','a','hr','math','mrow','mi','mn','mo','mfrac','msup','msub','msqrt','mtext','semantics','annotation'}
ATTRS = {'*':{'id','lang','dir','data-block-id','data-page','data-layout','data-layer','style'},'a':{'href','title'},'img':{'src','alt','width','height'}, 'th':{'rowspan','colspan','scope'},'td':{'rowspan','colspan'},'ol':{'start'},'annotation':{'encoding'}}
CSS = DOCUMENT_CSS + "body{margin:0;background:#fff;color:#202420}::highlight(saved){background:#ffdf70;color:#172226}::highlight(search){background:#9cdbdf;color:#172226}"


def safe_asset(src: str) -> bool:
    return bool(re.fullmatch(r'assets/[A-Za-z0-9_-]+\.(png|jpg|jpeg|webp)', src))

def sanitize(source: str) -> str:
    cleaned = nh3.clean(source, tags=TAGS, attributes=ATTRS, url_schemes={'https','http','mailto'}, link_rel='noopener noreferrer', strip_comments=True,attribute_filter=lambda tag,attr,value: clean_style(value) if attr=='style' else value,filter_style_properties={'text-align','font-family','font-size','font-weight','font-style','line-height','margin-block-start','margin-block-end','width','color','background-color','border-color','text-decoration','text-indent','position','z-index','top','left','pointer-events','display','height','border','border-collapse','table-layout','vertical-align','font-stretch','padding','padding-right','min-height','margin-left','margin-right','white-space','padding-left','list-style-position','word-spacing'})
    soup = BeautifulSoup(cleaned, 'html.parser')
    for node in soup.find_all(style=True):
        normalized=clean_style(str(node.get('style','')))
        if normalized:node['style']=normalized
        else:node.attrs.pop('style',None)
    for image in soup.find_all('img'):
        if not safe_asset(str(image.get('src',''))):
            image.decompose()
    for link in soup.find_all('a'):
        href = str(link.get('href',''))
        if href.startswith('//') or (urlsplit(href).scheme not in ('http','https','mailto') and not href.startswith('#')):
            link.attrs.pop('href', None)
    return str(soup)

class HTMLNormalizationService:
    def blocks(self, source: str, doc_id: str, page: int | None, engine: str, language: str = 'und', start: int = 0) -> list[Block]:
        soup = BeautifulSoup(sanitize(source), 'html.parser')
        root = soup.find('article') or soup.body or soup
        blocks: list[Block] = []
        seen: set[str] = set()
        semantic = {'h1','h2','h3','h4','h5','h6','p','ul','ol','table','figure','blockquote','pre','math','img','figcaption'}
        nodes = [n for n in root.find_all(semantic) if not any(isinstance(p,Tag) and p.name in semantic for p in n.parents if p is not root)]
        if not nodes and root.get_text().strip():
            p = soup.new_tag('p'); p.string = root.get_text(); nodes = [p]
        for i, node in enumerate(nodes):
            content = str(node)
            order = start+i
            existing = str(node.get('data-block-id',''))
            block_id = existing if re.fullmatch(r'b-[a-f0-9]{20}', existing) and existing not in seen else 'b-'+hashlib.sha256(f'{doc_id}:{page}:{order}:{content}'.encode()).hexdigest()[:20]
            seen.add(block_id)
            node.attrs.pop('id',None); node.attrs.pop('data-block-id',None)
            mapped_page = page
            page_owner=node if node.get('data-page') else node.find_parent(attrs={'data-page':True})
            if page_owner and str(page_owner.get('data-page','')).isdigit():
                mapped_page = int(str(page_owner['data-page']))
            node.attrs.pop('data-page',None)
            kind = {'ul':'list','ol':'list','pre':'code','figure':'image','img':'image','figcaption':'caption','math':'equation'}.get(node.name, node.name)
            if re.fullmatch('h[1-6]',node.name): kind = 'heading'
            if kind == 'p': kind = 'paragraph'
            text = node.get_text()
            direction = 'rtl' if sum(unicodedata.bidirectional(c) in ('R','AL') for c in text) > sum(unicodedata.bidirectional(c)=='L' for c in text) else 'auto'
            blocks.append(Block(blockId=block_id,blockType=kind,sourcePage=mapped_page,language=language,direction=direction,
                content=str(node),readingOrder=order,provenance={'engine':engine,'textSource':'ocr' if engine=='tesseract' else 'native-or-engine'}))
        return blocks

class HTMLGenerationService:
    def article(self, doc: Document) -> str:
        soup = BeautifulSoup('', 'html.parser')
        article = soup.new_tag('article', attrs={'lang':doc.language, 'data-document-id':doc.documentId,'class':'pdf-document'})
        soup.append(article)
        section = None; last_page = object()
        for block in sorted(doc.blocks, key=lambda b:b.readingOrder):
            if block.sourcePage != last_page:
                section = soup.new_tag('section', attrs={'data-page':str(block.sourcePage or 0)})
                article.append(section); last_page = block.sourcePage
                background=doc.metadata.get('pageBackground')
                if background and background.get('page')==block.sourcePage and safe_asset(background.get('path','')):
                    section['style']=f"display: flow-root; position: relative; min-height: {background['height']/16:.4f}em; margin-block-end: 0rem"
                    image=soup.new_tag('img',attrs={'src':background['path'],'alt':'','data-layer':'background','style':'position: absolute; top: 0; left: 0; width: 100%; height: auto; z-index: 0; pointer-events: none'})
                    section.append(image)
            parsed = BeautifulSoup(sanitize(block.content), 'html.parser')
            node = next((n for n in parsed.contents if isinstance(n,Tag)), None)
            if node is None:
                node = soup.new_tag('p'); node.string = parsed.get_text()
            node['id'] = block.blockId; node['data-block-id'] = block.blockId
            node['dir'] = block.direction; node['lang'] = block.language
            if block.sourcePage: node['data-page'] = str(block.sourcePage)
            section.append(node)
        return str(article)

    def generate(self, doc: Document) -> str:
        return '<!doctype html><html lang="'+html.escape(doc.language)+'"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src \'self\'; font-src data:; style-src \'unsafe-inline\'; script-src \'self\'"><title>'+html.escape(doc.title)+'</title><style>'+font_faces()+CSS+'</style></head><body>'+self.article(doc)+'</body></html>'

def document_text(doc: Document) -> str:
    return ''.join(BeautifulSoup(b.content,'html.parser').get_text() for b in sorted(doc.blocks,key=lambda b:b.readingOrder))
