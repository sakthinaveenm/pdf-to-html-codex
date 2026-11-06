"""Fit Unicode fallback glyph ink to PDF ink boxes using real HarfBuzz shaping."""
from functools import lru_cache
from io import BytesIO
import re
import statistics
from fontTools.ttLib import TTFont
import uharfbuzz as hb
from app.services.html.typography import FONT_DIR


@lru_cache(maxsize=8)
def _font_data(name):
    font=TTFont(FONT_DIR/name);font.flavor=None;buffer=BytesIO();font.save(buffer);font.close();return buffer.getvalue()


@lru_cache(maxsize=8192)
def ink_metrics(text,weight=400,italic=False):
    if re.search('[\u0900-\u097f]',text):name='noto-serif-devanagari.woff2'
    elif re.search('[\u0b80-\u0bff]',text):name='noto-serif-tamil.woff2'
    elif text.isascii():name='noto-serif-italic.woff2' if italic else 'noto-serif.woff2'
    else:return None
    face=hb.Face(_font_data(name));font=hb.Font(face);font.scale=(face.upem,face.upem);font.set_variations({'wght':weight,'wdth':100})
    buffer=hb.Buffer();buffer.add_str(text);buffer.guess_segment_properties();hb.shape(font,buffer)
    xs=[];ys=[];x=0;y=0
    for info,position in zip(buffer.glyph_infos,buffer.glyph_positions):
        if info.codepoint==0:return None
        extent=font.get_glyph_extents(info.codepoint)
        if extent and extent.width and extent.height:
            left=x+position.x_offset+extent.x_bearing;upper=y+position.y_offset+extent.y_bearing
            xs.extend((left,left+extent.width));ys.extend((upper,upper+extent.height))
        x+=position.x_advance;y+=position.y_advance
    if not xs or not ys:return None
    return (max(xs)-min(xs))/face.upem,(max(ys)-min(ys))/face.upem


def fit_fallback(region,nominal_size,weight=400,italic=False):
    samples=[]
    for line in region.lines:
        for word in line:
            value=word['text']
            if len(value)<2 or float(word.get('confidence',100))<50:continue
            if not re.search('[\u0900-\u097f\u0b80-\u0bff]',value):continue
            metrics=ink_metrics(value,weight,italic)
            partial=False
            if not metrics:
                # Latin digits in an Indic OCR token use another fallback font.
                # Its Indic run still provides a useful ink-height measurement.
                runs=re.findall('[\u0900-\u097f]+|[\u0b80-\u0bff]+',value)
                if runs:metrics=ink_metrics(max(runs,key=len),weight,italic);partial=True
            if not metrics:continue
            width,height=metrics;size=(word['bottom']-word['top'])/height
            if nominal_size*.5<=size<=nominal_size*1.2:
                stretch=100 if partial else (word['x1']-word['x0'])/(width*size)*100
                samples.append((size,stretch))
    if not samples:return nominal_size,100
    size=statistics.median(value[0] for value in samples)
    stretch=max(62.5,min(100,statistics.median(value[1] for value in samples)))
    return size,stretch


@lru_cache(maxsize=8192)
def _advance_units(text,weight,italic,stretch):
    if re.search('[\u0900-\u097f]',text):name='noto-serif-devanagari.woff2'
    elif re.search('[\u0b80-\u0bff]',text):name='noto-serif-tamil.woff2'
    elif text.isascii():name='noto-serif-italic.woff2' if italic else 'noto-serif.woff2'
    else:return None
    face=hb.Face(_font_data(name));font=hb.Font(face);font.scale=(face.upem,face.upem);font.set_variations({'wght':weight,'wdth':stretch})
    buffer=hb.Buffer();buffer.add_str(text);buffer.guess_segment_properties();hb.shape(font,buffer)
    if any(info.codepoint==0 for info in buffer.glyph_infos):return None
    return sum(position.x_advance for position in buffer.glyph_positions)/face.upem


def advance_width(text,size,weight=400,italic=False,stretch=100):
    # Browser fallback selects the Latin font for spaces/punctuation and the Indic
    # font for its script. Shape those runs separately, including combining marks.
    runs=re.findall(r'[\u0900-\u097f\u200c\u200d]+|[\u0b80-\u0bff\u200c\u200d]+|[^\u0900-\u097f\u0b80-\u0bff\u200c\u200d]+',text)
    total=0
    for run in runs:
        value=_advance_units(run,weight,italic,round(stretch,2))
        if value is None:return None
        total+=value*size
    return total
