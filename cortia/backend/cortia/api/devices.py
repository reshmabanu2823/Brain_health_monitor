import asyncio
import time
from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from ..auth import current_user, resolve_user

router = APIRouter(prefix='/api', tags=['Hardware'])
class DeviceConfig(BaseModel):
    port: str = Field(min_length=1, max_length=256)
    sampling_hz: int = Field(default=500)
    channel: int = Field(default=0, ge=0, le=5)

@router.get('/devices/ports')
def ports(request: Request, user=Depends(current_user)):
    return request.app.state.acquisition.ports()

@router.get('/devices/status')
def status(request: Request, user=Depends(current_user)):
    return request.app.state.acquisition.snapshot(user.id)

@router.post('/devices/connect')
def connect(data: DeviceConfig, request: Request, user=Depends(current_user)):
    if data.sampling_hz not in (250,500):
        raise HTTPException(422, 'Sampling rate must match firmware: 250 or 500 Hz')
    try:
        return request.app.state.acquisition.connect(user.id, data.port, data.sampling_hz, data.channel)
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    except Exception:
        raise HTTPException(503, 'Serial port unavailable. Check permissions, cable and other serial applications.')

@router.post('/devices/disconnect')
def disconnect(request: Request, user=Depends(current_user)):
    try:
        request.app.state.acquisition.disconnect(user.id)
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    return {'state':'disconnected'}

@router.websocket('/live')
async def live(socket: WebSocket):
    origin = socket.headers.get('origin')
    settings = socket.app.state.settings
    allowed = set(settings.allowed_origins) | {f'http://{socket.headers.get("host")}', f'https://{socket.headers.get("host")}'}
    if origin and origin not in allowed:
        await socket.close(code=1008)
        return
    after = 0
    stream_id = None
    try:
        with socket.app.state.db() as db:
            user = resolve_user(db, socket.cookies.get('cortia_session'))
            if user is None:
                await socket.close(code=1008)
                return
            owner = user.id
        await socket.accept()
        while True:
            # Revocation/logout takes effect during an existing connection.
            with socket.app.state.db() as db:
                if resolve_user(db, socket.cookies.get('cortia_session')) is None:
                    await socket.close(code=1008)
                    return
            snapshot = socket.app.state.acquisition.snapshot(owner, after)
            if snapshot.get('stream_id') != stream_id:
                stream_id = snapshot.get('stream_id')
                after = 0
                snapshot = socket.app.state.acquisition.snapshot(owner, 0)
            if snapshot.get('samples'):
                after = snapshot['samples'][-1]['sequence']
            if snapshot['state'] == 'disconnected':
                after = 0
            await socket.send_json(snapshot)
            await asyncio.sleep(.15)
    except (WebSocketDisconnect, RuntimeError):
        return
