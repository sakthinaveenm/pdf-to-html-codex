import type {Annotation} from './types';
export const codepoints=(text:string):number=>Array.from(text).length;
export function utf16ToCodepoint(text:string,offset:number):number {
 if(offset<0||offset>text.length)throw new RangeError('UTF-16 offset outside text');
 if(offset>0&&offset<text.length&&/[\uD800-\uDBFF]/.test(text[offset-1])&&/[\uDC00-\uDFFF]/.test(text[offset]))throw new RangeError('Offset splits a surrogate pair');
 return codepoints(text.slice(0,offset));
}
export function codepointToUtf16(text:string,offset:number):number {
 const chars=Array.from(text);if(offset<0||offset>chars.length)throw new RangeError('Codepoint offset outside text');
 return chars.slice(0,offset).join('').length;
}
export function nodes(root:HTMLElement):Text[]{
 const walk=root.ownerDocument.createTreeWalker(root,NodeFilter.SHOW_TEXT); const found:Text[]=[];
 while(walk.nextNode())found.push(walk.currentNode as Text); return found;
}
export function rangeAt(root:HTMLElement,start:number,end:number):Range|null {
 const list=nodes(root);let cursor=0;let first: [Text,number]|undefined;let last: [Text,number]|undefined;
 for(const node of list){const size=codepoints(node.data);
 if(!first&&start>=cursor&&start<=cursor+size)first=[node,codepointToUtf16(node.data,start-cursor)];
 if(end>=cursor&&end<=cursor+size){last=[node,codepointToUtf16(node.data,end-cursor)];break;}
 cursor+=size;}
 if(!first||!last||end<=start)return null;
 const range=root.ownerDocument.createRange();range.setStart(...first);range.setEnd(...last);return range;
}
export function resolveAnchor(annotation:Annotation,text:string,revision:number):Annotation {
 const chars=Array.from(text);const {start,end}=annotation.position;
 if(annotation.revision===revision&&chars.slice(start,end).join('')===annotation.quote.exact)return {...annotation,status:'resolved'};
 const {exact,prefix,suffix}=annotation.quote;const candidates:number[]=[];let offset=0;
 while(offset<=text.length){const found=text.indexOf(exact,offset);if(found<0)break;
 if((!prefix||text.slice(0,found).endsWith(prefix))&&(!suffix||text.slice(found+exact.length).startsWith(suffix)))candidates.push(codepoints(text.slice(0,found)));
 offset=found+Math.max(1,exact.length);}
 if(candidates.length!==1)return {...annotation,status:'unresolved'};
 return {...annotation,revision,status:'resolved',position:{start:candidates[0],end:candidates[0]+codepoints(exact),unit:'unicode-codepoint'}};
}
export function selectionAnchor(root:HTMLElement,documentId:string,revision:number):Annotation|null {
 const selection=root.ownerDocument.getSelection();if(!selection||selection.isCollapsed||!selection.rangeCount)return null;
 const range=selection.getRangeAt(0);if(!root.contains(range.startContainer)||!root.contains(range.endContainer))return null;
 const prefix=root.ownerDocument.createRange();prefix.selectNodeContents(root);prefix.setEnd(range.startContainer,range.startOffset);
 let start=codepoints(prefix.toString());let end=start+codepoints(range.toString());
 const text=root.textContent||'';const chars=Array.from(text);
 // Expand to grapheme boundaries so Indic vowel signs and emoji clusters remain intact.
 if('Segmenter' in Intl){const segmenter=new Intl.Segmenter(undefined,{granularity:'grapheme'});const segments=Array.from(segmenter.segment(text));
 const utfStart=codepointToUtf16(text,start),utfEnd=codepointToUtf16(text,end);
 for(const s of segments){if(s.index<utfStart&&s.index+s.segment.length>utfStart)start=codepoints(text.slice(0,s.index));
 if(s.index<utfEnd&&s.index+s.segment.length>utfEnd)end=codepoints(text.slice(0,s.index+s.segment.length));}}
 if(end<=start)return null;
 const ids=Array.from(root.querySelectorAll<HTMLElement>('[data-block-id]')).filter(n=>range.intersectsNode(n)).map(n=>n.dataset.blockId!);
 return {id:crypto.randomUUID(),documentId,revision,blockIds:ids,quote:{exact:chars.slice(start,end).join(''),prefix:chars.slice(Math.max(0,start-32),start).join(''),suffix:chars.slice(end,end+32).join('')},position:{start,end,unit:'unicode-codepoint'},color:'#ffdf70',status:'resolved'};
}
