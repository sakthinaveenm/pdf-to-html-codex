export interface Annotation {
 id:string; documentId:string; revision:number; blockIds:string[];
 quote:{exact:string;prefix:string;suffix:string};
 position:{start:number;end:number;unit:'unicode-codepoint'};
 color:string; status:'resolved'|'unresolved';
}
export type ReaderEventType='READER_READY'|'TEXT_SELECTED'|'HIGHLIGHT_CREATED'|'HIGHLIGHT_REMOVED'|'HIGHLIGHT_UPDATED'|'LINK_CLICKED'|'FONT_SIZE_CHANGED'|'READER_ERROR';
export interface ReaderMessage {version:1;type:ReaderEventType;payload:Record<string,unknown>}
function record(value:unknown):value is Record<string,unknown>{return value!==null&&typeof value==='object'&&!Array.isArray(value);}
export function isAnnotation(value:unknown):value is Annotation{
 if(!record(value)||!record(value.quote)||!record(value.position))return false;
 const q=value.quote,p=value.position;
 return typeof value.id==='string'&&/^[a-zA-Z0-9_-]{1,80}$/.test(value.id)&&typeof value.documentId==='string'&&Number.isInteger(value.revision)&&Number(value.revision)>0&&Array.isArray(value.blockIds)&&value.blockIds.length>0&&value.blockIds.every(id=>typeof id==='string')&&typeof q.exact==='string'&&q.exact.length>0&&typeof q.prefix==='string'&&typeof q.suffix==='string'&&Number.isInteger(p.start)&&Number(p.start)>=0&&Number.isInteger(p.end)&&Number(p.end)>Number(p.start)&&p.unit==='unicode-codepoint'&&typeof value.color==='string'&&/^#[0-9a-fA-F]{6}$/.test(value.color)&&(value.status==='resolved'||value.status==='unresolved');
}
export function parseMessage(value:string):ReaderMessage|null {
 try {const m:unknown=JSON.parse(value);if(!record(m)||m.version!==1||!record(m.payload))return null;const p=m.payload;let valid=false;
 switch(m.type){
 case 'READER_READY':valid=typeof p.documentId==='string'&&Number.isInteger(p.revision)&&Number(p.revision)>0;break;
 case 'TEXT_SELECTED':valid=typeof p.selectedText==='string'&&isAnnotation(p.annotation);break;
 case 'HIGHLIGHT_CREATED':valid=isAnnotation(p.annotation);break;
 case 'HIGHLIGHT_REMOVED':valid=typeof p.id==='string';break;
 case 'HIGHLIGHT_UPDATED':valid=typeof p.id==='string'&&typeof p.color==='string'&&/^#[0-9a-fA-F]{6}$/.test(p.color);break;
 case 'LINK_CLICKED':valid=typeof p.href==='string'&&/^(https?:|mailto:|#)/.test(p.href);break;
 case 'FONT_SIZE_CHANGED':valid=typeof p.size==='number'&&Number.isFinite(p.size)&&p.size>=12&&p.size<=40;break;
 case 'READER_ERROR':valid=typeof p.message==='string';break;
 }
 return valid?m as unknown as ReaderMessage:null;
 }catch{return null;}
}
