"""EEG routes in the existing FastAPI process, separate from MRI routes."""
from typing import Literal
from urllib.parse import urlsplit
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from serial.tools import list_ports

router = APIRouter()


def service(request: Request):
    s = getattr(request.app.state, 'eeg', None)
    if s is None:
        raise HTTPException(503, 'EEG service unavailable')
    return s


def local_control(request: Request):
    origin = request.headers.get('origin')
    if origin and urlsplit(origin).netloc != request.headers.get('host'):
        raise HTTPException(403, 'Device controls require same-origin requests')


class ConnectRequest(BaseModel):
    source: Literal['serial', 'simulated']
    port: str | None = Field(default=None, max_length=256)


@router.get('/api/device/ports')
def ports():
    return [{'device': p.device, 'description': p.description} for p in list_ports.comports()]


@router.get('/api/device/status')
def status(s=Depends(service)):
    return {k:v for k,v in s.snapshot().items() if k not in ('samples','analysis','prediction')}


@router.post('/api/device/connect', dependencies=[Depends(local_control)])
def connect(body: ConnectRequest, s=Depends(service)):
    if body.source == 'serial' and body.port not in {p.device for p in list_ports.comports()}:
        raise HTTPException(422, 'Choose an available serial port from /api/device/ports')
    try:
        s.connect(body.source, body.port)
        return {'state':'starting','source':body.source}
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post('/api/device/disconnect', dependencies=[Depends(local_control)])
def disconnect(s=Depends(service)):
    try:
        s.disconnect()
        return {'state':'disconnected'}
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc


@router.get('/api/eeg/live')
def live(s=Depends(service)):
    return s.snapshot()


@router.get('/api/eeg/model/info')
def model_info(s=Depends(service)):
    if s.model is None:
        return {'available':False,'reason':'No EEG model installed; labeled dataset required'}
    # No training subject identifiers or source-file paths in the public response.
    return {k:v for k,v in s.model.info.items() if k in ('available','reason','name','version','task','labels','feature_names','preprocessing','units','limitation')}


@router.post('/api/eeg/recordings', dependencies=[Depends(local_control)])
def start_recording(s=Depends(service)):
    try:
        return {'id':s.start_recording()}
    except ValueError as exc:
        raise HTTPException(409,str(exc)) from exc


@router.post('/api/eeg/recordings/stop', dependencies=[Depends(local_control)])
def stop_recording(s=Depends(service)):
    try:
        return {'id':s.stop_recording()}
    except ValueError as exc:
        raise HTTPException(409,str(exc)) from exc


@router.get('/api/eeg/recordings')
def recordings(limit: int=Query(100,ge=1,le=100), s=Depends(service)):
    return s.store.list(limit)


@router.get('/api/eeg/recordings/{rid}/export')
def export(rid: str, s=Depends(service)):
    try:
        session=s.store.get(rid)
    except KeyError as exc:
        raise HTTPException(404,'Recording not found') from exc
    if session['status']=='recording':
        raise HTTPException(409,'Stop recording before exporting a stable snapshot')
    return StreamingResponse(s.store.export(rid),media_type='text/csv',headers={'Content-Disposition':f'attachment; filename="eeg-{session["id"]}.csv"'})
