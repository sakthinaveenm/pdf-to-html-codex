import {useEffect,useRef,useState} from 'react';
import {getDocument,GlobalWorkerOptions,type PDFDocumentProxy,type RenderTask} from 'pdfjs-dist';
import workerURL from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
GlobalWorkerOptions.workerSrc=workerURL;
/** PDF.js is used only for the source preview. Canonical HTML remains semantic text. */
export function PDFPreview({url,page}:{url:string;page:number}){
 const canvas=useRef<HTMLCanvasElement>(null);const [pdf,setPDF]=useState<PDFDocumentProxy|null>(null);const [error,setError]=useState('');
 useEffect(()=>{setError('');const task=getDocument({url});let alive=true;void task.promise.then(value=>{if(alive)setPDF(value);}).catch(e=>{if(alive)setError(String(e));});return()=>{alive=false;setPDF(null);void task.destroy();};},[url]);
 useEffect(()=>{if(!pdf||!canvas.current)return;let alive=true;let render:RenderTask|undefined;
 void pdf.getPage(Math.max(1,Math.min(page,pdf.numPages))).then(source=>{if(!alive||!canvas.current)return;const context=canvas.current.getContext('2d');if(!context)return;const width=canvas.current.parentElement?.clientWidth||550;const viewport=source.getViewport({scale:Math.max(.2,(width-30)/source.getViewport({scale:1}).width)});canvas.current.width=viewport.width;canvas.current.height=viewport.height;render=source.render({canvas:canvas.current,canvasContext:context,viewport});return render.promise;}).catch(e=>{if(alive&&e?.name!=='RenderingCancelledException')setError(String(e));});
 return()=>{alive=false;render?.cancel();};},[pdf,page]);
 return <div className="pdf-preview" aria-label="Original PDF preview">{error?<p className="error">{error} <a href={url} target="_blank" rel="noreferrer">Open original PDF</a></p>:<canvas ref={canvas} aria-label={`Original PDF page ${page}`}/>}</div>;
}
