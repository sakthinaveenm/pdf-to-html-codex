"""Recover a flowing cover layout without embedding the cover as a screenshot."""
import html
from pathlib import Path
from pypdf import PdfReader
from PIL import ImageStat
from app.services.ocr.layout import region_markup


def is_title_page(page) -> bool:
    return len(page.chars)<250 and max((float(c.get('size',0)) for c in page.chars),default=0)>=28


def cover_html(page, regions, source: Path, output: Path, assets: list[dict]) -> str:
    placements=[]
    reader=PdfReader(source)
    try:
        native={image.indirect_reference.idnum:image.image for image in reader.pages[page.page_number-1].images if image.indirect_reference is not None}
        for index,image in enumerate(page.images):
            raster=native.get(getattr(image.get('stream'),'objid',None))
            if raster is None:continue
            rgba=raster.convert('RGBA');alpha=rgba.getchannel('A')
            if alpha.getbbox() is None:continue
            bbox=(image['x0'],image['top'],image['x1'],image['bottom'])
            area=(bbox[2]-bbox[0])*(bbox[3]-bbox[1])
            if area>page.width*page.height*.2 and ImageStat.Stat(alpha).mean[0]<50:continue
            # A full-cover raster is not a figure: editable OCR supplies its text.
            if area>page.width*page.height*.7:continue
            filename=f'cover-{page.page_number}-raster-{index}.png';rgba.save(output/'assets'/filename)
            assets.append({'assetId':filename,'path':'assets/'+filename,'sourcePage':page.page_number,'kind':'embedded-figure'})
            placements.append((bbox,'assets/'+filename))
    finally:reader.close()
    # Retain isolated vector logos. Large closed curves form the anchor; tiny
    # outlined text paths are supplied as OCR text instead of raster paragraphs.
    boxes=[]
    for curve in page.curves:
        box=(curve['x0'],curve['top'],curve['x1'],curve['bottom'])
        if not (12<box[2]-box[0]<page.width*.3 and 12<box[3]-box[1]<page.height*.15):continue
        merged=box;remaining=[]
        for previous in boxes:
            if merged[0]<=previous[2]+5 and merged[2]>=previous[0]-5 and merged[1]<=previous[3]+5 and merged[3]>=previous[1]-5:
                merged=(min(merged[0],previous[0]),min(merged[1],previous[1]),max(merged[2],previous[2]),max(merged[3],previous[3]))
            else:remaining.append(previous)
        boxes=remaining+[merged]
    for index,bbox in enumerate(boxes):
        if any(bbox[0]>=a and bbox[1]>=b and bbox[2]<=c and bbox[3]<=d for (a,b,c,d),_ in placements):continue
        bbox=(max(0,bbox[0]-4),max(0,bbox[1]-4),min(page.width,bbox[2]+4),min(page.height,bbox[3]+14))
        filename=f'cover-{page.page_number}-vector-{index}.png'
        page.crop(bbox).to_image(resolution=200).original.save(output/'assets'/filename)
        assets.append({'assetId':filename,'path':'assets/'+filename,'sourcePage':page.page_number,'kind':'vector-figure'})
        placements.append((bbox,'assets/'+filename))
    items=[]
    for region in regions:
        x0,top,x1,bottom=region.bbox
        # Do not duplicate QR/logotype labels already contained within a figure.
        if any(x0>=a-2 and top>=b-2 and x1<=c+2 and bottom<=d+2 for (a,b,c,d),_ in placements):continue
        items.append((region.bbox,'text',region))
    items.extend((bbox,'image',path) for bbox,path in placements)
    items.sort(key=lambda value:(value[0][1],value[0][0]))
    output_html=[];previous=None
    for bbox,kind,value in items:
        if kind=='text':output_html.append(region_markup(value,page,cover=True,previous_bottom=previous))
        else:
            width=min(page.width,bbox[2]-bbox[0]);gap=max(0,bbox[1]-(previous if previous is not None else max(page.bbox[1],(page.cropbox or page.bbox)[1])+24))
            style=f'text-align: center; margin-block-start: {min(8,gap/16):.3f}rem; margin-block-end: 0rem'
            output_html.append(f'<figure style="{style}"><img src="{html.escape(value,quote=True)}" alt="Figure from page {page.page_number}" style="width: {width/16:.3f}em"></figure>')
        previous=bbox[3]
    return ''.join(output_html)
