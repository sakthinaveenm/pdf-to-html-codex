"""Turn Tesseract's real word boxes into flowing, styled semantic blocks."""
import csv
import html
import io
import statistics
import re
import unicodedata
from collections import OrderedDict,Counter
from dataclasses import dataclass
from app.services.html.typography import FONT_STACKS

def is_legacy_font(font: str) -> bool:
    return bool(re.search('chanakya|krutidev|devlys|bamini|suntommy',font,re.I))


def is_literal_bullet(char: dict) -> bool:
    return char['text']=='•' and not is_legacy_font(char['fontname'])


@dataclass
class OCRTextRegion:
    text: str
    bbox: tuple[float,float,float,float]
    lines: list[list[dict]]


def parse_tsv(source: str, scale: float) -> list[OCRTextRegion]:
    groups=OrderedDict()
    for row in csv.DictReader(io.StringIO(source),delimiter='\t'):
        if row.get('level')!='5' or not row.get('text','').strip():continue
        key=(row['block_num'],row['par_num'])
        word={'text':row['text'],'confidence':float(row.get('conf',-1)),'x0':int(row['left'])/scale,'top':int(row['top'])/scale,'x1':(int(row['left'])+int(row['width']))/scale,'bottom':(int(row['top'])+int(row['height']))/scale,'line':row['line_num']}
        groups.setdefault(key,[]).append(word)
    regions=[]
    for words in groups.values():
        lines=OrderedDict()
        for word in words:lines.setdefault(word['line'],[]).append(word)
        bbox=(min(w['x0'] for w in words),min(w['top'] for w in words),max(w['x1'] for w in words),max(w['bottom'] for w in words))
        regions.append(OCRTextRegion(' '.join(w['text'] for w in words),bbox,list(lines.values())))
    return regions


def align_regions_to_page(regions: list[OCRTextRegion],page) -> list[OCRTextRegion]:
    # PDFium renders CropBox coordinates; pdfplumber reports MediaBox coordinates.
    # Keeping these coordinate systems aligned is essential for matching native fonts.
    crop=page.cropbox or page.bbox
    dx=max(page.bbox[0],crop[0]);dy=max(page.bbox[1],crop[1])
    result=[]
    for region in regions:
        x0,top,x1,bottom=region.bbox
        lines=[[{**word,'x0':word['x0']+dx,'x1':word['x1']+dx,'top':word['top']+dy,'bottom':word['bottom']+dy} for word in line] for line in region.lines]
        result.append(OCRTextRegion(region.text,(x0+dx,top+dy,x1+dx,bottom+dy),lines))
    return result


def family_for_font(font: str) -> str:
    name=font.lower()
    if any(value in name for value in ('courier','mono','consolas')):return 'monospace'
    if any(value in name for value in ('helvetica','arial','sans','calibri')):return 'sans-serif'
    return 'serif'


def region_markup(region: OCRTextRegion, page, *, cover: bool, previous_bottom: float | None=None) -> str:
    x0,top,x1,bottom=region.bbox
    chars=[c for c in page.chars if x0-3<=(c['x0']+c['x1'])/2<=x1+3 and top-5<=(c['top']+c['bottom'])/2<=bottom+5]
    sizes=[float(c['size']) for c in chars if c.get('size',0)>0]
    font_size=statistics.median(sizes) if sizes else statistics.median(max(w['bottom']-w['top'] for w in line) for line in region.lines)*1.3
    font=Counter(str(char['fontname']) for char in chars).most_common(1)[0][0] if chars else ''
    bold='bold' in font.lower() or (cover and font_size>=22)
    italic=any(term in font.lower() for term in ('italic','oblique'))
    align='center' if cover or (abs((x0+x1)/2-page.width/2)<page.width*.055 and x1-x0<page.width*.75) else 'right' if page.width-x1<page.width*.08 and x0>page.width*.45 else 'left'
    tag='h1' if font_size>=36 else 'h2' if font_size>=22 else 'h3' if font_size>=17 and bold else 'p'
    em=max(.625 if cover else .875,min(4.5,font_size/16))
    gap=max(0,top-(previous_bottom if previous_bottom is not None else max(page.bbox[1],(page.cropbox or page.bbox)[1])+24))
    margin=min(10 if previous_bottom is None else 8,gap/16) if cover else .7
    style=f'text-align: {align}; font-family: {FONT_STACKS[family_for_font(font)]}; font-size: {em:.3f}em; font-weight: {700 if bold else 400}; font-style: {"italic" if italic else "normal"}; line-height: {1.2 if tag!="p" else 1.5 if cover else 1.65}; margin-block-start: {margin:.3f}rem; margin-block-end: 0rem'
    if chars:
        color=max(chars,key=lambda char:float(char.get('size',0))).get('non_stroking_color')
        if isinstance(color,(int,float)):rgb=[color]*3
        elif isinstance(color,(tuple,list)) and len(color)==3:rgb=list(color)
        elif isinstance(color,(tuple,list)) and len(color)==4:
            c,m,y,k=color;rgb=[(1-c)*(1-k),(1-m)*(1-k),(1-y)*(1-k)]
        else:rgb=None
        if rgb is not None:
            style+='; color: #'+''.join(f'{round(max(0,min(1,float(channel)))*255):02x}' for channel in rgb)
    lines=[]
    for line in region.lines:
        output=[]
        for word in line:
            value=word['text']
            native=[c for c in page.chars if word['x0']-float(c.get('size',10))*.65<=(c['x0']+c['x1'])/2<=word['x1']+float(c.get('size',10))*.4 and word['top']-3<=(c['top']+c['bottom'])/2<=word['bottom']+3]
            unique=[]
            for char in sorted(native,key=lambda c:(c['x0'],c['top'])):
                if not any(char['text']==old['text'] and abs(char['x0']-old['x0'])<.8 and abs(char['top']-old['top'])<.8 for old in unique):unique.append(char)
            digits=''.join(c['text'] for c in sorted(unique,key=lambda c:c['x0'])).strip()
            numeric_token=any(c.isdigit() for c in value) and not any(c.isalpha() and c not in 'iIlOo' for c in value)
            if numeric_token and any(c.isdigit() for c in digits) and re.fullmatch(r'[0-9.,:/()%+\-– ]+',digits):value=digits
            if numeric_token:
                candidates=[]
                for candidate in getattr(page,'_folio_numeric_words',[]):
                    overlap=max(0,min(word['x1'],candidate['x1'])-max(word['x0'],candidate['x0']))
                    vertical=max(0,min(word['bottom'],candidate['bottom'])-max(word['top'],candidate['top']))
                    if overlap>min(word['x1']-word['x0'],candidate['x1']-candidate['x0'])*.35 and vertical>0:
                        candidates.append((overlap,candidate))
                if candidates:value=max(candidates,key=lambda pair:pair[0])[1]['text']
            latin=[]
            for candidate in getattr(page,'_folio_latin_words',[]):
                overlap=max(0,min(word['x1'],candidate['x1'])-max(word['x0'],candidate['x0']))
                if overlap>min(word['x1']-word['x0'],candidate['x1']-candidate['x0'])*.6 and min(word['bottom'],candidate['bottom'])>max(word['top'],candidate['top']):latin.append((overlap,candidate))
            if latin:value=max(latin,key=lambda pair:pair[0])[1]['text']
            for symbol in ('•','©','®','₹','€','£','±','×','÷'):
                if any(char['text']==symbol and not is_legacy_font(char['fontname']) for char in native):value=symbol;break
            if any('wingdings' in char['fontname'].lower() and char['text']=='q' for char in native):value='□'
            suffix=re.search(r'([0-9०-९]+)([,.;:]?)$',value)
            if suffix and suffix.start()>0:
                prefix=value[:suffix.start()]
                number=''.join(str(unicodedata.decimal(char)) for char in suffix[1])
                if any(char.isalpha() for char in prefix):
                    fragments=[candidate for candidate in getattr(page,'_folio_numeric_fragments',[]) if candidate['x0']>word['x0']+(word['x1']-word['x0'])*.35 and candidate['x0']<word['x1']+2 and candidate['x1']>word['x1']-4 and min(candidate['bottom'],word['bottom'])>max(candidate['top'],word['top'])]
                    if fragments:
                        candidate=min(fragments,key=lambda item:abs(item['x1']-word['x1']))
                        number=candidate['text'];value=prefix+number+suffix[2]
                if any(char.isalpha() for char in prefix) and not prefix.endswith(('-', '–', '/', ':')):
                    for candidate in getattr(page,'_folio_numeric_words',[]):
                        if candidate['text'].rstrip(',.;:')!=number or not word['x0']<candidate['x0']<word['x1']:continue
                        if not min(word['bottom'],candidate['bottom'])>max(word['top'],candidate['top']):continue
                        if any(char['text'].isspace() and word['x0']<char['x0']<candidate['x0'] and abs(char['x1']-candidate['x0'])<2 and min(char['bottom'],word['bottom'])>max(char['top'],word['top']) for char in page.chars):
                            value=prefix.rstrip()+' '+number+suffix[2];break
            escaped=html.escape(value)
            if native:
                word_font=Counter(str(char['fontname']).lower() for char in native).most_common(1)[0][0]
                if 'bold' in word_font and not bold:escaped='<strong>'+escaped+'</strong>'
                if any(term in word_font for term in ('italic','oblique')) and not italic:escaped='<em>'+escaped+'</em>'
            if native:
                word_size=statistics.median(float(char['size']) for char in native)
                ratio=word_size/font_size
                if abs(ratio-1)>.08:escaped=f'<span style="font-size: {max(.25,min(6,ratio)):.4f}em">{escaped}</span>'
            output.append(escaped)
        lines.append(' '.join(output))
    content=('<br>' if cover else ' ').join(lines)
    return f'<{tag} style="{html.escape(style,quote=True)}">{content}</{tag}>'
