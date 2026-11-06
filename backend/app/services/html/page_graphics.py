"""Separate PDF graphics from selectable text; retain original graphics opacity."""
from pathlib import Path
from pypdf import PdfReader,PdfWriter
from pypdf.generic import ContentStream,DecodedStreamObject
import pypdfium2 as pdfium
from PIL import ImageStat


def _rewrite(owner,writer,*,text=False,decorations=None,seen=None,paint=False):
    seen=seen if seen is not None else {}
    resources=owner.get('/Resources',{})
    resources=resources.get_object() if hasattr(resources,'get_object') else resources
    xobjects=resources.get('/XObject',{})
    for key,reference in list(xobjects.items()):
        obj=reference.get_object()
        identity=getattr(reference,'idnum',id(obj))
        if obj.get('/Subtype')=='/Form':
            if identity in seen:
                xobjects[key]=seen[identity];continue
            seen[identity]=reference
            rewritten=_rewrite(obj,writer,text=text,decorations=decorations,seen=seen,paint=paint)
            rewritten_ref=writer._add_object(rewritten)
            seen[identity]=rewritten_ref;xobjects[key]=rewritten_ref
    stream=owner.get_contents() if hasattr(owner,'get_contents') else owner
    if stream is None:return owner
    content=ContentStream(stream,writer)
    operations=[]
    for args,operator in content.operations:
        if paint and operator in (b'S',b's',b'f',b'F',b'f*',b'B',b'B*',b'b',b'b*'):
            operations.append(([],b'n'));continue
        if text and operator in (b'Tj',b'TJ',b"'",b'"'):continue
        if decorations and operator==b'Do':
            reference=xobjects.get(args[0])
            if reference is not None and getattr(reference,'idnum',None) in decorations:continue
        operations.append((args,operator))
    content.operations=operations
    if hasattr(owner,'replace_contents'):owner.replace_contents(content)
    else:
        decoded=DecodedStreamObject()
        decoded.update({key:value for key,value in owner.items() if key not in ('/Filter','/DecodeParms','/Length')})
        decoded.set_data(content.get_data());return decoded
    return owner


def page_layers(source: Path,number: int,folder: Path,page,*,ocr_dpi=300):
    """Graphics-only PNG for output, and a watermark-free image for OCR.

    Text drawing commands are removed from the graphics layer at every Form depth.
    Only large, sparse transparent raster decorations are excluded from OCR.
    Foreground diagrams/images are retained; the original PDF is never modified.
    """
    folder.mkdir(parents=True,exist_ok=True);(folder/'assets').mkdir(exist_ok=True)
    reader=PdfReader(source)
    large_ids={getattr(image.get('stream'),'objid',None) for image in page.images if image['width']*image['height']>page.width*page.height*.2}
    decorations=set()
    for image in reader.pages[number-1].images:
        identity=image.indirect_reference.idnum if image.indirect_reference else None
        if identity not in large_ids or 'A' not in image.image.getbands():continue
        alpha=image.image.getchannel('A')
        if ImageStat.Stat(alpha).mean[0]<25:decorations.add(identity)
    # Match cloned object identities after translation rather than relying on original IDs.
    def render(name,remove_text=False,remove_decorations=False,scale=2,paint=False):
        writer=PdfWriter();writer.add_page(reader.pages[number-1]);target=writer.pages[0]
        translated={}
        if remove_decorations:
            for original_id in decorations:
                translated_id=writer._id_translated.get(id(reader),{}).get(original_id)
                if translated_id:translated[translated_id]=True
        _rewrite(target,writer,text=remove_text,decorations=set(translated),paint=paint)
        path=folder/(name+'.pdf')
        try:
            with path.open('wb') as output:writer.write(output)
            renderer=pdfium.PdfDocument(path)
            try:image=renderer[0].render(scale=scale).to_pil().copy()
            finally:renderer.close()
            return image
        finally:path.unlink(missing_ok=True);writer.close()
    try:
        background=render('_graphics',remove_text=True)
        try:
            name=f'page-{number}-graphics.png';background.save(folder/'assets'/name)
        finally:background.close()
        def dark(char):
            color=char.get('non_stroking_color',0)
            if color is None:return True
            if isinstance(color,(int,float)):return color<.6
            if len(color)==4:
                c,m,y,k=color;return max((1-c)*(1-k),(1-m)*(1-k),(1-y)*(1-k))<.6
            return max(color,default=0)<.6
        # Do not erase backgrounds behind white/light text. For dark-text pages,
        # graphics-free OCR avoids borders/rules being read as extra letters.
        clean=render('_ocr',remove_decorations=True,scale=ocr_dpi/72,paint=all(dark(char) for char in page.chars))
        return clean,{'assetId':name,'path':'assets/'+name,'sourcePage':number,'kind':'page-graphics-no-text'},bool(decorations)
    finally:reader.close()
