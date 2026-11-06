import {useEffect,useRef,useState} from 'react';
import {getDocument,GlobalWorkerOptions,type PDFDocumentProxy,type RenderTask} from 'pdfjs-dist';
import workerURL from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
GlobalWorkerOptions.workerSrc=workerURL;
export function PDFPreview({url,page}:{url:string;page:number}){
 const canvas=useRef<HTMLCanvasElement>(null);const container=useRef<HTMLDivElement>(null);const [width,setWidth]=useState(0);const [pdf,setPDF]=useState<PDFDocumentProxy|null>(null);const [error,setError]=useState('');
 useEffect(()=>{if(!container.current)return;const resize=new ResizeObserver(entries=>setWidth(entries[0].contentRect.width));resize.observe(container.current);return()=>resize.disconnect();},[]);
 useEffect(()=>{setError('');const task=getDocument({url});let alive=true;void task.promise.then(value=>{if(alive)setPDF(value);}).catch(e=>{if(alive)setError(String(e));});return()=>{alive=false;setPDF(null);void task.destroy();};},[url]);
 useEffect(()=>{if(!pdf||!canvas.current||width<=0)return;if(container.current)container.current.scrollTop=0;let alive=true;let render:RenderTask|undefined;
 void pdf.getPage(Math.max(1,Math.min(page,pdf.numPages))).then(source=>{if(!alive||!canvas.current)return;const context=canvas.current.getContext('2d');if(!context)return;const viewport=source.getViewport({scale:Math.max(.2,width/source.getViewport({scale:1}).width)});const ratio=window.devicePixelRatio||1;canvas.current.width=Math.round(viewport.width*ratio);canvas.current.height=Math.round(viewport.height*ratio);canvas.current.style.width=viewport.width+'px';canvas.current.style.height=viewport.height+'px';render=source.render({canvas:canvas.current,canvasContext:context,viewport,transform:ratio===1?undefined:[ratio,0,0,ratio,0,0]});return render.promise;}).catch(e=>{if(alive&&e?.name!=='RenderingCancelledException')setError(String(e));});return()=>{alive=false;render?.cancel();};},[pdf,page,width]);
 return <div ref={container} className="pdf-preview" aria-label="Original PDF preview">{error?<p className="error">{error} <a href={url} target="_blank" rel="noreferrer">Open original PDF</a></p>:<canvas ref={canvas} aria-label={`Original PDF page ${page}`}/>}</div>;
}
