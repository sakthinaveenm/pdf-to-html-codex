/** Copy literal HTML source, suitable for an editor's HTML/source mode. */
export async function copyHTML(source:string):Promise<void>{
 if(navigator.clipboard?.writeText){try{await navigator.clipboard.writeText(source);return;}catch{/* Use native selection on older browsers. */}}
 const previous=document.activeElement as HTMLElement|null;const area=document.createElement('textarea');area.value=source;area.style.position='fixed';area.style.opacity='0';document.body.append(area);area.select();
 try{if(!document.execCommand('copy'))throw new Error('Clipboard access was blocked. Select the HTML code and copy it manually.');}finally{area.remove();previous?.focus();}
}
/** Paste actual formatted content into a rich-text editor rather than literal tags. */
export async function copyFormattedHTML(source:string):Promise<void>{
 const text=new DOMParser().parseFromString(source,'text/html').body.textContent||'';
 if(navigator.clipboard?.write&&typeof ClipboardItem!=='undefined'){
  try{await navigator.clipboard.write([new ClipboardItem({'text/html':new Blob([source],{type:'text/html'}),'text/plain':new Blob([text],{type:'text/plain'})})]);return;}catch{/* Native rich selection fallback below. */}
 }
 const previous=document.activeElement as HTMLElement|null;const selection=getSelection();const saved:Range[]=[];if(selection)for(let i=0;i<selection.rangeCount;i++)saved.push(selection.getRangeAt(i).cloneRange());
 const holder=document.createElement('div');holder.contentEditable='true';holder.style.cssText='position:fixed;left:-10000px;top:0;width:800px;background:white';holder.innerHTML=source;document.body.append(holder);
 try{const range=document.createRange();range.selectNodeContents(holder);selection?.removeAllRanges();selection?.addRange(range);holder.focus();if(!document.execCommand('copy'))throw new Error('Rich clipboard access was blocked. Use Copy HTML Source and paste into your editor’s source mode.');}
 finally{holder.remove();selection?.removeAllRanges();saved.forEach(range=>selection?.addRange(range));previous?.focus();}
}
