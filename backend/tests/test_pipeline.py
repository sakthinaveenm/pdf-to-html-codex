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

def test_one_html_per_pdf_contains_every_page_and_base64_images(client):
    from PIL import Image
    from reportlab.lib.utils import ImageReader
    from bs4 import BeautifulSoup
    import base64
    image=Image.new('RGB',(30,20),'green')
    stream=io.BytesIO();canvas=Canvas(stream)
    canvas.drawString(50,750,'First page text for editor')
    canvas.drawImage(ImageReader(image),50,600,90,60)
    canvas.showPage();canvas.drawString(50,750,'Second page text for editor');canvas.save()
    result=client.post('/api/v1/jobs',files={'files':('my-book.pdf',stream.getvalue(),'application/pdf')},data={'options':'{"engine":"LIGHTWEIGHT"}'})
    identity=result.json()['results'][0]['job']['id']
    assert wait(client,identity)['status']=='COMPLETED'
    endpoint=f'/api/v1/documents/{identity}'
    for response in [client.get(endpoint+'/html?fragment=true&standalone=true'),client.get(endpoint+'/export?format=html')]:
        assert response.status_code==200,response.text
        soup=BeautifulSoup(response.text,'html.parser')
        assert 'First page text for editor' in soup.get_text()
        assert 'Second page text for editor' in soup.get_text()
        assert len(soup.select('section[data-page]'))==2
        images=soup.find_all('img');assert len(images)==1
        uri=images[0]['src'];assert uri.startswith('data:image/png;base64,')
        raw=base64.b64decode(uri.split(',',1)[1],validate=True)
        with Image.open(io.BytesIO(raw)) as restored:assert restored.format=='PNG'
        assert '<script' not in response.text and 'localhost' not in response.text
    assert 'my-book.html' in client.get(endpoint+'/export?format=html').headers['content-disposition']
    # The editor/reader's canonical representation still uses safe relative assets.
    assert 'src="assets/' in client.get(endpoint+'/html?fragment=true').text
    assert 'data:image/' not in client.get(endpoint+'/html?fragment=true').text


def test_portable_export_refuses_unregistered_and_missing_assets(tmp_path):
    from app.services.export.standalone import standalone_html
    blocks=HTMLNormalizationService().blocks('<p>Text</p><figure><img src="assets/missing.png" alt="diagram"></figure>','test',1,'test')
    doc=Document(documentId='test',sourceFileName='x.pdf',sourceChecksum='x',title='x',blocks=blocks)
    with pytest.raises(ValueError,match='registered'):standalone_html(doc,tmp_path)
    doc.assets=[{'assetId':'missing.png','path':'assets/missing.png'}]
    with pytest.raises(ValueError,match='missing'):standalone_html(doc,tmp_path)

def test_base64_image_editor_revision_preserves_display_and_export(client):
    from PIL import Image
    from bs4 import BeautifulSoup
    from reportlab.lib.utils import ImageReader
    stream=io.BytesIO();canvas=Canvas(stream);canvas.drawString(50,750,'Image round trip');canvas.drawImage(ImageReader(Image.new('RGB',(20,20),'red')),50,600,50,50);canvas.save()
    response=client.post('/api/v1/jobs',files={'files':('figure.pdf',stream.getvalue(),'application/pdf')},data={'options':'{"engine":"LIGHTWEIGHT"}'})
    identity=response.json()['results'][0]['job']['id'];assert wait(client,identity)['status']=='COMPLETED'
    base=f'/api/v1/documents/{identity}'
    before=client.get(base+'/html?fragment=true&standalone=true').text
    before_src=BeautifulSoup(before,'html.parser').img['src']
    saved=client.put(base+'/revisions',json={'baseRevision':1,'html':before})
    assert saved.status_code==200,saved.text
    assert len(saved.json()['assets'])==1
    after=client.get(base+'/html?fragment=true&standalone=true').text
    assert BeautifulSoup(after,'html.parser').img['src']==before_src
    rejected=client.put(base+'/revisions',json={'baseRevision':2,'html':'<p>Unsafe image</p><img src="data:image/svg+xml;base64,PHN2Zz4="/>'})
    assert rejected.status_code==422

def test_any_and_extensible_language_settings():
    assert Options(languages=['any'],language='any').languages==['auto']
    assert Options(language='any').language=='und'
    assert Options(languages=['vie','script/Arabic'],language='pt-BR').language=='pt-BR'
    assert Options(languages=['script/Arabic']).languages==['script/Arabic']
    with pytest.raises(ValueError):Options(languages=['../../invalid'])
    with pytest.raises(ValueError):Options(languages=['auto','eng'])


def test_virtualenv_python_symlink_is_not_resolved(tmp_path):
    import os
    from app.helpers.runtime import interpreter_path
    if os.name=='nt':pytest.skip('Symlink creation needs privileges on Windows; check native runtime separately.')
    target=tmp_path/'base-python';target.touch()
    link=tmp_path/'venv'/'bin'/'python';link.parent.mkdir(parents=True);link.symlink_to(target)
    assert interpreter_path(str(link))==str(link.absolute())
    assert interpreter_path(str(link))!=str(link.resolve())


def test_real_automatic_ocr_language_detection():
    from PIL import Image, ImageDraw, ImageFont
    installed=OCRService.languages()
    if 'eng' not in installed:pytest.skip('Tesseract English is unavailable.')
    font=Path(os.environ.get('FONT_PATH','/System/Library/Fonts/Supplemental/Arial Unicode.ttf'))
    if not font.exists():pytest.skip('Unicode fixture font unavailable.')
    image=Image.new('RGB',(1500,800),'white');draw=ImageDraw.Draw(image);face=ImageFont.truetype(str(font),32)
    for index in range(12):draw.text((30,25+index*60),'Automatic language detection reads this English document.',font=face,fill='black')
    codes,warning=OCRService().resolve_languages(image,['auto'])
    assert codes and set(codes)<=set(installed)
    text=OCRService().recognize(image,codes)
    assert 'English document' in text

def test_delete_document_removes_all_owned_data_and_preserves_other_documents(client):
    from app.config.settings import settings
    from app.db.database import Session,Job,Revision,Annotation
    from sqlalchemy import select
    import uuid
    response=client.post('/api/v1/jobs',files=[('files',('delete.pdf',make_pdf(),'application/pdf')),('files',('keep.pdf',make_pdf('Keep this document'),'application/pdf'))],data={'options':'{"engine":"LIGHTWEIGHT"}'})
    remove,keep=[item['job']['id'] for item in response.json()['results']]
    assert wait(client,remove)['status']=='COMPLETED';assert wait(client,keep)['status']=='COMPLETED'
    # Wait for completed-job cleanup, not just the persisted completion state.
    from app.workers.queue import queue
    for _ in range(100):
        if remove not in queue.active_ids:break
        time.sleep(.01)
    doc=client.get(f'/api/v1/documents/{remove}').json()
    annotation={'id':'delete-anchor','documentId':remove,'revision':1,'blockIds':[doc['blocks'][0]['blockId']],'quote':{'exact':'Hello'},'position':{'start':0,'end':5},'color':'#ffdf70'}
    assert client.post(f'/api/v1/documents/{remove}/highlights',json=annotation).status_code==201
    (settings.storage/'tmp'/f'{remove}.log').write_text('test log')
    assert client.delete(f'/api/v1/documents/{remove}').status_code==204
    assert client.get(f'/api/v1/jobs/{remove}').status_code==404
    assert client.get(f'/api/v1/documents/{remove}/html').status_code==404
    assert client.get(f'/api/v1/documents/{keep}/html').status_code==200
    assert not (settings.storage/'originals'/f'{remove}.pdf').exists()
    assert not (settings.storage/'documents'/remove).exists()
    assert not (settings.storage/'tmp'/f'{remove}.log').exists()
    assert not list((settings.storage/'tmp').glob('deleted-*'))
    with Session() as db:
        assert db.get(Job,remove) is None
        assert db.scalar(select(Revision).where(Revision.document_id==remove)) is None
        assert db.scalar(select(Annotation).where(Annotation.document_id==remove)) is None
    assert client.delete(f'/api/v1/documents/{remove}').status_code==404
    # Queued/active work cannot be deleted underneath the worker.
    identity=uuid.uuid4().hex
    with Session.begin() as db:db.add(Job(id=identity,filename='busy.pdf',checksum='x',options='{}',status='CONVERTING'))
    assert client.delete(f'/api/v1/jobs/{identity}').status_code==409
    with Session.begin() as db:db.get(Job,identity).status='CANCELED'
    assert client.delete(f'/api/v1/jobs/{identity}').status_code==204


def test_delete_rolls_back_files_and_records_on_staging_failure(client):
    from app.config.settings import settings
    from unittest.mock import patch
    response=client.post('/api/v1/jobs',files={'files':('rollback.pdf',make_pdf(),'application/pdf')},data={'options':'{"engine":"LIGHTWEIGHT"}'})
    identity=response.json()['results'][0]['job']['id'];assert wait(client,identity)['status']=='COMPLETED'
    from app.workers.queue import queue
    for _ in range(100):
        if identity not in queue.active_ids:break
        time.sleep(.01)
    original_replace=Path.replace
    folder=settings.storage/'documents'/identity
    def fail_document_move(source,target):
        if source==folder:raise PermissionError('Simulated locked output folder')
        return original_replace(source,target)
    with patch.object(Path,'replace',fail_document_move):
        assert client.delete(f'/api/v1/documents/{identity}').status_code==500
    assert client.get(f'/api/v1/documents/{identity}/html').status_code==200
    assert (settings.storage/'originals'/f'{identity}.pdf').is_file()
    assert folder.is_dir()

def test_delete_startup_recovery_restores_uncommitted_and_purges_committed(client):
    from app.services.documents.deletion import purge_deleted_files
    from app.config.settings import settings
    from app.db.database import Session,Job
    import uuid
    identity=uuid.uuid4().hex
    with Session.begin() as db:db.add(Job(id=identity,filename='recovery.pdf',checksum='x',options='{}',status='CANCELED'))
    folder=settings.storage/'tmp'/('deleted-'+uuid.uuid4().hex);folder.mkdir()
    (folder/'0').write_bytes(b'original PDF bytes')
    (folder/'manifest.json').write_text(json.dumps({'jobId':identity,'files':[{'original':f'originals/{identity}.pdf','staged':'0'}]}))
    purge_deleted_files()
    original=settings.storage/'originals'/f'{identity}.pdf'
    assert original.read_bytes()==b'original PDF bytes' and not folder.exists()
    assert client.delete(f'/api/v1/documents/{identity}').status_code==204
    committed=settings.storage/'tmp'/('deleted-'+uuid.uuid4().hex);committed.mkdir()
    (committed/'0').write_bytes(b'committed deletion')
    (committed/'manifest.json').write_text(json.dumps({'jobId':identity,'files':[{'original':f'originals/{identity}.pdf','staged':'0'}]}))
    purge_deleted_files();assert not committed.exists() and not original.exists()

def test_legacy_indic_font_is_not_treated_as_valid_latin_text(tmp_path):
    from pypdf.generic import NameObject,DictionaryObject,ArrayObject,NumberObject
    reader=PdfReader(io.BytesIO(make_pdf('legacy encoded text layer')))
    for font in reader.pages[0]['/Resources']['/Font'].values():
        value=font.get_object()
        value[NameObject('/BaseFont')]=NameObject('/Walkman-Chanakya905Normal')
        value[NameObject('/FontDescriptor')]=DictionaryObject({NameObject('/Type'):NameObject('/FontDescriptor'),NameObject('/FontName'):NameObject('/Walkman-Chanakya905Normal'),NameObject('/FontBBox'):ArrayObject([NumberObject(0),NumberObject(-200),NumberObject(1000),NumberObject(900)]),NameObject('/Flags'):NumberObject(4),NameObject('/ItalicAngle'):NumberObject(0),NameObject('/Ascent'):NumberObject(800),NameObject('/Descent'):NumberObject(-200),NameObject('/CapHeight'):NumberObject(700),NameObject('/StemV'):NumberObject(80)})
    writer=PdfWriter();writer.add_page(reader.pages[0]);source=tmp_path/'legacy.pdf'
    with source.open('wb') as output:writer.write(output)
    report=PDFInspectionService().inspect(source)
    assert report['pages'][0]['classification']=='TEXT_ENCODING_PROBLEM'
    assert report['pages'][0]['legacyFonts']
    assert any('Unicode' in warning for warning in report['warnings'])


def test_forced_ocr_keeps_figures_in_single_html(tmp_path):
    from PIL import Image,ImageDraw,ImageFont
    from reportlab.lib.utils import ImageReader
    from app.services.export.standalone import standalone_html
    if 'eng' not in OCRService.languages():pytest.skip('Tesseract English is unavailable.')
    source=tmp_path/'ocr-and-figure.pdf';canvas=Canvas(str(source))
    canvas.setFont('Helvetica',18);canvas.drawString(50,750,'Visible text and a figure');canvas.drawImage(ImageReader(Image.new('RGB',(60,30),'green')),50,600,180,90);canvas.save()
    report=PDFInspectionService().inspect(source)
    doc=Document(documentId='ocr-figure',sourceFileName='ocr-and-figure.pdf',sourceChecksum='x',title='Figure',pages=report['pages'])
    output=tmp_path/'output';(output/'assets').mkdir(parents=True)
    result=LightweightConverter().convert(source,doc,Options(force_ocr=True,languages=['eng']),output)
    assert 'figure' in document_text(result).lower()
    assert len(result.assets)==1
    assert 'data:image/png;base64,' in standalone_html(result,output)


def test_multiple_native_scripts_share_one_document(tmp_path):
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    font=Path(os.environ.get('FONT_PATH','/System/Library/Fonts/Supplemental/Arial Unicode.ttf'))
    if not font.exists():pytest.skip('Set FONT_PATH to a Unicode TrueType fixture font.')
    pdfmetrics.registerFont(TTFont('MixedUnicodeFixture',str(font)))
    texts=['தமிழ் மொழி','हिन्दी भाषा','مرحبا بالعالم','中文文本','English text']
    source=tmp_path/'mixed.pdf';canvas=Canvas(str(source));canvas.setFont('MixedUnicodeFixture',18)
    for index,value in enumerate(texts):canvas.drawString(50,750-index*50,value)
    canvas.save();report=PDFInspectionService().inspect(source)
    doc=Document(documentId='mixed',sourceFileName='mixed.pdf',sourceChecksum='x',title='Mixed',pages=report['pages'])
    (tmp_path/'assets').mkdir()
    result=LightweightConverter().convert(source,doc,Options(languages=['auto']),tmp_path)
    actual=document_text(result).replace(' ','')
    for value in texts:assert value.replace(' ','') in actual

def test_known_legacy_font_language_overrides_unreliable_cover_script_detection():
    from PIL import Image
    if 'hin' not in OCRService.languages():pytest.skip('Hindi OCR pack unavailable.')
    # Sparse title pages can be classified as unrelated scripts by OSD. A known
    # Chanakya font supplies stronger language evidence than that visual guess.
    codes,warning=OCRService().resolve_languages(Image.new('RGB',(200,100),'white'),['auto'],hint='hin')
    assert codes[0]=='hin' and 'auto' not in codes

def test_native_footer_does_not_hide_a_scanned_text_page(tmp_path):
    from PIL import Image,ImageDraw,ImageFont
    from reportlab.lib.utils import ImageReader
    if 'eng' not in OCRService.languages():pytest.skip('English OCR unavailable.')
    font=Path(os.environ.get('FONT_PATH','/System/Library/Fonts/Supplemental/Arial Unicode.ttf'))
    if not font.exists():pytest.skip('Unicode fixture font unavailable.')
    scan=Image.new('RGB',(1500,500),'white');ImageDraw.Draw(scan).text((40,70),'Scanned body must be recovered',font=ImageFont.truetype(str(font),60),fill='black')
    source=tmp_path/'scan-with-footer.pdf';canvas=Canvas(str(source),pagesize=(750,250));canvas.drawImage(ImageReader(scan),0,0,750,250);canvas.setFont('Helvetica',6);canvas.drawString(20,10,'Reprint 2026');canvas.save()
    report=PDFInspectionService().inspect(source)
    assert report['pages'][0]['classification']=='MIXED_CONTENT'
    assert report['pages'][0]['requiresOCR']
    doc=Document(documentId='mixed-scan',sourceFileName='mixed-scan.pdf',sourceChecksum='x',title='Scan',pages=report['pages'])
    output=tmp_path/'output';(output/'assets').mkdir(parents=True)
    result=LightweightConverter().convert(source,doc,Options(languages=['eng']),output)
    assert 'Scanned body must be recovered' in document_text(result)
    assert result.pages[0]['textSource']=='ocr'
    assert len(result.assets)==1
