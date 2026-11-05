import {test,expect} from '@playwright/test';
import path from 'node:path';
test('upload, convert, highlight, reload, edit and export',async({page})=>{
 await page.goto('/');await expect(page.getByText('Every language.')).toBeVisible();
 await page.getByLabel('Conversion engine').selectOption('LIGHTWEIGHT');
 const uploaded=page.waitForResponse(r=>r.url().endsWith('/api/v1/jobs')&&r.request().method()==='POST');
 await page.locator('input[type=file]').setInputFiles(path.resolve('../samples/digital-english.pdf'));
 const jobId=(await (await uploaded).json()).results[0].job.id as string;
 await expect.poll(async()=> (await (await page.request.get(`/api/v1/jobs/${jobId}`)).json()).status,{timeout:45000}).toBe('COMPLETED');
 await page.goto(`/documents/${jobId}`);
 const reader=page.frameLocator('iframe[title="Selectable document reader"]');
 await expect(reader.locator('article')).toContainText('Select this sentence');
 await reader.locator('article').evaluate(root=>{const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);let node:Node|null;while(node=walker.nextNode()){if(node.textContent?.includes('Select this sentence')){const range=document.createRange();range.setStart(node,0);range.setEnd(node,20);const s=window.getSelection()!;s.removeAllRanges();s.addRange(range);break;}}});
 await expect(page.getByRole('button',{name:'Highlight selection'})).toBeEnabled();await page.getByRole('button',{name:'Highlight selection'}).click();
 await expect(page.locator('.annotation')).toHaveCount(1);await page.reload();await expect(page.locator('.annotation')).toHaveCount(1);
 await page.getByLabel('Font size').fill('24');await expect(reader.locator('article')).toHaveCSS('font-size','24px');
 await page.getByRole('button',{name:'Edit',exact:true}).click();await expect(page.locator('.tiptap')).toContainText('Language brings ideas to life.');
 await page.getByRole('button',{name:'Save revision'}).click();await expect(page.getByText('DOCUMENT WORKSPACE / REVISION 2')).toBeVisible();
 await page.getByRole('button',{name:'Export & quality'}).click();await expect(page.getByRole('link',{name:/Complete package/})).toBeVisible();
});
for(const fallback of [false,true])test(`reader Unicode, cross-block selection and restore (fallback ${fallback})`,async({page})=>{
 await page.goto('/');const script=await (await page.request.get('/reader.js')).text();
 await page.setContent('<article data-document-id="test"><p data-block-id="b1">தமிழ் <strong>bold 😀</strong></p><p data-block-id="b2">हिन्दी text</p></article>');
 if(fallback)await page.evaluate(()=>Object.defineProperty(CSS,'highlights',{value:undefined,configurable:true}));
 await page.addScriptTag({content:script});
 const result=await page.evaluate(()=>{const w=window as unknown as {Reader:{create:()=>{quote:{exact:string}};restore:(a:unknown[])=>void;fontSize:(n:number)=>void}};const article=document.querySelector('article')!;const before=article.textContent;const range=document.createRange();range.setStart(article.querySelector('p')!.firstChild!,0);range.setEnd(article.querySelectorAll('p')[1].firstChild!,6);const s=getSelection()!;s.removeAllRanges();s.addRange(range);const a=w.Reader.create();w.Reader.fontSize(30);w.Reader.restore([JSON.parse(JSON.stringify(a))]);return {before,after:article.textContent,quote:a.quote.exact,paragraphs:article.querySelectorAll('p').length};});
 expect(result.before).toBe(result.after);expect(result.quote).toContain('😀हिन्दी');expect(result.paragraphs).toBe(2);
});
test('source comparison uses PDF.js and preserves selectable HTML',async({page})=>{
 await page.goto('/');const response=await page.request.get('/api/v1/jobs');const jobs=await response.json();const job=jobs.items.find((j:{status:string;filename:string})=>j.status==='COMPLETED'&&j.filename==='digital-english.pdf');expect(job).toBeTruthy();
 await page.goto(`/documents/${job.id}`);await page.getByRole('button',{name:'Compare',exact:true}).click();await expect(page.getByLabel('Original PDF page 1')).toBeVisible();
 await expect.poll(async()=>page.getByLabel('Original PDF page 1').evaluate(c=>(c as HTMLCanvasElement).width)).toBeGreaterThan(100);
 await page.getByLabel('Source page').fill('2');await expect(page.getByLabel('Original PDF page 2')).toBeVisible();
 await expect(page.frameLocator('iframe[title="Converted HTML comparison"]').locator('article')).toContainText('A second page');
});
test('WebView bridge emits versioned events without native services',async({page})=>{
 await page.goto('/');const script=await(await page.request.get('/reader.js')).text();await page.setContent('<article data-document-id="bridge"><p data-block-id="b">தமிழ் English</p><a href="https://example.org">Link</a></article>');
 await page.evaluate(()=>{const w=window as unknown as {messages:unknown[];ReactNativeWebView:{postMessage:(s:string)=>void}};w.messages=[];w.ReactNativeWebView={postMessage:s=>w.messages.push(JSON.parse(s))};});await page.addScriptTag({content:script});
 await page.locator('a').click();const types=await page.evaluate(()=> (window as unknown as {messages:{version:number;type:string}[]}).messages.map(m=>[m.version,m.type]));expect(types).toContainEqual([1,'READER_READY']);expect(types).toContainEqual([1,'LINK_CLICKED']);
});
