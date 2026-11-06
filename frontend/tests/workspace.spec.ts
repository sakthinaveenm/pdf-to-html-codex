import {test,expect,type Page} from '@playwright/test';
import {fileURLToPath} from 'node:url';
async function upload(page:Page){
 await page.goto('/');await page.getByText('Conversion and export settings',{exact:true}).click();await page.getByLabel('Conversion engine').selectOption('LIGHTWEIGHT');
 const response=page.waitForResponse(r=>r.url().endsWith('/api/v1/jobs')&&r.request().method()==='POST');
 await page.locator('input[type=file]').setInputFiles(fileURLToPath(new URL('../../samples/digital-image.pdf',import.meta.url)));
 const id=(await(await response).json()).results[0].job.id as string;
 await expect.poll(async()=>(await(await page.request.get(`/api/v1/books/${id}/pages`)).json()).completed,{timeout:45000}).toBe(2);
 await expect(page.frameLocator('iframe[title="Converted HTML page"]').locator('article')).toBeVisible();return id;
}
test('page isolation, rich clipboard, editing, reset and selected export',async({page,context})=>{
 await context.grantPermissions(['clipboard-read','clipboard-write']);const id=await upload(page);
 const preview=page.frameLocator('iframe[title="Converted HTML page"]');await expect(preview.locator('img')).toHaveCount(1);
 expect(await preview.locator('img').evaluate(img=>(img as HTMLImageElement).naturalWidth)).toBeGreaterThan(0);
 await page.getByText('HTML source for this page',{exact:true}).click();const source=page.getByLabel('Page HTML source');
 const first=await source.inputValue();expect(first).toContain('data:image/png;base64,');expect(first).not.toContain('Second page remains editable');expect(first).not.toContain('<html');
 await page.getByRole('button',{name:'Copy HTML Source',exact:true}).click();await expect.poll(()=>page.evaluate(()=>navigator.clipboard.readText())).toBe(first);
 await page.getByRole('button',{name:'Copy Formatted Content',exact:true}).click();await expect(page.getByText('Formatted page content copied. Paste into your HTML editor.',{exact:true})).toBeVisible();
 const rich=await page.evaluate(async()=>{const items=await navigator.clipboard.read();return(await items[0].getType('text/html')).text();});expect(rich).toContain('data:image/png;base64,');
 // Paste the actual clipboard into an ordinary editor and exercise DOM ranges.
 const target=await context.newPage();await target.goto('/');await target.setContent('<div contenteditable="true" id="editor"></div>');await target.locator('#editor').focus();await target.keyboard.press(process.platform==='darwin'?'Meta+V':'Control+V');
 await expect(target.locator('#editor img')).toHaveCount(1);expect(await target.locator('#editor img').evaluate(img=>(img as HTMLImageElement).naturalWidth)).toBeGreaterThan(0);
 expect(await target.locator('#editor').evaluate(root=>{const range=document.createRange();range.selectNodeContents(root);const s=getSelection()!;s.removeAllRanges();s.addRange(range);return s.toString().length;})).toBeGreaterThan(10);await target.close();
 await page.getByRole('button',{name:'Next page',exact:true}).click();await expect(source).toHaveValue(/Second page remains editable/);expect(await source.inputValue()).not.toContain('data:image/');
 await page.getByRole('button',{name:'Edit HTML',exact:true}).click();await page.locator('.tiptap p').first().click();await page.keyboard.press('End');await page.keyboard.type(' correction');
 await expect(page.getByRole('button',{name:'Copy HTML Source',exact:true})).toBeDisabled();await page.getByRole('button',{name:'Save edits',exact:true}).click();await expect(source).toHaveValue(/correction/);
 await page.getByRole('button',{name:'Previous page',exact:true}).click();await expect(source).toHaveValue(first);await page.getByRole('button',{name:'Next page',exact:true}).click();await expect(source).toHaveValue(/correction/);
 page.once('dialog',d=>d.accept());await page.getByRole('button',{name:'Reset to Converted Version',exact:true}).click();await expect(source).not.toHaveValue(/correction/);
 await page.getByLabel('Pages to export').fill('1,2');await expect(page.getByRole('link',{name:'Export selected'})).toHaveAttribute('href',/pages=1,2/);
 expect((await page.request.get(`/api/v1/books/${id}/export?pages=2`)).status()).toBe(200);expect(new URL(page.url()).pathname).toBe('/');
});
test('deletion removes the book and its page records',async({page})=>{
 const id=await upload(page);page.once('dialog',d=>d.accept());await page.getByRole('button',{name:'Delete book',exact:true}).click();await expect.poll(async()=>(await page.request.get(`/api/v1/books/${id}/pages`)).status()).toBe(404);
});
for(const fallback of [false,true])test(`reader Unicode, cross-block selection and restore (fallback ${fallback})`,async({page})=>{
 await page.goto('/');const script=await (await page.request.get('/reader.js')).text();
 await page.setContent('<article data-document-id="test"><p data-block-id="b1">தமிழ் <strong>bold 😀</strong></p><p data-block-id="b2">हिन्दी text</p></article>');
 if(fallback)await page.evaluate(()=>Object.defineProperty(CSS,'highlights',{value:undefined,configurable:true}));
 await page.addScriptTag({content:script});
 const result=await page.evaluate(()=>{const w=window as unknown as {Reader:{create:()=>{quote:{exact:string}};restore:(a:unknown[])=>void;fontSize:(n:number)=>void}};const article=document.querySelector('article')!;const before=article.textContent;const range=document.createRange();range.setStart(article.querySelector('p')!.firstChild!,0);range.setEnd(article.querySelectorAll('p')[1].firstChild!,6);const s=getSelection()!;s.removeAllRanges();s.addRange(range);const a=w.Reader.create();w.Reader.fontSize(30);w.Reader.restore([JSON.parse(JSON.stringify(a))]);return {before,after:article.textContent,quote:a.quote.exact,paragraphs:article.querySelectorAll('p').length};});
 expect(result.before).toBe(result.after);expect(result.quote).toContain('😀हिन्दी');expect(result.paragraphs).toBe(2);
});
test('WebView bridge emits versioned events without native services',async({page})=>{
 await page.goto('/');const script=await(await page.request.get('/reader.js')).text();await page.setContent('<article data-document-id="bridge"><p data-block-id="b">தமிழ் English</p><a href="https://example.org">Link</a></article>');
 await page.evaluate(()=>{const w=window as unknown as {messages:unknown[];ReactNativeWebView:{postMessage:(s:string)=>void}};w.messages=[];w.ReactNativeWebView={postMessage:s=>w.messages.push(JSON.parse(s))};});await page.addScriptTag({content:script});
 await page.locator('a').click();const types=await page.evaluate(()=> (window as unknown as {messages:{version:number;type:string}[]}).messages.map(m=>[m.version,m.type]));expect(types).toContainEqual([1,'READER_READY']);expect(types).toContainEqual([1,'LINK_CLICKED']);
});

test('comparison sizing, synchronized scrolling and page scroll reset',async({page})=>{
 await upload(page);
 const original=page.getByLabel('Original PDF preview');
 const frame=page.frameLocator('iframe[title="Converted HTML page"]');
 await expect.poll(()=>original.locator('canvas').evaluate(c=>(c as HTMLCanvasElement).width)).toBeGreaterThan(300);
 const widths=await page.locator('.page-comparison').evaluate(root=>{const canvas=root.querySelector('canvas')!;const iframe=root.querySelector('iframe')!;return [canvas.getBoundingClientRect().width,iframe.contentDocument!.querySelector('article')!.getBoundingClientRect().width];});
 expect(Math.abs(widths[0]-widths[1])).toBeLessThan(2);
 await original.evaluate(element=>{element.scrollTop=element.scrollHeight;});
 await expect.poll(()=>page.locator('iframe[title="Converted HTML page"]').evaluate(frame=>(frame as HTMLIFrameElement).contentWindow!.scrollY)).toBeGreaterThan(20);
 await page.getByRole('button',{name:'Next page',exact:true}).click();
 await expect(frame.locator('section[data-page="2"]')).toBeVisible();
 await expect.poll(()=>original.evaluate(element=>element.scrollTop)).toBe(0);
 await expect.poll(()=>page.locator('iframe[title="Converted HTML page"]').evaluate(frame=>(frame as HTMLIFrameElement).contentWindow!.scrollY)).toBe(0);
});

test('inline font sizes survive a TipTap save',async({page})=>{
 const id=await upload(page);const endpoint=`/api/v1/books/${id}/pages/1`;
 const detail=await(await page.request.get(endpoint)).json();const original=await(await page.request.get(endpoint+'/html')).text();
 const changed=await page.evaluate(source=>{const doc=new DOMParser().parseFromString(source,'text/html');const p=doc.querySelector('p')!;p.innerHTML='<span style="font-size: 0.75em; word-spacing: 0.125rem; display: inline-block">'+p.innerHTML+'</span>';return doc.body.innerHTML;},original);
 expect((await page.request.put(endpoint+'/revisions',{data:{baseRevision:detail.revision,html:changed}})).status()).toBe(200);
 await expect.poll(async()=>(await(await page.request.get(endpoint)).json()).revision).toBe(2);
 await page.getByRole('button',{name:'Refresh Preview',exact:true}).click();await page.getByRole('button',{name:'Edit HTML',exact:true}).click();
 await expect(page.locator('.tiptap span[style*="0.75em"]').first()).toBeVisible();
 await page.getByRole('button',{name:'Save edits',exact:true}).click();
 await expect.poll(async()=>(await(await page.request.get(endpoint)).json()).revision).toBe(3);
 const saved=await(await page.request.get(endpoint+'/html')).text();expect(saved).toContain('0.75em');expect(saved).toContain('word-spacing: 0.125rem');
});
