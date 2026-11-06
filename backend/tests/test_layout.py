import io
from pathlib import Path
from types import SimpleNamespace
from bs4 import BeautifulSoup
import pdfplumber
from pypdf import PdfReader,PdfWriter
from pypdf.generic import ContentStream
from reportlab.pdfgen.canvas import Canvas
from app.services.html.page_graphics import _rewrite,page_layers
from app.services.html.flow_layout import flowing_layout
from app.services.html.service import HTMLNormalizationService,HTMLGenerationService,sanitize
from app.services.export.pages import editor_snippet
from app.services.ocr.layout import OCRTextRegion
from app.schemas.document import Document


def fixture_pdf(tmp_path):
    path=tmp_path/'layout.pdf';canvas=Canvas(str(path),pagesize=(500,700))
    canvas.setFillColorRGB(.8,.8,.8);canvas.rect(30,100,440,550,fill=1,stroke=0)
    canvas.beginForm('nested');canvas.setFont('Helvetica',12);canvas.drawString(60,620,'Nested main text');canvas.endForm();canvas.doForm('nested')
    canvas.setFillColorRGB(0,0,0);canvas.setFont('Helvetica',12)
    for row in range(5):
        canvas.drawString(50,550-row*25,f'Left column {row}');canvas.drawString(280,550-row*25,f'Right column {row}')
    canvas.showPage();canvas.save();return path


def test_graphics_removes_text_in_nested_forms_and_keeps_shapes(tmp_path):
    source=fixture_pdf(tmp_path);reader=PdfReader(source);writer=PdfWriter();writer.add_page(reader.pages[0]);page=writer.pages[0]
    _rewrite(page,writer,text=True)
    def operators(owner):
        content=owner.get_contents() if hasattr(owner,'get_contents') else owner
        result=[op for _,op in ContentStream(content,writer).operations]
        for ref in owner.get('/Resources',{}).get('/XObject',{}).values():
            form=ref.get_object()
            if form.get('/Subtype')=='/Form':result.extend(operators(form))
        return result
    result=operators(page)
    assert b'Tj' not in result and b'TJ' not in result
    assert b're' in result
    with pdfplumber.open(source) as pdf:
        image,asset,_=page_layers(source,1,tmp_path/'output',pdf.pages[0]);image.close()
    assert (tmp_path/'output'/asset['path']).is_file()


def test_column_rows_and_background_are_portable_without_foreground_crops(tmp_path):
    source=fixture_pdf(tmp_path);folder=tmp_path/'output'
    with pdfplumber.open(source) as pdf:
        page=pdf.pages[0];regions=[]
        for word in page.extract_words():
            # A real source word box is enough to verify row/column grouping.
            regions.append(OCRTextRegion(word['text'],(word['x0'],word['top'],word['x1'],word['bottom']),[[{**word,'line':'1'}]]))
        markup,columns=flowing_layout(page,regions)
        assert columns and 'data-layout="columns"' in markup
        image,asset,_=page_layers(source,1,folder,page);image.close()
    blocks=HTMLNormalizationService().blocks(markup,'book',1,'test')
    doc=Document(documentId='book',sourceFileName='layout.pdf',sourceChecksum='x',title='x',pages=[{'page':1}],blocks=blocks,assets=[asset],metadata={'pageNumber':1,'pageBackground':{'path':asset['path'],'page':1,'height':700}})
    snippet=editor_snippet(doc,folder);soup=BeautifulSoup(snippet,'html.parser')
    images=soup.find_all('img');assert len(images)==1 and images[0]['data-layer']=='background'
    assert images[0]['src'].startswith('data:image/png;base64,')
    assert 'position: absolute' in images[0]['style']
    assert 'display: flow-root' in soup.section['style']
    assert soup.find('table')['data-layout']=='columns'
    assert all('border: 0' in cell.get('style','') for cell in soup.find_all('td'))
    assert 'Left' in soup.get_text() and 'Right' in soup.get_text()
    assert 'position: absolute' not in sanitize('<p style="position:absolute">Unsafe text positioning</p>')


def test_fallback_font_uses_glyph_ink_instead_of_nominal_em():
    from app.services.html.font_metrics import ink_metrics,fit_fallback
    text='पुनर्मुद्रण';width,height=ink_metrics(text,700)
    # Source legacy glyphs have a smaller ink box than a nominal 13pt Unicode font.
    word={'text':text,'confidence':95,'x0':20,'top':30,'x1':20+width*10.5,'bottom':30+height*10.5}
    region=OCRTextRegion(text,(word['x0'],word['top'],word['x1'],word['bottom']),[[word]])
    size,stretch=fit_fallback(region,13,700)
    assert abs(size-10.5)<.01 and stretch==100
    assert ink_metrics('தமிழ்') is not None
    assert ink_metrics('\U0010ffff') is None


def test_precision_noise_does_not_split_native_phone_numbers():
    from reportlab.pdfgen.canvas import Canvas
    # The index should ignore sub-pixel PDF float differences within the same font.
    class Page:
        width=500;bbox=(0,0,500,700);cropbox=None
        chars=[{'text':char,'x0':50+i*8,'x1':58+i*8,'top':50,'bottom':62,'size':12+(1e-10 if i%2 else 0),'fontname':'Helvetica'} for i,char in enumerate('011-26562708')]
        def dedupe_chars(self,**kw):return self
        def extract_words(self,**kw):
            assert len({char['size'] for char in self.chars})==1
            return [{'text':'011-26562708','fontname':'Helvetica','size':12,'x0':50,'x1':146,'top':50,'bottom':62}]
    page=Page();word={'text':'0-26562708','x0':50,'x1':146,'top':50,'bottom':62,'line':'1'}
    markup,_=flowing_layout(page,[OCRTextRegion(word['text'],(50,50,146,62),[[word]])])
    assert '011-26562708' in BeautifulSoup(markup,'html.parser').get_text()


def test_legacy_symbol_codes_do_not_replace_real_hindi_letters():
    from app.services.ocr.layout import region_markup
    # This legacy font encodes a Hindi glyph at the nominal ± code point.
    char={'text':'±','fontname':'Walkman-Chanakya905Normal','size':8,'x0':20,'x1':28,'top':30,'bottom':38}
    page=SimpleNamespace(chars=[char],width=500,bbox=(0,0,500,700),cropbox=None)
    word={'text':'रिकॉर्डिंग','x0':20,'x1':50,'top':30,'bottom':38,'line':'1'}
    output=region_markup(OCRTextRegion(word['text'],(20,30,50,38),[[word]]),page,cover=False)
    assert 'रिकॉर्डिंग' in BeautifulSoup(output,'html.parser').get_text()
    assert '±' not in BeautifulSoup(output,'html.parser').get_text()


def test_ocr_cleanup_removes_rules_without_removing_native_text(tmp_path):
    source=fixture_pdf(tmp_path);reader=PdfReader(source);writer=PdfWriter();writer.add_page(reader.pages[0]);page=writer.pages[0]
    _rewrite(page,writer,paint=True)
    operations=[op for _,op in ContentStream(page.get_contents(),writer).operations]
    assert b'f' not in operations and b'B' not in operations
    assert b'Tj' in operations
    assert 'Left column' in page.extract_text()
    assert any(op in (b'f',b'f*',b'B',b'B*') for _,op in ContentStream(reader.pages[0].get_contents(),reader).operations)


def test_legacy_bullet_code_preserves_sentence_words_and_real_bullets():
    from app.services.ocr.layout import region_markup,is_literal_bullet
    char={'text':'•','fontname':'Walkman-Chanakya905Normal','size':13,'x0':20,'x1':28,'top':30,'bottom':43}
    page=SimpleNamespace(chars=[char],width=500,bbox=(0,0,500,700),cropbox=None)
    for text in ['देखते','सीखने','रखा','सकते']:
        word={'text':text,'x0':20,'x1':50,'top':30,'bottom':43,'line':'1'}
        result=region_markup(OCRTextRegion(text,(20,30,50,43),[[word]]),page,cover=False)
        assert BeautifulSoup(result,'html.parser').get_text()==text
    assert not is_literal_bullet(char)
    assert is_literal_bullet({**char,'fontname':'TimesNewRoman'})


def test_numeric_recovery_does_not_replace_an_alphanumeric_word():
    from app.services.ocr.layout import region_markup
    page=SimpleNamespace(chars=[],width=500,bbox=(0,0,500,700),cropbox=None,_folio_numeric_words=[{'text':'19','x0':40,'x1':60,'top':30,'bottom':43}])
    word={'text':'कोविड-19','x0':20,'x1':60,'top':30,'bottom':43,'line':'1'}
    result=region_markup(OCRTextRegion(word['text'],(20,30,60,43),[[word]]),page,cover=False)
    assert 'कोविड-19' in BeautifulSoup(result,'html.parser').get_text()


def test_fused_date_uses_a_verified_source_space():
    from app.services.ocr.layout import region_markup
    chars=[{'text':' ','fontname':'Walkman-Chanakya905NormalItalic','size':13,'x0':40,'x1':45,'top':30,'bottom':43}]
    candidate={'text':'2006','x0':45,'x1':65,'top':30,'bottom':43}
    page=SimpleNamespace(chars=chars,width=500,bbox=(0,0,500,700),cropbox=None,_folio_numeric_words=[candidate])
    word={'text':'नवंबर2006','x0':20,'x1':65,'top':30,'bottom':43,'line':'1'}
    output=region_markup(OCRTextRegion(word['text'],(20,30,65,43),[[word]]),page,cover=False)
    assert BeautifulSoup(output,'html.parser').get_text()=='नवंबर 2006'


def test_source_spacing_keeps_unicode_and_adds_measured_word_gaps():
    from app.services.html.source_spacing import spaced_line
    words=[{'text':'Tamil','x0':30,'x1':70,'top':20,'bottom':32},{'text':'text','x0':100,'x1':130,'top':20,'bottom':32}]
    markup=spaced_line('Tamil <strong>text</strong>',words,20,150,12,400,False,100)
    soup=BeautifulSoup(sanitize(markup),'html.parser')
    assert soup.get_text()=='Tamil text'
    assert 'word-spacing:' in soup.span['style'] and 'inline-block' in soup.span['style']
    assert 'margin-left:' in soup.span['style']


def test_ordinary_page_signature_blocks_share_one_row_and_fit_margins(tmp_path):
    path=tmp_path/'signature.pdf';canvas=Canvas(str(path),pagesize=(500,700));canvas.setFont('Helvetica',12)
    canvas.drawString(60,600,'Body paragraph')
    canvas.drawString(60,520,'New Delhi');canvas.drawString(360,520,'Director')
    canvas.drawString(60,500,'20 November 2006');canvas.drawString(300,500,'Research Council')
    canvas.showPage();canvas.save()
    with pdfplumber.open(path) as pdf:
        page=pdf.pages[0];regions=[]
        for line in page.extract_text_lines(return_chars=True):
            # Split distant source fields into separate OCR regions, as on page 4.
            source_words=page.crop((0,line['top']-.1,500,line['bottom']+.1)).extract_words()
            groups=[]
            for word in source_words:
                if not groups or word['x0']-groups[-1][-1]['x1']>35:groups.append([])
                groups[-1].append({**word,'line':'1'})
            for words in groups:
                bbox=(min(w['x0'] for w in words),min(w['top'] for w in words),max(w['x1'] for w in words),max(w['bottom'] for w in words))
                regions.append(OCRTextRegion(' '.join(w['text'] for w in words),bbox,[words]))
        markup,columns=flowing_layout(page,regions)
    soup=BeautifulSoup(sanitize(markup),'html.parser');table=soup.find('table')
    assert not columns and table is not None
    assert 'New Delhi' in table.get_text() and 'Director' in table.get_text()
    import re
    widths=re.findall(r'(?<![-\w])width:\s*([\d.]+)%',table['style'])
    assert widths and float(widths[-1])<90


def test_mixed_hindi_token_recovers_native_number_without_losing_word():
    from app.services.ocr.layout import region_markup
    page=SimpleNamespace(chars=[],width=500,bbox=(0,0,500,700),cropbox=None,_folio_numeric_fragments=[{'text':'19','x0':45,'x1':60,'top':30,'bottom':43}])
    word={'text':'कोविड-9','x0':20,'x1':60,'top':30,'bottom':43,'line':'1'}
    result=region_markup(OCRTextRegion(word['text'],(20,30,60,43),[[word]]),page,cover=False)
    assert BeautifulSoup(result,'html.parser').get_text()=='कोविड-19'


def test_list_continuation_does_not_apply_source_indent_twice(tmp_path):
    path=tmp_path/'list.pdf';canvas=Canvas(str(path),pagesize=(500,700));canvas.setFont('Helvetica',12)
    canvas.drawString(50,600,'Body text establishes margins')
    canvas.drawString(80,500,'*');canvas.drawString(90,500,'First item')
    canvas.drawString(90,484,'continued words');canvas.save()
    with pdfplumber.open(path) as pdf:
        page=pdf.pages[0];groups={}
        # Simulate a correctly decoded Unicode bullet independent of host fonts.
        for char in page.chars:
            if char['text']=='*':char['text']='•'
        for word in page.extract_words():groups.setdefault(round(word['top']),[]).append({**word,'line':'1'})
        lines=list(groups.values());regions=[]
        for selected in [lines[:1],lines[1:]]:
            words=[word for line in selected for word in line];bbox=(min(w['x0'] for w in words),min(w['top'] for w in words),max(w['x1'] for w in words),max(w['bottom'] for w in words))
            regions.append(OCRTextRegion('',bbox,selected))
        markup,_=flowing_layout(page,regions)
    soup=BeautifulSoup(sanitize(markup),'html.parser');listing=soup.ul
    assert listing is not None and len(listing.find_all('li'))==1
    assert 'First item' in listing.get_text() and 'continued words' in listing.get_text()
    assert all('margin-left: 0.0000%' in span.get('style','') for span in listing.li.find_all('span',recursive=False))
    assert 'padding-left: 1em' not in listing['style']
