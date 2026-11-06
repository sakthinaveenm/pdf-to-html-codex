import {useMemo,useRef,useEffect} from 'react';
export interface PageMetrics{displayWidth?:number;displayHeight?:number;width?:number;height?:number}
export function HTMLPagePreview({html,page,metrics}:{html:string;page:number;metrics?:PageMetrics}){
 const cleanup=useRef<()=>void>(()=>{});
 useEffect(()=>()=>cleanup.current(),[]);
 const source=useMemo(()=>html.replace('</head>',`<style>html{font-size:16px}body{margin:0;background:#edf0e9;padding:15px}.pdf-document{background:white;max-width:none;font-size:1rem;padding:0;margin:0}.pdf-document>section{margin:0}.pdf-document>section:not([data-page="${page}"]){display:none}</style></head>`),[html,page]);
 return <iframe title="Converted HTML page" className="page-html-frame" sandbox="allow-same-origin" srcDoc={source} onLoad={event=>{
  cleanup.current();const frame=event.currentTarget;const doc=frame.contentDocument;const view=frame.contentWindow;
  const original=frame.closest('.page-comparison')?.querySelector<HTMLElement>('.pdf-preview');if(!doc||!view)return;
  const fit=()=>{const article=doc.querySelector<HTMLElement>('.pdf-document');if(!article)return;const scale=(frame.clientWidth-30)/(metrics?.displayWidth||metrics?.width||612);doc.documentElement.style.fontSize=16*scale+'px';article.style.minHeight=(metrics?.displayHeight||metrics?.height||792)*scale+'px';};
  fit();view.scrollTo(0,0);if(original)original.scrollTop=0;
  let locked=false;let timer=0;
  const unlock=()=>{window.clearTimeout(timer);timer=window.setTimeout(()=>{locked=false;},80);};
  const fromPDF=()=>{if(locked||!original)return;locked=true;const extent=original.scrollHeight-original.clientHeight;view.scrollTo(0,(extent>0?original.scrollTop/extent:0)*(doc.documentElement.scrollHeight-view.innerHeight));unlock();};
  const fromHTML=()=>{if(locked||!original)return;locked=true;const extent=doc.documentElement.scrollHeight-view.innerHeight;original.scrollTop=(extent>0?view.scrollY/extent:0)*(original.scrollHeight-original.clientHeight);unlock();};
  const resize=new ResizeObserver(fit);resize.observe(frame);original?.addEventListener('scroll',fromPDF,{passive:true});view.addEventListener('scroll',fromHTML,{passive:true});
  cleanup.current=()=>{resize.disconnect();original?.removeEventListener('scroll',fromPDF);view.removeEventListener('scroll',fromHTML);window.clearTimeout(timer);};
 }}/>
}
