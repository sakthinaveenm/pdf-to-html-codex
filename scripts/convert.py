"""Batch client for the running local API."""
import argparse
import json
import time
from pathlib import Path
from contextlib import ExitStack
import httpx
parser=argparse.ArgumentParser();parser.add_argument('pdfs',type=Path,nargs='+');parser.add_argument('--engine',choices=['AUTO','MARKER','DOCLING','LIGHTWEIGHT'],default='AUTO');parser.add_argument('--languages',default='eng');parser.add_argument('--url',default='http://127.0.0.1:8000');args=parser.parse_args()
with ExitStack() as stack,httpx.Client(base_url=args.url,timeout=120) as client:
    files=[('files',(path.name,stack.enter_context(path.open('rb')),'application/pdf')) for path in args.pdfs]
    response=client.post('/api/v1/jobs',files=files,data={'options':json.dumps({'engine':args.engine,'languages':args.languages.split('+')})});response.raise_for_status()
    for result in response.json()['results']:
        if 'error' in result: print(result);continue
        identity=result['job']['id']
        while True:
            job=client.get(f'/api/v1/jobs/{identity}').json()
            if job['status'] in ('COMPLETED','FAILED','CANCELED'):break
            time.sleep(1)
        print(json.dumps(job,ensure_ascii=False))
        if job['status']=='COMPLETED':
            export=client.get(f'/api/v1/documents/{identity}/export');export.raise_for_status()
            Path(identity+'.zip').write_bytes(export.content)
