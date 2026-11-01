import asyncio
import logging
import os
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from .config import Settings, ROOT
from .db import setup
from .eeg.acquisition import Acquisition
from .mri.service import MRIService
from .security import BodyLimit
from . import auth
from .api import devices, sessions, mri, insights

log = logging.getLogger('cortia')


def create_app(settings=None):
    settings = settings or Settings()
    settings.data_dir = Path(settings.data_dir)
    engine, factory = setup(settings)
    acquisition = Acquisition(factory,settings.data_dir)
    @asynccontextmanager
    async def lifespan(app):
        yield
        await asyncio.to_thread(acquisition.disconnect)
        engine.dispose()
    app = FastAPI(docs_url=None,redoc_url=None,title='CORTIA API',version='0.1.0',description='Personal EEG monitoring and separate MRI image classification. Research support, not diagnosis.',lifespan=lifespan)
    app.state.settings,app.state.db = settings,factory
    app.state.acquisition,app.state.mri = acquisition,MRIService(settings.model_dir)
    app.state.auth_attempts = defaultdict(deque)
    app.add_middleware(BodyLimit,limit=settings.max_upload_bytes+65536)
    app.add_middleware(TrustedHostMiddleware,allowed_hosts=['localhost','127.0.0.1','[::1]','testserver'])
    @app.middleware('http')
    async def security(request:Request,call_next):
        if request.method in ('POST','PUT','PATCH','DELETE'):
            origin = request.headers.get('origin')
            allowed = set(settings.allowed_origins) | {str(request.base_url).rstrip('/')}
            if origin and origin not in allowed:
                return JSONResponse({'detail':'Origin not allowed'},status_code=403)
            length = request.headers.get('content-length')
            if length and (not length.isdigit() or int(length) > settings.max_upload_bytes+65536):
                return JSONResponse({'detail':'Request exceeds upload limit'},status_code=413)
        response = await call_next(request)
        response.headers.update({'X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY','Referrer-Policy':'no-referrer',
                                 'Cache-Control':'no-store','Permissions-Policy':'camera=(), microphone=(), geolocation=()',
                                 'Content-Security-Policy':"default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self' ws://localhost:* ws://127.0.0.1:*; frame-ancestors 'none'"})
        return response
    @app.exception_handler(Exception)
    async def internal_error(request,exc):
        log.error('Request failed: %s',type(exc).__name__)
        return JSONResponse({'detail':'Operation failed. Check local server logs and storage availability.'},status_code=500)
    @app.get('/api/health',tags=['System'])
    def health():
        return {'product':'CORTIA','status':'ok','hardware_verified':False,'clinical_validation':False}
    for router in (auth.router,devices.router,sessions.router,mri.router,insights.router):
        app.include_router(router)
    docs_dir = Path(__file__).parent/'static/docs'
    app.mount('/docs-assets',StaticFiles(directory=docs_dir),name='docs-assets')
    @app.get('/docs',include_in_schema=False)
    def documentation():
        return FileResponse(docs_dir/'index.html')
    dist = ROOT/'frontend/dist'
    if dist.exists():
        app.mount('/assets',StaticFiles(directory=dist/'assets'),name='assets')
        @app.get('/',include_in_schema=False)
        def frontend():
            return FileResponse(dist/'index.html')
    return app

# Factory mode prevents DB creation when importing tests.
