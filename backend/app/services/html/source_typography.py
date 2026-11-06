from collections import Counter
from pathlib import Path
import re
import pdfplumber
import pypdfium2 as pdfium
from pypdf import PdfReader
from bs4 import BeautifulSoup
from app.schemas.document import Document
from app.config.settings import settings
from app.services.html.service import HTMLNormalizationService
from app.services.html.source_layout import is_title_page,cover_html
from app.services.ocr.layout import align_regions_to_page,family_for_font
from app.services.ocr.service import OCRService
from app.services.html.typography import FONT_STACKS,clean_style


def apply_source_typography(doc: Document,source: Path,output: Path,source_page: int=1,recover_cover: bool=True) -> Document:
    """Apply source font categories and recover a sparse title page as actual blocks."""
    with pdfplumber.open(source) as pdf:
        page=pdf.pages[source_page-1]
        crop=page.cropbox or page.bbox
        if doc.pages:
            doc.pages[0].update({'displayWidth':min(page.bbox[2],crop[2])-max(page.bbox[0],crop[0]),'displayHeight':min(page.bbox[3],crop[3])-max(page.bbox[1],crop[1]),'cropBox':list(crop)})
        descriptors={}
        try:
            reader=PdfReader(source)
            resources=reader.pages[source_page-1].get('/Resources',{})
            for item in resources.get('/Font',{}).values():
                font=item.get_object();name=str(font.get('/BaseFont','')).lstrip('/')
                descendants=font.get('/DescendantFonts',[])
                descriptor=(descendants[0].get_object() if descendants else font).get('/FontDescriptor')
                descriptor=descriptor.get_object() if descriptor else {}
                descriptors[name]={'embedded':'yes' if any(key in descriptor for key in ('/FontFile','/FontFile2','/FontFile3')) else 'no','unicodeMapping':'present' if '/ToUnicode' in font else 'absent'}
            reader.close()
        except Exception:
            pass  # Unknown is reported explicitly; do not infer Unicode from a font name.
        font_groups={}
        for char in page.chars:
            name=str(char.get('fontname','unknown'));entry=font_groups.setdefault(name,{'sourceFont':name,'family':family_for_font(name),'sizes':set(),'subset':bool(re.match(r'^[A-Z]{6}\+',name)),'embedded':'unknown','unicodeMapping':'unknown'})
            entry.update(descriptors.get(name,{}));entry['sizes'].add(round(float(char.get('size',0)),2))
        fonts=[{**entry,'sizes':sorted(entry['sizes'])} for entry in font_groups.values()]
        doc.metadata['fonts']=fonts
        doc.metadata['fontDependencies']=['Folio Serif / Noto Serif','Folio Devanagari / Noto Serif Devanagari','Folio Tamil / Noto Serif Tamil','Destination editors may substitute installed Unicode fallback fonts.']
        legacy=any(re.search('chanakya|krutidev|devlys|bamini|suntommy',name,re.I) for name in font_groups)
        if legacy and recover_cover:
            from app.services.html.page_graphics import page_layers
            from app.services.html.flow_layout import flowing_layout
            image,background,removed=page_layers(source,source_page,output,page,ocr_dpi=300)
            try:
                hint='hin' if any(re.search('chanakya|krutidev|devlys',name,re.I) for name in font_groups) else 'tam'
                codes,warning=OCRService().resolve_languages(image,['auto'],hint)
                model_dir=settings.storage/'models'/'tessdata_best'
                if not (model_dir/f'{hint}.traineddata').is_file():model_dir=None
                regions=align_regions_to_page(OCRService().recognize_layout(image,[hint],300/72),page)
                from app.services.ocr.refinement import refine_lines
                repaired=refine_lines(image,regions,page,[hint],model_dir,300/72)
                uncertain=sum(float(word.get('confidence',0))<60 for region in regions for line in region.lines for word in line)
                doc.metadata['ocrRefinement']={'dpi':300,'smallPrintRetryDpi':450,'model':'system-detection+best-line-retry' if model_dir else 'system','repairedLines':repaired,'uncertainWords':uncertain}
                doc.warnings=[warning for warning in doc.warnings if not warning.startswith('Low-confidence OCR:')]
                if uncertain:doc.warnings.append(f'Low-confidence OCR: {uncertain} words require comparison with the original PDF.')
                doc.pages[0]['ocrDpi']=300
            finally:image.close()
            markup,columns=flowing_layout(page.dedupe_chars(tolerance=1),regions)
            if not markup.strip():raise ValueError('Source layout recovery found no mapped selectable text.')
            previous={BeautifulSoup(block.content,'html.parser').get_text(' ',strip=True):block.blockId for block in doc.blocks}
            doc.blocks=HTMLNormalizationService().blocks(markup,doc.documentId,doc.pages[0]['page'],'tesseract-layout',doc.language)
            for block in doc.blocks:
                old=previous.get(BeautifulSoup(block.content,'html.parser').get_text(' ',strip=True))
                if old:block.blockId=old
                block.provenance.update({'formatting':'source-metrics-flow','columns':columns})
            background['sourcePage']=doc.pages[0]['page'];doc.assets=[background]
            doc.metadata['pageBackground']={'path':background['path'],'page':doc.pages[0]['page'],'height':doc.pages[0]['displayHeight']}
            doc.pages[0]['ocrLanguages']=[hint]
            doc.metadata['sourceLayout']={'version':4,'columns':columns,'watermarkExcludedFromOCR':removed,'graphicsContainMainText':False,'fontFit':'harfbuzz-ink-box'}
            mapping=doc.metadata.get('fontMapping',{})
            override=mapping.get('*') or next((target for name,target in mapping.items() if any(re.sub(r'^[A-Z]{6}\+','',font['sourceFont']).casefold()==name.casefold() for font in fonts)),None)
            if override:
                for block in doc.blocks:
                    tree=BeautifulSoup(block.content,'html.parser')
                    for node in tree.find_all(['p','h1','h2','h3','h4','li','figcaption']):node['style']=clean_style(str(node.get('style',''))+f'; font-family: {FONT_STACKS[override]}')
                    block.content=str(tree)
            doc.metadata['typographyVersion']=4
            doc.metadata['formattingLimitations']=['Source font sizes and flowing columns are retained; Unicode font glyph metrics and OCR may differ.','Graphics layer contains source shapes, images and watermark; main text remains selectable HTML. Destination editors can strip positioning styles.']
            if warning:doc.warnings.append(warning)
            return doc
        cover=source_page==1 and is_title_page(page)
        styled_cover=any(block.blockType=='heading' and 'font-size:' in block.content for block in doc.blocks)
        if cover and recover_cover and not styled_cover:
            renderer=pdfium.PdfDocument(source)
            try:
                image=renderer[source_page-1].render(scale=300/72).to_pil()
                try:
                    hint='hin' if any(re.search('chanakya|krutidev|devlys',name,re.I) for name in font_groups) else 'tam' if any(re.search('bamini|suntommy',name,re.I) for name in font_groups) else None
                    codes,warning=OCRService().resolve_languages(image,['auto'],hint)
                    regions=OCRService().recognize_layout(image,codes,300/72)
                finally:image.close()
            finally:renderer.close()
            old={BeautifulSoup(block.content,'html.parser').get_text(' ',strip=True):block for block in doc.blocks}
            html=cover_html(page,align_regions_to_page(regions,page),source,output,doc.assets)
            blocks=HTMLNormalizationService().blocks(html,doc.documentId,doc.pages[0]['page'],'tesseract-layout',doc.language)
            for block in blocks:
                match=old.get(BeautifulSoup(block.content,'html.parser').get_text(' ',strip=True))
                if match:block.blockId=match.blockId
                block.provenance['formatting']='source-font-metrics-and-ocr-boxes'
            doc.blocks=blocks
            referenced={str(image.get('src','')) for block in blocks for image in BeautifulSoup(block.content,'html.parser').find_all('img')}
            doc.assets=[asset for asset in doc.assets if asset['path'] in referenced]
            if warning:doc.warnings.append(warning)
        dominant=Counter(family_for_font(str(char['fontname'])) for char in page.chars).most_common(1)
        family=doc.metadata.get('fontMapping',{}).get('*',dominant[0][0] if dominant else 'serif')
        sizes=Counter(round(float(char['size']),1) for char in page.chars if char.get('size',0)>0)
        body=max(.875,min(1.25,(sizes.most_common(1)[0][0] if sizes else 16)/16))
        for block in doc.blocks:
            soup=BeautifulSoup(block.content,'html.parser');node=soup.find()
            if not node:continue
            current=str(node.get('style',''))
            mapping=doc.metadata.get('fontMapping',{})
            override=mapping.get('*')
            if not override:
                for name,target in mapping.items():
                    if any(re.sub(r'^[A-Z]{6}\+','',font['sourceFont']).casefold()==name.casefold() for font in fonts):override=target;break
            defaults=f'font-family: {FONT_STACKS[family]}; '
            if block.blockType in ('paragraph','list','blockquote','caption','table'):defaults+=f'font-size: {body:.3f}em; line-height: 1.65; '
            node['style']=clean_style(defaults+current+(f'; font-family: {FONT_STACKS[override]}' if override else ''))
            block.content=str(soup)
        doc.metadata['typographyVersion']=1
        doc.metadata['formattingLimitations']=['Unicode fallback fonts replace legacy PDF encodings; exact glyph metrics may differ.','OCR colors, complex text boxes and column boundaries require visual review.']
    return doc
