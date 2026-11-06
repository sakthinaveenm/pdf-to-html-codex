"""Source-derived flowing paragraphs and column groups; text stays editable DOM."""
import html
import statistics
from bs4 import BeautifulSoup
from app.services.ocr.layout import OCRTextRegion,region_markup,is_literal_bullet,is_legacy_font
from app.services.html.font_metrics import fit_fallback
from app.services.html.source_spacing import spaced_line


def _bbox(lines):
    words=[word for line in lines for word in line]
    return min(w['x0'] for w in words),min(w['top'] for w in words),max(w['x1'] for w in words),max(w['bottom'] for w in words)


def _parts(region):
    """Separate side-by-side labels that Tesseract joined into one line."""
    pieces=[]
    for line in region.lines:
        chunks=[];chunk=[]
        for word in line:
            if chunk and word['x0']-chunk[-1]['x1']>35:
                chunks.append(chunk);chunk=[]
            chunk.append(word)
        if chunk:chunks.append(chunk)
        pieces.append(chunks)
    if all(len(parts)==1 for parts in pieces):return [region]
    return [OCRTextRegion(' '.join(w['text'] for w in chunk),_bbox([chunk]),[chunk]) for parts in pieces for chunk in parts]


def flowing_layout(page,regions):
    import re
    native_page=page.dedupe_chars(tolerance=1)
    for char in native_page.chars:char['size']=round(float(char['size']),3)
    native_words=native_page.extract_words(extra_attrs=['fontname','size'])
    for word in native_words:
        if re.search('chanakya|krutidev|devlys',word['fontname'],re.I) and re.fullmatch(r'[0-9]+&[0-9]+',word['text']):word['text']=word['text'].replace('&','-')
        if re.search('chanakya|krutidev|devlys',word['fontname'],re.I) and re.fullmatch(r'[0-9]+\]',word['text']):word['text']=word['text'][:-1]+','
    fragments=[]
    for word in native_words:
        suffix=re.search(r'([0-9]+)[,.;:\]]?$',word['text'])
        if not is_legacy_font(word['fontname']) or not suffix or suffix.start()==0:continue
        digits=[char for char in native_page.chars if char['text'] in '0123456789' and word['x0']-.5<=char['x0']<=word['x1']+.5 and abs(char['top']-word['top'])<2]
        digits=sorted(digits,key=lambda char:char['x0'])[-len(suffix[1]):]
        if ''.join(char['text'] for char in digits)==suffix[1]:fragments.append({'text':suffix[1],'x0':digits[0]['x0'],'x1':digits[-1]['x1'],'top':min(char['top'] for char in digits),'bottom':max(char['bottom'] for char in digits)})
    page._folio_numeric_fragments=fragments
    page._folio_numeric_words=[word for word in native_words if re.fullmatch(r'[0-9][0-9.,:/()%+\-–]*',word['text'])]
    page._folio_latin_words=[word for word in native_words if not re.search('chanakya|krutidev|devlys|bamini|suntommy|wingdings',word['fontname'],re.I) and re.search('[A-Za-z]',word['text'])]
    crop=page.cropbox or page.bbox;left=max(page.bbox[0],crop[0]);top=max(page.bbox[1],crop[1]);width=min(page.bbox[2],crop[2])-left
    regions=[part for region in regions for part in _parts(region)]
    # Exclude artifacts unsupported by any source text. QR/logos live in graphics.
    def native(region):
        x0,y0,x1,y1=region.bbox
        return [char for char in page.chars if x0-3<=(char['x0']+char['x1'])/2<=x1+3 and y0-5<=(char['top']+char['bottom'])/2<=y1+5]
    mapped=[]
    for region in regions:
        lines=[line for line in region.lines if native(OCRTextRegion('',_bbox([line]),[line]))]
        if lines and any(char['text'].strip() and not is_literal_bullet(char) for char in native(region)):mapped.append(OCRTextRegion(' '.join(w['text'] for line in lines for w in line),_bbox(lines),lines))
    regions=mapped
    bullet_line_ids=set()
    for char in page.chars:
        if not is_literal_bullet(char):continue
        candidates=[]
        for region in regions:
            for line in region.lines:
                box=_bbox([line]);distance=abs((box[1]+box[3])/2-(char['top']+char['bottom'])/2)
                if char['x0']-5<=box[0]<=char['x0']+float(char['size'])*2 and distance<float(char['size'])*.8:candidates.append((distance,line))
        if candidates:bullet_line_ids.add(id(min(candidates,key=lambda pair:pair[0])[1]))
    def render(items,x0,x1,start,columns=False):
        result=[];previous=start
        ordered=sorted(items,key=lambda r:(r.bbox[1],r.bbox[0]));used=set()
        for region in ordered:
            if id(region) in used:continue
            parallel=[other for other in ordered if id(other) not in used and other is not region and min(other.bbox[3],region.bbox[3])-max(other.bbox[1],region.bbox[1])>1 and (other.bbox[0]>=region.bbox[2]-2 or other.bbox[2]<=region.bbox[0]+2)]
            if parallel:
                group=[region]+parallel
                while True:
                    more=[other for other in ordered if other not in group and id(other) not in used and any(min(other.bbox[3],member.bbox[3])-max(other.bbox[1],member.bbox[1])>1 and (other.bbox[0]>=member.bbox[2]-2 or other.bbox[2]<=member.bbox[0]+2) for member in group)]
                    if not more:break
                    group.extend(more)
                for member in group:used.add(id(member))
                starts=sorted(set(member.bbox[0] for member in group))
                cut=max(zip(starts,starts[1:]),key=lambda pair:pair[1]-pair[0]);cut=(cut[0]+cut[1])/2
                buckets=[[member for member in group if member.bbox[0]<cut],[member for member in group if member.bbox[0]>=cut]]
                cells=[];cursor=x0;y=min(item.bbox[1] for item in group)
                for bucket in buckets:
                    a=min(item.bbox[0] for item in bucket);b=max(item.bbox[2] for item in bucket)
                    if a>cursor:cells.append(f'<td style="width: {(a-cursor)/(x1-x0)*100:.3f}%; padding: 0; border: 0"></td>')
                    cells.append(f'<td style="width: {(b-a)/(x1-x0)*100:.3f}%; padding: 0; border: 0; vertical-align: top">{render(bucket,a,b,y,True)}</td>');cursor=b
                if cursor<x1:cells.append(f'<td style="width: {(x1-cursor)/(x1-x0)*100:.3f}%; padding: 0; border: 0"></td>')
                result.append(f'<table data-layout="columns" style="width: 100%; border: 0; border-collapse: collapse; table-layout: fixed; margin-block-start: {max(0,y-previous)/16:.4f}rem; margin-block-end: 0rem"><tbody><tr>{"".join(cells)}</tr></tbody></table>')
                previous=max(item.bbox[3] for item in group);continue
            chars=native(region);size=statistics.median(float(c['size']) for c in chars)
            soup=BeautifulSoup(region_markup(region,page,cover=False),'html.parser');node=soup.find()
            source_size=size
            font_name=statistics.mode(str(char['fontname']).lower() for char in chars)
            size,stretch=fit_fallback(region,source_size,700 if 'bold' in font_name else 400,any(term in font_name for term in ('italic','oblique')))
            # The nominal PDF em size is not the glyph's ink height in a fallback font.
            pitch=statistics.median([b[0]['top']-a[0]['top'] for a,b in zip(region.lines,region.lines[1:]) if b[0]['top']>a[0]['top']]) if len(region.lines)>1 else size*1.2
            leading=max(1,min(2.5,pitch/size));height=max(size*leading,len(region.lines)*size*leading)
            align='left'
            region_width=region.bbox[2]-region.bbox[0]
            if region_width<(x1-x0)*.85 and abs((region.bbox[0]+region.bbox[2])/2-(x0+x1)/2)<(x1-x0)*.08:align='center'
            elif region.bbox[0]>x0+(x1-x0)*.5 and x1-region.bbox[2]<15:align='right'
            elif len(region.lines)>2:align='justify'
            gap=max(0,region.bbox[1]-size*.15-previous)
            indent=max(0,(region.bbox[0]-x0)/(x1-x0)*100) if align=='left' else 0
            # Build list lines from the text after the real marker. Continuations
            # share that content origin instead of applying the indent twice.
            bullet_lines=[id(line) in bullet_line_ids for line in region.lines]
            prepared=[]
            for line,is_bullet in zip(region.lines,bullet_lines):
                one=OCRTextRegion('',_bbox([line]),[line])
                tree=BeautifulSoup(region_markup(one,page,cover=False),'html.parser').find()
                words=line
                if is_bullet:
                    first=next((value for value in tree.descendants if isinstance(value,str) and value.strip()),None)
                    if first is not None and re.match(r'^\s*(?:•|«)',str(first)):
                        first.replace_with(re.sub(r'^\s*(?:•|«)\s*','',str(first)))
                        if len(line)>1:words=line[1:]
                prepared.append((tree.decode_contents(),words))
            content_start=min(min(word['x0'] for word in words) for _,words in prepared) if any(bullet_lines) else x0
            lines=[spaced_line(markup,words,content_start,x1,size,700 if 'bold' in font_name else 400,any(term in font_name for term in ('italic','oblique')),stretch,'left' if any(bullet_lines) else align) for markup,words in prepared]
            node.clear()
            if any(bullet_lines):
                node.name='ul';item=None
                for value,is_bullet in zip(lines,bullet_lines):
                    if is_bullet or item is None:
                        item=soup.new_tag('li');node.append(item)
                    else:item.append(soup.new_tag('br'))
                    item.append(BeautifulSoup(value,'html.parser'))
            else:node.append(BeautifulSoup('<br>'.join(lines),'html.parser'))
            node['style']=str(node.get('style',''))+'; '+('white-space: nowrap; ' if columns else '')+f'; font-size: {max(.25,min(6,size/16)):.4f}em; font-stretch: {stretch:.2f}%; line-height: {leading:.4f}; text-align: {align}; margin-block-start: {gap/16:.4f}rem; margin-block-end: 0rem; margin-left: 0%; margin-right: 0%; position: relative; z-index: 1'
            if node.name=='ul':node['style']+=f'; padding-left: {max(0,(content_start-x0)/size):.4f}em; list-style-position: outside'
            result.append(str(node));previous=max(previous,region.bbox[1]-size*.15+height)
        return ''.join(result)
    # Detect sustained columns, rather than interpreting a centered title as a column.
    split=left+width*.5
    l=[r for r in regions if r.bbox[2]<split+8 and r.bbox[0]<split-width*.12]
    r=[r for r in regions if r.bbox[0]>split-8 and r.bbox[2]>split+width*.12]
    columnar=len(l)>=4 and len(r)>=4
    if columnar:
        l=[value for value in regions if value.bbox[2]<split+8 and value.bbox[0]<split-8]
        r=[value for value in regions if value.bbox[0]>split-8]
        body=l+r;begin=min(v.bbox[1] for v in body)
        before=[v for v in regions if v not in body and v.bbox[3]<begin]
        after=[v for v in regions if v not in body and v not in before]
        lx=min(v.bbox[0] for v in l);rx=min(v.bbox[0] for v in r)
        bound=max(v.bbox[2] for v in r);gutter=max(8,rx-max(v.bbox[2] for v in l))
        output=render(before,left,left+width,top)
        start=begin-top if not before else max(0,begin-max(v.bbox[3] for v in before))
        output+=f'<table data-layout="columns" style="width: {(bound-lx)/width*100:.3f}%; margin-left: {(lx-left)/width*100:.3f}%; margin-block-start: {start/16:.3f}rem; margin-block-end: 0rem; border: 0; border-collapse: collapse; table-layout: fixed; position: relative; z-index: 1"><tbody><tr><td style="width: {(rx-lx)/(bound-lx)*100:.3f}%; border: 0; padding: 0; vertical-align: top; padding-right: {gutter/16:.3f}rem">{render(l,lx,rx-gutter,begin,True)}</td><td style="border: 0; padding: 0; vertical-align: top">{render(r,rx,bound,begin,True)}</td></tr></tbody></table>'
        output+=render(after,left,left+width,max(v.bbox[3] for v in body))
        return output,True
    if max((float(char.get('size',0)) for char in page.chars),default=0)>28 and len(page.chars)<250:
        return render(regions,left+24,left+width-24,top),False
    content_left=min((v.bbox[0] for v in regions),default=left+24);content_right=max((v.bbox[2] for v in regions),default=left+width-24)
    output=render(regions,content_left,content_right,top)
    # Block margins retain the source content area while allowing narrow-screen wrapping.
    soup=BeautifulSoup(output,'html.parser')
    for node in soup.find_all(recursive=False):
        if node.name=='table':node['style']=str(node.get('style',''))+f'; width: {(content_right-content_left)/width*100:.4f}%'
        node['style']=str(node.get('style',''))+f'; margin-left: {(content_left-left)/width*100:.3f}%; margin-right: {(left+width-content_right)/width*100:.3f}%'
    return str(soup),False
