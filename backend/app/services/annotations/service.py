from app.schemas.document import Document, Highlight
from app.services.html.service import document_text
from bs4 import BeautifulSoup

def resolve(highlight: Highlight, doc: Document) -> Highlight:
    text=document_text(doc)
    start,end=highlight.position.start,highlight.position.end
    exact=highlight.quote.exact
    if highlight.revision==doc.revision and text[start:end]==exact:
        highlight.status='resolved'; return highlight
    positions=[]; offset=0
    while True:
        found=text.find(exact,offset)
        if found<0: break
        before=text[:found]; after=text[found+len(exact):]
        if (not highlight.quote.prefix or before.endswith(highlight.quote.prefix)) and (not highlight.quote.suffix or after.startswith(highlight.quote.suffix)):
            positions.append(found)
        offset=found+1
    if len(positions)!=1:
        highlight.status='unresolved'; return highlight
    highlight.position.start=positions[0]; highlight.position.end=positions[0]+len(exact)
    highlight.revision=doc.revision; highlight.status='resolved'
    cursor=0; ids=[]
    for block in sorted(doc.blocks,key=lambda b:b.readingOrder):
        length=len(BeautifulSoup(block.content,'html.parser').get_text())
        if cursor<highlight.position.end and cursor+length>highlight.position.start: ids.append(block.blockId)
        cursor+=length
    highlight.blockIds=ids
    return highlight
