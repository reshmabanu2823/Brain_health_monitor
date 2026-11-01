from fastapi import APIRouter, Depends, Request, HTTPException
from pydantic import BaseModel
from ..auth import current_user, get_db
from ..models import Explanation
from ..services.explanations import explain
from .sessions import recording, session_data, baseline_comparison

router = APIRouter(prefix='/api',tags=['Evidence explanations'])
class InsightRequest(BaseModel):
    use_external_ai: bool = False
    consent_to_send_metrics: bool = False

@router.post('/sessions/{sid}/explanations')
def generate(sid:str,data:InsightRequest,request:Request,user=Depends(current_user),db=Depends(get_db)):
    row = recording(db,sid,user)
    if data.use_external_ai and not data.consent_to_send_metrics:
        raise HTTPException(422,'Explicit consent required to send curated metrics to configured external AI')
    try:
        result = explain(session_data(row),baseline_comparison(db,row),request.app.state.settings,data.use_external_ai)
    except ValueError as exc:
        raise HTTPException(422,str(exc))
    except Exception:
        raise HTTPException(502,'External explanation service unavailable or returned invalid evidence selections')
    item = Explanation(user_id=user.id,session_id=sid,evidence_digest=result['evidence_digest'],result=result)
    db.add(item)
    db.commit()
    return dict(id=item.id,created_at=item.created_at,**result)

@router.get('/sessions/{sid}/explanations')
def history(sid:str,user=Depends(current_user),db=Depends(get_db)):
    recording(db,sid,user)
    return [dict(id=r.id,created_at=r.created_at,**r.result) for r in db.query(Explanation).filter_by(user_id=user.id,session_id=sid).order_by(Explanation.created_at.desc()).limit(100).all()]
