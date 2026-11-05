import html
import statistics
from pathlib import Path
import pdfplumber
import pypdfium2 as pdfium
from app.schemas.document import Document, Options
from app.services.converters.base import PDFConverter
from app.services.html.service import HTMLNormalizationService
from app.services.ocr.service import OCRService

class LightweightConverter(PDFConverter):
    name = 'LIGHTWEIGHT'
    def check_availability(self) -> bool:
        return True

    def convert(self, path: Path, document: Document, options: Options, output: Path) -> Document:
        normalizer = HTMLNormalizationService()
        renderer = None
        document.warnings.append('Lightweight fallback: reading order, headings, lists, equations and table spans are heuristic. Review against the original PDF.')
        try:
            with pdfplumber.open(path) as pdf:
                for index, page in enumerate(pdf.pages):
                    info = document.pages[index]
                    use_ocr = options.force_ocr or info['classification'] in ('SCANNED_IMAGE','TEXT_ENCODING_PROBLEM')
                    source = ''; provenance = 'lightweight'
                    if use_ocr:
                        if renderer is None: renderer = pdfium.PdfDocument(path)
                        image = renderer[index].render(scale=options.dpi/72).to_pil()
                        try:
                            text = OCRService().recognize(image,options.languages)
                        finally:
                            image.close()
                        source = ''.join('<p>'+html.escape(p)+'</p>' for p in text.split('\n\n') if p.strip())
                        provenance = 'tesseract'
                        info['textSource'] = 'ocr'
                    else:
                        info['textSource'] = 'native'
                        tables = page.find_tables()
                        table_boxes = [t.bbox for t in tables]
                        def outside(obj):
                            x = (obj.get('x0',0)+obj.get('x1',0))/2
                            y = (obj.get('top',0)+obj.get('bottom',0))/2
                            return not any(a <= x <= c and b <= y <= d for a,b,c,d in table_boxes)
                        filtered = page.filter(outside)
                        words = filtered.extract_words(extra_attrs=['fontname','size'])
                        median = statistics.median([float(w['size']) for w in words]) if words else 12
                        entries = []
                        # Split at wide horizontal gaps to avoid merging two columns.
                        lines: list[list[dict]] = []
                        for word in words:
                            if not lines or abs(float(word['top'])-float(lines[-1][0]['top'])) > 3 or float(word['x0'])-float(lines[-1][-1]['x1']) > 60:
                                lines.append([word])
                            else: lines[-1].append(word)
                        for line in lines:
                            fragments = []
                            for word in line:
                                value = html.escape(word['text'])
                                font = word['fontname'].lower()
                                if 'bold' in font: value = '<strong>'+value+'</strong>'
                                if any(f in font for f in ('italic','oblique')): value = '<em>'+value+'</em>'
                                fragments.append(value)
                            size = max(float(w['size']) for w in line)
                            tag = 'h2' if size >= median*1.3 else 'p'
                            entries.append((float(line[0]['top']),float(line[0]['x0']),'<'+tag+'>'+' '.join(fragments)+'</'+tag+'>'))
                        for table in tables:
                            rows = table.extract()
                            markup = '<table><tbody>'+''.join('<tr>'+''.join('<td>'+html.escape(cell or '')+'</td>' for cell in row)+'</tr>' for row in rows)+'</tbody></table>'
                            entries.append((float(table.bbox[1]),float(table.bbox[0]),markup))
                        # Detect clear two-column pages; tables crossing the gutter disable this heuristic.
                        left = [e for e in entries if e[1] < float(page.width)*.45]
                        right = [e for e in entries if e[1] > float(page.width)*.5]
                        if len(left)>3 and len(right)>3 and not tables:
                            entries = sorted(left,key=lambda e:e[0])+sorted([e for e in entries if e not in left],key=lambda e:e[0])
                            document.warnings.append(f'Page {index+1}: inferred column reading order; review required.')
                        else: entries.sort(key=lambda e:(e[0],e[1]))
                        source = ''.join(e[2] for e in entries)
                        for link in page.hyperlinks:
                            uri = link.get('uri')
                            if uri:
                                source += '<p><a href="'+html.escape(uri,quote=True)+'">'+html.escape(uri)+'</a></p>'
                        for number, image_obj in enumerate(page.images):
                            # Crop only embedded figure regions, never use page screenshots for text.
                            box = (max(0,image_obj['x0']),max(0,image_obj['top']),min(page.width,image_obj['x1']),min(page.height,image_obj['bottom']))
                            if box[2] <= box[0] or box[3] <= box[1]: continue
                            if (box[2]-box[0])*(box[3]-box[1]) > page.width*page.height*.8:
                                document.warnings.append(f'Page {index+1}: full-page image omitted from text output.'); continue
                            asset = f'image-{index+1}-{number+1}.png'
                            try:
                                page.crop(box).to_image(resolution=120).original.save(output/'assets'/asset)
                                document.assets.append({'assetId':asset,'path':'assets/'+asset,'sourcePage':index+1})
                                source += '<figure><img src="assets/'+asset+'" alt="Extracted figure from page '+str(index+1)+'"></figure>'
                            except Exception as exc:
                                document.warnings.append(f'Page {index+1}: figure extraction failed: {type(exc).__name__}')
                    document.blocks.extend(normalizer.blocks(source,document.documentId,index+1,provenance,options.language,len(document.blocks)))
                    page.close()
        finally:
            if renderer is not None: renderer.close()
        return document
