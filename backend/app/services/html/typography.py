"""A bounded typography vocabulary shared by semantic HTML and the editor."""
from functools import lru_cache
from pathlib import Path
import base64
import re

SERIF='"Folio Serif", "Folio Devanagari", "Folio Tamil", Georgia, "Nirmala UI", serif'
SANS='system-ui, "Noto Sans Devanagari", "Nirmala UI", sans-serif'
MONO='ui-monospace, SFMono-Regular, Consolas, monospace'
FONT_STACKS={'serif':SERIF,'sans-serif':SANS,'monospace':MONO}
FONT_DIR=Path(__file__).resolve().parents[2]/'resources'/'fonts'


def clean_style(style: str) -> str:
    result=[]
    for declaration in style.split(';'):
        if ':' not in declaration:continue
        prop,value=(part.strip() for part in declaration.split(':',1));prop=prop.lower()
        allowed=False
        if prop=='text-align':allowed=value in ('left','right','center','justify','start','end')
        elif prop=='font-family':
            value=FONT_STACKS.get(value,value)
            compact=lambda item: re.sub(r'\s*,\s*',',',item)
            value=next((stack for stack in FONT_STACKS.values() if compact(stack)==compact(value)),value)
            allowed=value in FONT_STACKS.values()
        elif prop=='font-size':
            match=re.fullmatch(r'(\d+(?:\.\d+)?)(em|px)',value)
            allowed=bool(match and (.25<=float(match[1])<=6 if match[2]=='em' else 8<=float(match[1])<=96))
        elif prop=='word-spacing':
            match=re.fullmatch(r'(-?\d+(?:\.\d+)?)rem',value);allowed=bool(match and -2<=float(match[1])<=4)
        elif prop=='font-weight':allowed=value in ('400','500','600','700','800','900','normal','bold')
        elif prop=='font-style':allowed=value in ('normal','italic','oblique')
        elif prop=='line-height':allowed=bool(re.fullmatch(r'\d+(?:\.\d+)?',value) and 1<=float(value)<=2.5)
        elif prop in ('margin-block-start','margin-block-end'):
            match=re.fullmatch(r'(\d+(?:\.\d+)?)rem',value);allowed=bool(match and 0<=float(match[1])<=100)
        elif prop in ('color','background-color','border-color'):
            allowed=bool(re.fullmatch(r'#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?',value))
        elif prop=='text-decoration':allowed=value in ('none','underline','line-through')
        elif prop=='text-indent':
            match=re.fullmatch(r'(\d+(?:\.\d+)?)em',value);allowed=bool(match and 0<=float(match[1])<=10)
        elif prop in ('position',):allowed=value=='relative'
        elif prop=='z-index':allowed=value in ('0','1')
        elif prop in ('top','left'):allowed=value=='0'
        elif prop=='pointer-events':allowed=value=='none'
        elif prop=='list-style-position':allowed=value in ('inside','outside')
        elif prop=='white-space':allowed=value in ('normal','nowrap')
        elif prop=='display':allowed=value in ('block','inline-block','table','flow-root')
        elif prop=='height':allowed=value=='auto'
        elif prop=='border':allowed=value=='0'
        elif prop=='border-collapse':allowed=value=='collapse'
        elif prop=='table-layout':allowed=value=='fixed'
        elif prop=='vertical-align':allowed=value=='top'
        elif prop=='font-stretch':allowed=bool(re.fullmatch(r'\d+(?:\.\d+)?%',value) and 62.5<=float(value[:-1])<=100)
        elif prop in ('padding','padding-right','padding-left','min-height'):
            match=re.fullmatch(r'(\d+(?:\.\d+)?)(rem|em)?',value);allowed=bool(match and 0<=float(match[1])<=100)
        elif prop in ('margin-left','margin-right') or (prop=='width' and value.endswith('%')):
            match=re.fullmatch(r'(\d+(?:\.\d+)?)%',value);allowed=bool(match and 0<=float(match[1])<=100)
        elif prop=='width':
            match=re.fullmatch(r'(\d+(?:\.\d+)?)em',value);allowed=bool(match and 0<float(match[1])<=60)
        if allowed:result.append(f'{prop}: {value}')
    return '; '.join(result)


@lru_cache(maxsize=1)
def font_faces() -> str:
    faces=['/* Bundled Noto fonts: SIL Open Font License 1.1.\n'+'\n'.join(path.read_text(encoding='utf-8').replace('*/','* /') for path in FONT_DIR.glob('*-OFL.txt'))+'\n*/']
    for filename,family,style in [('noto-serif.woff2','Folio Serif','normal'),('noto-serif-italic.woff2','Folio Serif','italic'),('noto-serif-devanagari.woff2','Folio Devanagari','normal'),('noto-serif-tamil.woff2','Folio Tamil','normal')]:
        path=FONT_DIR/filename
        if not path.is_file():continue
        encoded=base64.b64encode(path.read_bytes()).decode('ascii')
        faces.append(f'@font-face{{font-family:"{family}";font-style:{style};font-weight:100 900;font-stretch:62.5% 100%;font-display:swap;src:url(data:font/woff2;base64,{encoded}) format("woff2")}}')
    return ''.join(faces)

DOCUMENT_CSS=f'''.pdf-document{{box-sizing:border-box;max-width:900px;margin:0 auto;padding:24px;color:#202420;background:#fff;font-family:{SERIF};font-size:var(--reader-size,16px);line-height:1.65;overflow-wrap:anywhere;font-kerning:normal}}.pdf-document *{{box-sizing:border-box}}.pdf-document p{{margin:.7rem 0;unicode-bidi:plaintext}}.pdf-document h1,.pdf-document h2,.pdf-document h3,.pdf-document h4{{font-family:inherit;font-weight:700;line-height:1.25;margin:1.2rem 0 .6rem}}.pdf-document h1{{font-size:2.5em}}.pdf-document h2{{font-size:1.75em}}.pdf-document h3{{font-size:1.3em}}.pdf-document figure{{margin:1rem 0}}.pdf-document img{{max-width:100%;height:auto;display:block;margin-inline:auto}}.pdf-document figcaption{{font-size:.8em;text-align:center}}.pdf-document table{{border-collapse:collapse;max-width:100%;font-size:inherit}}.pdf-document th,.pdf-document td{{border:1px solid #ccd2cc;padding:.45em .65em;vertical-align:top}}.pdf-document pre{{overflow:auto;font-family:{MONO}}}.pdf-document blockquote{{border-inline-start:3px solid #d0d7d0;padding-inline-start:1em;margin-inline:0}}.pdf-document [data-page]{{scroll-margin-top:12px}}.pdf-document section{{margin:0 0 2rem}}.dark .pdf-document{{background:#172226;color:#e7ece9}}@media(max-width:600px){{.pdf-document{{padding:16px}}.pdf-document h1{{overflow-wrap:anywhere}}}}'''
