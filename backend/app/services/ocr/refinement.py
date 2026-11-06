"""Retry uncertain text lines in a single local Tesseract batch."""
import csv
import io
from pathlib import Path
import subprocess
import tempfile
import statistics
from PIL import ImageOps


def refine_lines(image,regions,page,languages,model_dir,scale):
    crop=page.cropbox or page.bbox;origin_x=max(page.bbox[0],crop[0]);origin_y=max(page.bbox[1],crop[1])
    candidates=[]
    for region in regions:
        for line in region.lines:
            confidence=sum(float(word.get('confidence',0)) for word in line)/len(line)
            if confidence>=85:continue
            x0=min(word['x0'] for word in line);x1=max(word['x1'] for word in line)
            y0=min(word['top'] for word in line);y1=max(word['bottom'] for word in line)
            chars=[char for char in page.chars if x0-3<=(char['x0']+char['x1'])/2<=x1+3 and y0-3<=(char['top']+char['bottom'])/2<=y1+3]
            if not chars or statistics.median(float(char['size']) for char in chars)>=11:continue
            x0=min(x0,min(c['x0'] for c in chars));x1=max(x1,max(c['x1'] for c in chars))
            y0=min(y0,min(c['top'] for c in chars));y1=max(y1,max(c['bottom'] for c in chars))
            box=(max(0,int((x0-origin_x)*scale)-5),max(0,int((y0-origin_y)*scale)-4),min(image.width,int((x1-origin_x)*scale)+5),min(image.height,int((y1-origin_y)*scale)+4))
            if box[2]>box[0] and box[3]>box[1]:candidates.append((line,confidence,box))
    if not candidates:return 0
    with tempfile.TemporaryDirectory(prefix='pdf-ocr-lines-') as temporary:
        root=Path(temporary);paths=[]
        for index,(_,_,box) in enumerate(candidates):
            path=root/f'{index}.png';tile=image.crop(box).convert('L');resized=tile.resize((round(tile.width*1.5),round(tile.height*1.5)));ImageOps.autocontrast(resized).save(path);tile.close();resized.close();paths.append(str(path.resolve()))
        inputs=root/'lines.txt';inputs.write_text('\n'.join(paths)+'\n')
        command=['tesseract',str(inputs.resolve()),'stdout','-l','+'.join(languages),'--oem','1','--psm','7']
        if model_dir:command+=['--tessdata-dir',str(model_dir.resolve())]
        result=subprocess.run(command+['-c','tessedit_create_tsv=1'],capture_output=True,text=True,encoding='utf-8',timeout=180,check=True)
        outputs={}
        for row in csv.DictReader(io.StringIO(result.stdout),delimiter='\t'):
            if row.get('level')!='5' or not row.get('text','').strip():continue
            number=int(row['page_num'])-1
            if number>=len(candidates):continue
            box=candidates[number][2]
            word={'text':row['text'],'confidence':float(row['conf']),'x0':(box[0]+int(row['left'])/1.5)/scale+origin_x,'x1':(box[0]+(int(row['left'])+int(row['width']))/1.5)/scale+origin_x,'top':(box[1]+int(row['top'])/1.5)/scale+origin_y,'bottom':(box[1]+(int(row['top'])+int(row['height']))/1.5)/scale+origin_y,'line':'1'}
            outputs.setdefault(number,[]).append(word)
        repaired=0
        for index,words in outputs.items():
            original,confidence,_=candidates[index];new_confidence=sum(word['confidence'] for word in words)/len(words)
            if new_confidence>confidence+3 and len(''.join(word['text'] for word in words))>=len(''.join(word['text'] for word in original))*.95:
                original[:]=words;repaired+=1
        for region in regions:
            words=[word for line in region.lines for word in line]
            region.bbox=(min(word['x0'] for word in words),min(word['top'] for word in words),max(word['x1'] for word in words),max(word['bottom'] for word in words))
            region.text=' '.join(word['text'] for word in words)
        return repaired
