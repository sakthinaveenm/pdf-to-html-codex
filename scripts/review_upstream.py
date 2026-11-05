"""Snapshot public upstream metadata without downloading or forking repositories."""
import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
repos=['datalab-to/marker','docling-project/docling','opendatalab/MinerU','pdf2htmlEX/pdf2htmlEX','mozilla/pdf.js','tesseract-ocr/tesseract','tesseract-ocr/tessdata','ueberdosis/tiptap','ProseMirror/prosemirror-view','hypothesis/client','react-native-webview/react-native-webview','messense/nh3','lxml/lxml','jsvine/pdfplumber']
def fetch(repo):
    try:
        request=urllib.request.Request('https://api.github.com/repos/'+repo,headers={'User-Agent':'local-pdf-evaluation'})
        with urllib.request.urlopen(request,timeout=20) as response:d=json.load(response)
        return {'project':repo,'url':d['html_url'],'pushedAt':d['pushed_at'],'archived':d['archived'],'license':(d.get('license') or {}).get('spdx_id'),'defaultBranch':d['default_branch']}
    except Exception as exc:return {'project':repo,'error':str(exc)}
results=list(ThreadPoolExecutor(max_workers=6).map(fetch,repos))
Path('docs/upstream-metadata.json').write_text(json.dumps({'reviewDate':'2026-11-05','projects':results},indent=2))
print(json.dumps(results,indent=2))
