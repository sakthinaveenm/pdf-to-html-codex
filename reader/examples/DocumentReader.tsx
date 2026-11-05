/** Install react-native-webview in your React Native app. Native testing is pending. */
import React,{useRef,useState} from 'react';
import {View,Button,Linking,Text} from 'react-native';
import {WebView,type WebViewMessageEvent} from 'react-native-webview';
import {parseMessage} from '../src/types';
import type {Annotation} from '../src/types';
interface Props {
 /** Absolute file URI to an extracted ZIP's reader.html. Assets remain beside it. */
 uri:string;
 /** Directory containing only this document and its assets. */
 directoryURI:string;
 annotations:Annotation[];
 onSave:(items:Annotation[])=>Promise<void>;
}
export function DocumentReader({uri,directoryURI,annotations,onSave}:Props){
 const ref=useRef<WebView>(null);const [items,setItems]=useState(annotations);const [selection,setSelection]=useState('');const [error,setError]=useState('');
 function invoke(method:'restore'|'create'|'fontSize'|'search',value:unknown){
  // Fixed method allowlist, JSON serialization and escaped angle brackets.
  const argument=JSON.stringify(value).replace(/</g,'\\u003c');
  ref.current?.injectJavaScript(`window.Reader && window.Reader.${method}(${argument}); true;`);
 }
 async function persist(next:Annotation[]){setItems(next);try{await onSave(next);}catch(e){setError(String(e));}}
 function message(event:WebViewMessageEvent){const msg=parseMessage(event.nativeEvent.data);if(!msg)return;
  if(msg.type==='READER_READY')invoke('restore',items);
  if(msg.type==='TEXT_SELECTED')setSelection(String(msg.payload.selectedText||''));
  if(msg.type==='HIGHLIGHT_CREATED')void persist([...items,msg.payload.annotation as Annotation]);
  if(msg.type==='HIGHLIGHT_REMOVED')void persist(items.filter(a=>a.id!==msg.payload.id));
  if(msg.type==='HIGHLIGHT_UPDATED')void persist(items.map(a=>a.id===msg.payload.id?{...a,color:String(msg.payload.color)}:a));
  if(msg.type==='LINK_CLICKED'&&/^https?:\/\//.test(String(msg.payload.href)))void Linking.openURL(String(msg.payload.href));
  if(msg.type==='READER_ERROR')setError(String(msg.payload.message));
 }
 return <View style={{flex:1}}><Text>{selection}</Text>{!!error&&<Text accessibilityRole="alert">{error}</Text>}<Button title="Highlight selection" onPress={()=>invoke('create','#ffdf70')}/><Button title="Larger text" onPress={()=>invoke('fontSize',24)}/><Button title="Search: language" onPress={()=>invoke('search','language')}/><WebView ref={ref} source={{uri}} originWhitelist={['file://*']} allowingReadAccessToURL={directoryURI} allowFileAccess allowUniversalAccessFromFileURLs={false} javaScriptEnabled onMessage={message} onShouldStartLoadWithRequest={request=>request.url===uri||request.url==='about:blank'} style={{flex:1}}/></View>;
}
