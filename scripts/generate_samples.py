"""Generated fixtures contain project-authored text; no third-party PDF samples."""
from pathlib import Path
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.utils import ImageReader
from PIL import Image, ImageDraw, ImageFont
root=Path(__file__).resolve().parents[1]/'samples';root.mkdir(exist_ok=True)
c=Canvas(str(root/'digital-english.pdf'))
c.setFont('Helvetica-Bold',24);c.drawString(60,770,'A world of readable documents')
c.setFont('Helvetica',12)
for y,text in [(725,'Language brings ideas to life.'),(695,'Select this sentence and save a highlight.'),(665,'Offline reading keeps your documents close.')]:c.drawString(60,y,text)
c.showPage();c.setFont('Helvetica',12);c.drawString(60,760,'A second page for annotations and page navigation.');c.save()
image=Image.new('RGB',(1400,400),'white');draw=ImageDraw.Draw(image)
font_path='/System/Library/Fonts/Supplemental/Arial.ttf'
font=ImageFont.truetype(font_path,50) if Path(font_path).exists() else ImageFont.load_default(size=50)
draw.text((70,80),'Scanned English document',font=font,fill='black');draw.text((70,180),'Real OCR makes this text selectable.',font=font,fill='black')
c=Canvas(str(root/'scanned-english.pdf'),pagesize=(700,200));c.drawImage(ImageReader(image),0,0,700,200);c.save()
print(root)
# A small figure with native text for single-file/base64 and editor round trips.
c=Canvas(str(root/'digital-image.pdf'))
c.drawString(50,750,'First page with an embedded figure')
c.drawImage(ImageReader(Image.new('RGB',(60,30),'green')),50,600,180,90)
c.showPage();c.drawString(50,750,'Second page remains editable');c.save()
