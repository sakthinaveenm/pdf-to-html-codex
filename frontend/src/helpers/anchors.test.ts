import {describe,it,expect} from 'vitest';
import {codepoints,utf16ToCodepoint,codepointToUtf16,resolveAnchor} from '../../../reader/src/anchors';
import {parseMessage} from '../../../reader/src/types';
import type {Annotation} from '../../../reader/src/types';
describe('Unicode anchors',()=>{
 it.each(['Tamil தமிழ்','क्‍ष','😀a𐐷','العربية','中文','മലയാളം'])('round trips codepoint offsets for %s',text=>{for(let i=0;i<=codepoints(text);i++)expect(utf16ToCodepoint(text,codepointToUtf16(text,i))).toBe(i);});
 it('rejects a split surrogate',()=>expect(()=>utf16ToCodepoint('😀',1)).toThrow());
 const a:Annotation={id:'test',documentId:'d',revision:1,blockIds:['b'],quote:{exact:'தமிழ்',prefix:'hello ',suffix:'!'},position:{start:6,end:11,unit:'unicode-codepoint'},color:'#ffdf70',status:'resolved'};
 it('reanchors after editing',()=>expect(resolveAnchor(a,'new hello தமிழ்!',2).position.start).toBe(10));
 it('does not guess between repeated quotes',()=>expect(resolveAnchor({...a,quote:{exact:'word',prefix:'',suffix:''}},'word word',2).status).toBe('unresolved'));
 it('validates bridge envelopes',()=>{expect(parseMessage('{"version":2,"type":"READER_READY","payload":{}}')).toBeNull();expect(parseMessage('{"version":1,"type":"READER_READY","payload":{}}')?.type).toBe('READER_READY');});
});
