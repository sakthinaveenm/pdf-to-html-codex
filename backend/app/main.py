import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException
from app.config.settings import settings
from app.db.database import initialize
from app.api.routes import router
from app.workers.queue import queue

logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(name)s %(message)s')
@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize()
    from app.services.documents.deletion import purge_deleted_files
    purge_deleted_files()
    queue.start()
    yield
    queue.close()

app=FastAPI(title='Multilingual PDF to HTML',version='0.1.0',lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=settings.cors_origins,allow_methods=['GET','POST','PUT','PATCH','DELETE'],allow_headers=['Content-Type'])
@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    return JSONResponse({'error':{'code':exc.status_code,'message':exc.detail}},status_code=exc.status_code)
@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    return JSONResponse({'error':{'code':422,'message':str(exc)}},status_code=422)
@app.middleware('http')
async def security_headers(request: Request, call_next):
    origin=request.headers.get('origin')
    if origin and origin not in settings.cors_origins and origin not in ('http://127.0.0.1:8000','http://localhost:8000'):
        return JSONResponse({'error':{'code':403,'message':'Origin is not allowed.'}},status_code=403)
    length=request.headers.get('content-length')
    if length and int(length)>settings.max_upload_mb*1024**2*20+1024**2:
        return JSONResponse({'error':{'code':413,'message':'Batch upload exceeds size limit.'}},status_code=413)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='no-referrer'
    return response
app.include_router(router)
from app.api.pages import router as page_router
app.include_router(page_router)
