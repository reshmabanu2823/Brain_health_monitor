import hashlib
import io
import json
from pathlib import Path
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response
from ..auth import current_user, get_db
from ..db import uid
from ..models import MRIUpload, MRIPrediction
from ..mri.service import validate_image

router = APIRouter(prefix='/api/mri',tags=['MRI classifier'])

@router.get('/status')
def status(request:Request,user=Depends(current_user)):
    return request.app.state.mri.status()

@router.post('/predict',status_code=201)
def predict(request:Request,file:UploadFile=File(...),user=Depends(current_user),db=Depends(get_db)):
    content = file.file.read(request.app.state.settings.max_upload_bytes+1)
    try:
        image = validate_image(content,file.filename or 'image')
    except ValueError as exc:
        raise HTTPException(422,str(exc))
    try:
        result = request.app.state.mri.predict(image)
    except RuntimeError as exc:
        raise HTTPException(503,str(exc))
    upload_id = uid()
    relative = Path('mri')/f'{upload_id}.png'
    path = request.app.state.settings.data_dir/relative
    # Only decoded, normalized pixels retained. EXIF/DICOM identity stripped.
    image.save(path,format='PNG')
    path.chmod(0o600)
    record = MRIUpload(id=upload_id,user_id=user.id,filename='Uploaded MRI image',private_path=str(relative),sha256=hashlib.sha256(content).hexdigest())
    try:
        db.add(record)
        db.flush()
        db.add(MRIPrediction(upload_id=upload_id,result=result))
        db.commit()
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return dict(id=upload_id,created_at=record.created_at,filename=record.filename,result=result)

@router.get('/history')
def history(user=Depends(current_user),db=Depends(get_db)):
    rows = db.query(MRIUpload).filter_by(user_id=user.id).order_by(MRIUpload.created_at.desc()).limit(100).all()
    return [dict(id=r.id,created_at=r.created_at,filename=r.filename,result=db.get(MRIPrediction,r.id).result) for r in rows]

@router.get('/{mid}/image')
def image(mid:str,request:Request,user=Depends(current_user),db=Depends(get_db)):
    record = db.query(MRIUpload).filter_by(id=mid,user_id=user.id).first()
    if record is None:
        raise HTTPException(404,'MRI upload not found')
    path = request.app.state.settings.data_dir/record.private_path
    if not path.exists():
        raise HTTPException(404,'MRI image unavailable')
    return FileResponse(path,media_type='image/png',headers={'Cache-Control':'no-store'})

@router.get('/{mid}/report')
def report(mid:str,user=Depends(current_user),db=Depends(get_db)):
    record = db.query(MRIUpload).filter_by(id=mid,user_id=user.id).first()
    if record is None:
        raise HTTPException(404,'MRI upload not found')
    result = db.get(MRIPrediction,mid).result
    return Response(json.dumps(dict(id=mid,created_at=record.created_at,source_sha256=record.sha256,result=result),indent=2),
                    media_type='application/json',headers={'Content-Disposition':f'attachment; filename="cortia-mri-{mid}.json"'})
