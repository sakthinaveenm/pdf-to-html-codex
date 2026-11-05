export interface Annotation {
 id:string; documentId:string; revision:number; blockIds:string[];
 quote:{exact:string;prefix:string;suffix:string};
 position:{start:number;end:number;unit:'unicode-codepoint'};
 color:string; status:'resolved'|'unresolved';
}
export type ReaderEventType='READER_READY'|'TEXT_SELECTED'|'HIGHLIGHT_CREATED'|'HIGHLIGHT_REMOVED'|'HIGHLIGHT_UPDATED'|'LINK_CLICKED'|'FONT_SIZE_CHANGED'|'READER_ERROR';
export interface ReaderMessage {version:1;type:ReaderEventType;payload:Record<string,unknown>}
export function parseMessage(value:string):ReaderMessage|null {
 try {const data:unknown=JSON.parse(value); if(!data||typeof data!=='object')return null;
 const m=data as Record<string,unknown>;
 const types:ReaderEventType[]=['READER_READY','TEXT_SELECTED','HIGHLIGHT_CREATED','HIGHLIGHT_REMOVED','HIGHLIGHT_UPDATED','LINK_CLICKED','FONT_SIZE_CHANGED','READER_ERROR'];
 return m.version===1&&types.includes(m.type as ReaderEventType)&&m.payload!==null&&typeof m.payload==='object'&&!Array.isArray(m.payload)?m as unknown as ReaderMessage:null;
 }catch{return null;}
}
