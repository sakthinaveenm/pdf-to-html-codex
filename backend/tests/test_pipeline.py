import io
import os
import json
import time
import zipfile
from pathlib import Path
import pytest
from reportlab.pdfgen.canvas import Canvas
from pypdf import PdfReader, PdfWriter
from app.schemas.document import Document, Options, Highlight
from app.services.pdf_inspector.service import PDFInspectionService
from app.services.converters.lightweight import LightweightConverter
from app.services.html.service import HTMLGenerationService, HTMLNormalizationService, document_text, sanitize
from app.services.annotations.service import resolve
from app.services.ocr.service import OCRService

ROOT=Path(__file__).resolve().parents[2]
def make_pdf(text='Hello selectable world',pages=1,font=None):
    stream=io.BytesIO(); canvas=Canvas(stream)
    if font: canvas.setFont(font,16)
    for _ in range(pages):
        canvas.drawString(60,750,text); canvas.showPage()
    canvas.save();return stream.getvalue()

def wait(client,identity):
    for _ in range(200):
        job=client.get(f'/api/v1/jobs/{identity}').json()
        if job['status'] in ('COMPLETED','FAILED','CANCELED'): return job
        time.sleep(.1)
    pytest.fail(f'Job did not finish: {job}')

def test_real_batch_revision_annotations_export(client):
    result=client.post('/api/v1/jobs',files=[('files',('one.pdf',make_pdf(),'application/pdf')),('files',('two.pdf',make_pdf('Second independent document'),'application/pdf'))],data={'options':'{"engine":"LIGHTWEIGHT"}'})
    assert result.status_code==201,result.text
    ids=[r['job']['id'] for r in result.json()['results']];assert len(set(ids))==2
    for identity in ids: assert wait(client,identity)['status']=='COMPLETED'
    identity=ids[0]; prefix=f'/api/v1/documents/{identity}'
    doc=client.get(prefix+'/ast').json(); assert 'Hello selectable world' in client.get(prefix+'/html').text
    block=doc['blocks'][0]
    highlight={'id':'test-anchor','documentId':identity,'revision':1,'blockIds':[block['blockId']], 'quote':{'exact':'selectable','prefix':'Hello ','suffix':' world'},'position':{'start':6,'end':16,'unit':'unicode-codepoint'},'color':'#ffdf70'}
    assert client.post(prefix+'/highlights',json=highlight).status_code==201
    assert client.patch(prefix+'/highlights/test-anchor',json={'color':'#aabbcc'}).status_code==200
    changed=block['content'].replace('Hello','Welcome Hello')
    changed=changed.replace('<p>',f'<p data-block-id="{block["blockId"]}">')
    saved=client.put(prefix+'/revisions',json={'baseRevision':1,'html':changed}); assert saved.status_code==200,saved.text
    assert saved.json()['revision']==2
    anchors=client.get(prefix+'/highlights').json(); assert anchors[0]['position']['start']==14
    assert client.put(prefix+'/revisions',json={'baseRevision':1,'html':changed}).status_code==409
    export=client.get(prefix+'/export'); assert export.status_code==200
    with zipfile.ZipFile(io.BytesIO(export.content)) as archive:
        assert 'Welcome Hello' in archive.read('document.html').decode()
        assert {'document.json','highlights.json','reader.css','reader.js'}<=set(archive.namelist())
        assert 'localhost' not in archive.read('document.html').decode()
    assert client.delete(prefix+'/highlights/test-anchor').status_code==204
    assert client.get(prefix+'/assets/../../jobs.sqlite').status_code==404

@pytest.mark.parametrize('payload,name,mime',[(b'garbage','bad.pdf','application/pdf'),(b'%PDF-hi','bad.txt','text/plain'),(b'','empty.pdf','application/pdf')])
def test_upload_validation(client,payload,name,mime):
    response=client.post('/api/v1/jobs',files={'files':(name,payload,mime)})
    assert 'error' in response.json()['results'][0]

def test_corrupt_and_encrypted(client):
    writer=PdfWriter();writer.add_page(PdfReader(io.BytesIO(make_pdf())).pages[0]);writer.encrypt('secret');stream=io.BytesIO();writer.write(stream)
    for raw in [b'%PDF-1.4\ncorrupt',stream.getvalue()]:
        result=client.post('/api/v1/jobs',files={'files':('bad.pdf',raw,'application/pdf')},data={'options':'{"engine":"LIGHTWEIGHT"}'})
        job=wait(client,result.json()['results'][0]['job']['id']);assert job['status']=='FAILED';assert job['error']

def test_sanitizer_preserves_unicode_and_tables():
    result=sanitize('<script>alert(1)</script><p onclick="evil()">தமிழ் क्‍ष 😀 <strong>bold</strong></p><img src="https://evil/x"><a href="javascript:alert(1)">x</a><table><tr><td colspan="2">Cell</td></tr></table>')
    assert '<script' not in result and 'onclick' not in result and 'javascript:' not in result and '<img' not in result
    assert 'தமிழ் क्‍ष 😀' in result and 'colspan="2"' in result

def test_stable_blocks_and_rtl():
    service=HTMLNormalizationService();source='<h1>عنوان</h1><p>தமிழ் <em>English</em></p><table><tr><td rowspan="2">A</td></tr></table>'
    one=service.blocks(source,'id',1,'test');two=service.blocks(source,'id',1,'test')
    assert [b.blockId for b in one]==[b.blockId for b in two]
    assert one[0].direction=='rtl';assert one[2].blockType=='table'
    doc=Document(documentId='id',sourceFileName='test.pdf',sourceChecksum='a',title='test',blocks=one)
    html=HTMLGenerationService().generate(doc);assert 'data-page="1"' in html and '<canvas' not in html

def test_ambiguous_reanchoring():
    doc=Document(documentId='id',sourceFileName='x',sourceChecksum='a',title='x',revision=2,blocks=HTMLNormalizationService().blocks('<p>word word</p>','id',1,'test'))
    a=Highlight(id='a',documentId='id',revision=1,blockIds=['b'],quote={'exact':'word'},position={'start':0,'end':4})
    assert resolve(a,doc).status=='unresolved'

@pytest.mark.parametrize('text',['தமிழ் மொழி','हिन्दी भाषा','తెలుగు భాష','മലയാളം ഭാഷ','தமிழ் English','مرحبا بالعالم','中文文本'])
def test_multilingual_digital(tmp_path,text):
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    font=Path(os.environ.get('FONT_PATH','/System/Library/Fonts/Supplemental/Arial Unicode.ttf'))
    if not font.exists(): pytest.skip('Generated multilingual PDF fixture needs FONT_PATH pointing to a Unicode TrueType font; macOS Arial Unicode is unavailable.')
    pdfmetrics.registerFont(TTFont('UnicodeTest',str(font)))
    path=tmp_path/'language.pdf';path.write_bytes(make_pdf(text,font='UnicodeTest'))
    report=PDFInspectionService().inspect(path)
    doc=Document(documentId='test',sourceFileName='language.pdf',sourceChecksum='x',title='Language',pages=report['pages'])
    (tmp_path/'assets').mkdir()
    result=LightweightConverter().convert(path,doc,Options(),tmp_path)
    assert text.replace(' ','') in document_text(result).replace(' ','')

@pytest.mark.parametrize('language',['eng','tam'])
def test_scanned_ocr(tmp_path,language):
    from PIL import Image, ImageDraw, ImageFont
    from reportlab.lib.utils import ImageReader
    if language not in OCRService.languages(): pytest.skip(f'Tesseract {language} pack is not installed.')
    path=Path(os.environ.get('FONT_PATH','/System/Library/Fonts/Supplemental/Arial Unicode.ttf'))
    if not path.exists(): pytest.skip('Unicode fixture font unavailable.')
    text='Real scanned English text' if language=='eng' else 'தமிழ் மொழி'
    image=Image.new('RGB',(1500,350),'white');ImageDraw.Draw(image).text((40,70),text,font=ImageFont.truetype(str(path),72),fill='black')
    pdf=tmp_path/'scan.pdf';canvas=Canvas(str(pdf),pagesize=(750,175));canvas.drawImage(ImageReader(image),0,0,750,175);canvas.save()
    report=PDFInspectionService().inspect(pdf);assert report['pages'][0]['classification']=='SCANNED_IMAGE'
    doc=Document(documentId='scan',sourceFileName='scan.pdf',sourceChecksum='x',title='Scan',pages=report['pages'])
    (tmp_path/'assets').mkdir()
    converted=LightweightConverter().convert(pdf,doc,Options(languages=[language]),tmp_path)
    actual=document_text(converted)
    assert ('scanned' in actual) if language=='eng' else ('தமிழ்' in actual)
    assert converted.pages[0]['textSource']=='ocr'

def test_large_multipage_and_tables(tmp_path):
    path=tmp_path/'large.pdf';path.write_bytes(make_pdf(pages=50));report=PDFInspectionService().inspect(path);assert report['pageCount']==50
    canvas=Canvas(str(tmp_path/'table.pdf'));canvas.grid([50,150,250],[600,630,660]);canvas.drawString(60,640,'Name');canvas.drawString(160,640,'Value');canvas.drawString(60,610,'Sample');canvas.drawString(160,610,'42');canvas.save()
    report=PDFInspectionService().inspect(tmp_path/'table.pdf');doc=Document(documentId='table',sourceFileName='table.pdf',sourceChecksum='x',title='Table',pages=report['pages']);(tmp_path/'assets').mkdir()
    result=LightweightConverter().convert(tmp_path/'table.pdf',doc,Options(),tmp_path)
    assert any(b.blockType=='table' and '42' in b.content for b in result.blocks)

@pytest.mark.parametrize('platform',['Android WebView','iOS WKWebView'])
def test_native_mobile(platform):
    pytest.skip(f'{platform} runtime is unavailable on this host. Browser reader tests cover bridge logic; run reader/examples on a device.')
