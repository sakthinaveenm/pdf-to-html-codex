import io
import json
import time
import zipfile
from reportlab.pdfgen.canvas import Canvas
from bs4 import BeautifulSoup


def upload_book(client):
    data=io.BytesIO();pdf=Canvas(data)
    for number in (1,2):
        pdf.setFont('Helvetica-Bold',24);pdf.drawCentredString(300,730,f'Chapter {number}')
        pdf.setFont('Helvetica',12);pdf.drawString(60,680,f'Unique content for page {number}');pdf.showPage()
    pdf.save()
    result=client.post('/api/v1/jobs',files={'files':('book.pdf',data.getvalue(),'application/pdf')},data={'options':'{"engine":"LIGHTWEIGHT"}'})
    book=result.json()['results'][0]['job']['id']
    for _ in range(200):
        response=client.get(f'/api/v1/books/{book}/pages').json()
        if response['completed']==2:return book
        time.sleep(.1)
    raise AssertionError(response)


def test_page_isolation_edit_reset_export_and_delete(client):
    book=upload_book(client);base=f'/api/v1/books/{book}'
    first=client.get(base+'/pages/1/html').text;second=client.get(base+'/pages/2/html').text
    assert 'Unique content for page 1' in first and 'Unique content for page 2' not in first
    assert 'Unique content for page 2' in second and 'Unique content for page 1' not in second
    assert not any(tag in first.lower() for tag in ('<html','<head','<body','<script','<style'))
    assert 'font-size' in first and 'data-page="1"' in first
    detail=client.get(base+'/pages/1').json();revision=detail['revision']
    saved=client.put(base+'/pages/1/revisions',json={'baseRevision':revision,'html':first.replace('Unique content','Corrected content')})
    assert saved.status_code==200,saved.text
    assert saved.json()['edited'] and saved.json()['revision']==revision+1
    assert client.get(base+'/pages/2/html').text==second
    assert client.post(base+'/pages/1/reconvert').status_code==409
    assert client.put(base+'/pages/1/revisions',json={'baseRevision':revision,'html':first}).status_code==409
    assert client.post(base+'/pages/1/reset').status_code==200
    assert 'Unique content' in client.get(base+'/pages/1/html').text
    export=client.get(base+'/export?pages=2');assert export.status_code==200
    with zipfile.ZipFile(io.BytesIO(export.content)) as archive:
        assert 'pages/0002/paste.html' in archive.namelist()
        assert 'pages/0001/paste.html' not in archive.namelist()
        assert json.loads(archive.read('book.json'))['exportedPages']==[2]
        assert '<!DOCTYPE html>' in archive.read('pages/0002/standalone.html').decode()
    whole=client.get(f'/api/v1/documents/{book}/ast').json()
    block=next(block for block in whole['blocks'] if 'Unique content for page 1' in block['content'])
    markup=''.join(f'<section data-page="{item["sourcePage"]}">{item["content"]}</section>' for item in whole['blocks'])
    assert client.put(f'/api/v1/documents/{book}/revisions',json={'baseRevision':whole['revision'],'html':markup.replace('Unique content for page 1','Legacy API correction')}).status_code==200
    assert 'Legacy API correction' in client.get(base+'/pages/1/html').text
    assert 'Unique content for page 2' in client.get(base+'/pages/2/html').text
    assert client.get(base+'/export?pages=99').status_code==422
    assert client.get(base+'/pages/1/html?image_mode=url&asset_base_url=file:///tmp').status_code==422
    for _ in range(50):
        if client.get(f'/api/v1/jobs/{book}').json()['status']=='COMPLETED':break
        time.sleep(.1)
    assert client.delete(f'/api/v1/documents/{book}').status_code==204
    assert client.get(base+'/pages').status_code==404


def test_typography_sanitization():
    from app.services.html.service import sanitize
    value=sanitize('<h1 style="text-align:center;font-size:4em;font-weight:700;position:absolute;background:url(https://evil)">Title</h1>')
    node=BeautifulSoup(value,'html.parser').h1
    assert 'text-align: center' in node['style'] and 'font-size: 4em' in node['style']
    assert 'position' not in node['style'] and 'url(' not in node['style']


def test_retry_only_failed_page_preserves_corrected_neighbor(client):
    from app.db.database import Session,BookPage,Job
    book=upload_book(client);base=f'/api/v1/books/{book}'
    for _ in range(50):
        if client.get(f'/api/v1/jobs/{book}').json()['status']=='COMPLETED':break
        time.sleep(.1)
    first=client.get(base+'/pages/1/html').text
    saved=client.put(base+'/pages/1/revisions',json={'baseRevision':1,'html':first.replace('Unique content','Manual correction')})
    assert saved.status_code==200
    with Session.begin() as db:
        failed=db.get(BookPage,(book,2));failed.status='FAILED';failed.error='Simulated isolated page failure'
        db.get(Job,book).status='PARTIAL'
    assert client.get(base+'/pages/1/html').status_code==200
    assert client.post(base+'/pages/2/retry').status_code==200
    for _ in range(150):
        status=client.get(base+'/pages/2').json()['status']
        if status=='COMPLETED':break
        time.sleep(.1)
    assert status=='COMPLETED'
    assert client.get(base+'/pages/1').json()['revision']==2
    assert 'Manual correction' in client.get(base+'/pages/1/html').text
