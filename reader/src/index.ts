import {nodes,codepoints,codepointToUtf16,rangeAt,resolveAnchor,selectionAnchor} from './anchors';
import type {Annotation,ReaderMessage,ReaderEventType} from './types';
import {isAnnotation} from './types';
declare global {interface Window {__readerInitialAnnotations?:Annotation[];Reader:ReaderAPI;ReactNativeWebView?:{postMessage:(message:string)=>void};__readerConfig?:{documentId:string;revision:number};Highlight?:new(...ranges:Range[])=>unknown}}
interface ReaderAPI {restore:(items:Annotation[])=>void;create:(color?:string)=>Annotation|null;remove:(id:string)=>void;update:(id:string,color:string)=>void;fontSize:(size:number)=>void;theme:(dark:boolean)=>void;search:(query:string)=>number;selection:()=>Annotation|null}
const root=document.querySelector<HTMLElement>('article');
if(root){
 const article=root;
 const config=window.__readerConfig||{documentId:article.dataset.documentId||'',revision:1};
 let annotations:Annotation[]=[];let pending:Annotation|null=null;
 const highlights=(CSS as unknown as {highlights?:Map<string,unknown>}).highlights;
 const style=document.createElement('style');document.head.append(style);
 function emit(type:ReaderEventType,payload:Record<string,unknown>){const msg:ReaderMessage={version:1,type,payload};window.ReactNativeWebView?.postMessage(JSON.stringify(msg));window.parent.postMessage(msg,window.location.origin==='null'?'*':window.location.origin);}
 function clear(){article.querySelectorAll('mark[data-reader-highlight]').forEach(mark=>mark.replaceWith(...mark.childNodes));article.normalize();highlights?.clear();style.textContent='';}
 function paint(){clear();const text=article.textContent||'';annotations=annotations.map(a=>resolveAnchor(a,text,config.revision));
 const resolved=annotations.filter(a=>a.status==='resolved');
 if(highlights&&window.Highlight){resolved.forEach((a,i)=>{const range=rangeAt(article,a.position.start,a.position.end);if(range){const name='annotation'+i;highlights.set(name,new window.Highlight!(range));style.textContent+=`::highlight(${name}){background:${a.color};color:inherit}`;}});}
 else {
  // Split text nodes only, never extract paragraph structure. Repaint starts from pristine text nodes.
  let cursor=0;const original=nodes(article);
  for(const node of original){const length=codepoints(node.data);const relevant=resolved.filter(a=>a.position.start<cursor+length&&a.position.end>cursor);const boundaries=new Set([0,length]);
   relevant.forEach(a=>{boundaries.add(Math.max(0,a.position.start-cursor));boundaries.add(Math.min(length,a.position.end-cursor));});
   const points=Array.from(boundaries).sort((a,b)=>a-b);const fragment=document.createDocumentFragment();
   for(let i=0;i<points.length-1;i++){const from=points[i],to=points[i+1];const textNode=document.createTextNode(node.data.slice(codepointToUtf16(node.data,from),codepointToUtf16(node.data,to)));const a=relevant.find(a=>a.position.start<=cursor+from&&a.position.end>=cursor+to);
    if(a){const mark=document.createElement('mark');mark.dataset.readerHighlight=a.id;mark.style.backgroundColor=a.color;mark.append(textNode);fragment.append(mark);}else fragment.append(textNode);}
   node.replaceWith(fragment);cursor+=length;
  }
 }
 }

 window.Reader={
 restore(items){if(!Array.isArray(items)||items.some(a=>!isAnnotation(a)||a.documentId!==config.documentId)){emit('READER_ERROR',{message:'Invalid annotations'});return;}annotations=items;paint();},
 selection(){return selectionAnchor(article,config.documentId,config.revision)||pending;},
 create(color='#ffdf70'){const a=window.Reader.selection();if(!a||!/^#[0-9a-fA-F]{6}$/.test(color))return null;a.color=color;annotations.push(a);paint();pending=null;emit('HIGHLIGHT_CREATED',{annotation:a});return a;},
 remove(id){annotations=annotations.filter(a=>a.id!==id);paint();emit('HIGHLIGHT_REMOVED',{id});},
 update(id,color){if(!/^#[0-9a-fA-F]{6}$/.test(color))return;annotations=annotations.map(a=>a.id===id?{...a,color}:a);paint();emit('HIGHLIGHT_UPDATED',{id,color});},
 fontSize(size){if(!Number.isFinite(size)||size<12||size>40)return;article.style.setProperty('--reader-size',size+'px');emit('FONT_SIZE_CHANGED',{size});},
 theme(dark){document.body.classList.toggle('dark',dark);},
 search(query){paint();if(!query)return 0;const text=article.textContent||'';let from=0;const ranges:Range[]=[];
 while(from<text.length){const found=text.indexOf(query,from);if(found<0)break;const range=rangeAt(article,codepoints(text.slice(0,found)),codepoints(text.slice(0,found+query.length)));if(range)ranges.push(range);from=found+query.length;}
 if(highlights&&window.Highlight){highlights.set('search',new window.Highlight(...ranges));style.textContent+='::highlight(search){background:#9cdbdf;color:#172226}';}ranges[0]?.startContainer.parentElement?.scrollIntoView({block:'center'});return ranges.length;}
 };
 document.addEventListener('selectionchange',()=>{const a=selectionAnchor(article,config.documentId,config.revision);if(a){pending=a;emit('TEXT_SELECTED',{annotation:a,selectedText:a.quote.exact});}});
 article.addEventListener('click',event=>{const link=(event.target as Element).closest('a');if(link){event.preventDefault();const href=link.getAttribute('href')||'';if(/^(https?:|mailto:|#)/.test(href))emit('LINK_CLICKED',{href});}});
 if(window.__readerInitialAnnotations)window.Reader.restore(window.__readerInitialAnnotations);
 emit('READER_READY',{documentId:config.documentId,revision:config.revision});
}
