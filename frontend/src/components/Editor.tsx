import {useEditor,EditorContent} from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import {Table,TableRow,TableHeader,TableCell} from '@tiptap/extension-table';
import Image from '@tiptap/extension-image';
import {Extension} from '@tiptap/core';
import {useState} from 'react';
const References=Extension.create({name:'references',addGlobalAttributes(){return [{types:['paragraph','heading','bulletList','orderedList','listItem','table','image','blockquote','codeBlock'],attributes:{blockId:{default:null,parseHTML:el=>el.getAttribute('data-block-id'),renderHTML:attrs=>attrs.blockId?{'data-block-id':attrs.blockId}:{}},page:{default:null,parseHTML:el=>el.getAttribute('data-page'),renderHTML:attrs=>attrs.page?{'data-page':attrs.page}:{}}}}];}});
export function Editor({html,onSave}:{html:string;onSave:(value:string)=>Promise<void>}){
 const [source,setSource]=useState(false);const [busy,setBusy]=useState(false);
 const editor=useEditor({extensions:[StarterKit,References,Table.configure({resizable:false}),TableRow,TableHeader,TableCell,Image],content:html});
 if(!editor)return null;
 const save=async()=>{setBusy(true);try{await onSave(editor.getHTML());}finally{setBusy(false);}};
 return <div className="editor-pane"><div className="notice">Saving creates a revision. Highlights will be re-anchored; ambiguous matches become unresolved. Math and figure captions may change in the editor—review before saving.</div><div className="toolbar"><button onClick={()=>editor.chain().focus().toggleBold().run()}>Bold</button><button onClick={()=>editor.chain().focus().toggleItalic().run()}>Italic</button><button onClick={()=>editor.chain().focus().toggleHeading({level:2}).run()}>Heading</button><button onClick={()=>editor.chain().focus().toggleBulletList().run()}>List</button><button onClick={()=>editor.chain().focus().toggleOrderedList().run()}>1. List</button><button onClick={()=>editor.chain().focus().insertTable({rows:3,cols:3,withHeaderRow:true}).run()}>Table</button><button onClick={()=>{const src=window.prompt('Existing local asset path (assets/image-1.png)');if(src&&/^assets\/[\w-]+\.(png|jpg|jpeg|webp)$/.test(src))editor.chain().focus().setImage({src}).run();}}>Image</button><button onClick={()=>editor.chain().focus().undo().run()}>Undo</button><button onClick={()=>editor.chain().focus().redo().run()}>Redo</button><button onClick={()=>setSource(!source)}>Source</button><button className="primary" disabled={busy} onClick={()=>void save()}>{busy?'Saving…':'Save revision'}</button></div>{source?<pre className="source">{editor.getHTML()}</pre>:<EditorContent editor={editor}/>}</div>;
}
