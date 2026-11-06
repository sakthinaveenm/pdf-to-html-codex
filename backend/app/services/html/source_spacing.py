"""Preserve source line indents and measured gaps without altering Unicode text."""
import re
from bs4 import BeautifulSoup,NavigableString
from app.services.html.font_metrics import advance_width


def _measure(node,size,weight,italic,stretch):
    if isinstance(node,NavigableString):return advance_width(str(node),size,weight,italic,stretch)
    style=str(node.get('style',''));match=re.search(r'font-size:\s*([\d.]+)em',style)
    if match:size*=float(match[1])
    if node.name in ('strong','b'):weight=700
    if node.name in ('em','i'):italic=True
    values=[_measure(child,size,weight,italic,stretch) for child in node.children]
    return None if any(value is None for value in values) else sum(values)


def spaced_line(markup,line,x0,x1,size,weight,italic,stretch,align='left'):
    soup=BeautifulSoup(markup,'html.parser');text=soup.get_text();spaces=text.count(' ')
    measured=_measure(soup,size,weight,italic,stretch)
    start=min(word['x0'] for word in line);end=max(word['x1'] for word in line)
    word_spacing=0
    if spaces and measured is not None:
        space=advance_width(' ',size,weight,italic,stretch) or size*.25
        word_spacing=max(-space*.5,min(size*.8,(end-start-measured)/spaces))
    if spaces>len(line)-1:word_spacing=max(0,word_spacing)
    indent=max(0,min(90,(start-x0)/(x1-x0)*100)) if align not in ('center','right') else 0
    width=max(1,min(100,100-indent))
    span=soup.new_tag('span')
    span['style']=f'display: inline-block; width: {width:.4f}%; margin-left: {indent:.4f}%; word-spacing: {word_spacing/16:.5f}rem; text-align: {align if align in ("center","right") else "left"}'
    for child in list(soup.contents):span.append(child)
    return str(span)
