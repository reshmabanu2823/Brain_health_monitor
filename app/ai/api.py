"""FastAPI router for CORTIA AI Assistant (CliniQ)."""
import os
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
import database as cortia_db
from .config import (
    get_current_ai_config,
    test_cloud_provider,
    write_env_file,
)
from .schemas import (
    CapabilitiesResponse,
    ChatRequest,
    ChatResponse,
    ConversationSummary,
    CloudConfigResponse,
    CloudConfigRequest,
    CloudTestRequest,
    CloudTestResponse,
)
from .service import CortiaAIService

router = APIRouter(prefix="/api/ai", tags=["ai"])


def get_ai_service(request: Request) -> CortiaAIService:
    model_dir = getattr(request.app.state, "model_dir", None)
    if not model_dir:
        model_dir = os.getenv("BHM_MODEL_DIR", "model")
    eeg_service = getattr(request.app.state, "eeg", None)
    log_dir = Path(os.getenv("BHM_LOG_DIR", "logs"))
    db_path = str(log_dir / "cortia_ai.db")
    return CortiaAIService(
        db_path=db_path,
        model_dir=model_dir,
        eeg_service=eeg_service,
        app_state=request.app.state,
    )


@router.post("/chat", response_model=ChatResponse)
def chat_with_assistant(req: ChatRequest, service: CortiaAIService = Depends(get_ai_service)):
    try:
        return service.process_chat(req)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Assistant processing failed: {str(exc)}") from exc


@router.post("/conversations")
def new_conversation(service: CortiaAIService = Depends(get_ai_service)):
    conv_id = service.store.create_conversation("New Clinical Inquiry")
    return {"conversation_id": conv_id}


@router.get("/conversations", response_model=List[ConversationSummary])
def list_conversations(service: CortiaAIService = Depends(get_ai_service)):
    convs = service.store.list_conversations()
    return [
        ConversationSummary(
            id=c["id"],
            title=c["title"],
            created_at=c["created_at"],
            updated_at=c["updated_at"],
            message_count=c["message_count"],
        )
        for c in convs
    ]


@router.get("/conversations/{conversation_id}/messages")
def get_conversation_history(conversation_id: str, service: CortiaAIService = Depends(get_ai_service)):
    messages = service.store.get_messages(conversation_id)
    return {"conversation_id": conversation_id, "messages": messages}


@router.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: str, service: CortiaAIService = Depends(get_ai_service)):
    success = service.store.delete_conversation(conversation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    try:
        cortia_db.delete_conversation(conversation_id)
    except Exception:
        pass
    return {"status": "deleted", "conversation_id": conversation_id}


@router.delete("/conversations")
def clear_all_conversations(service: CortiaAIService = Depends(get_ai_service)):
    convs = service.store.list_conversations()
    for c in convs:
        service.store.delete_conversation(c["id"])
    try:
        conn = cortia_db.get_connection()
        conn.execute("DELETE FROM ai_messages")
        conn.execute("DELETE FROM ai_conversations")
        conn.commit()
        conn.close()
    except Exception:
        pass
    return {"status": "cleared"}


@router.get("/capabilities", response_model=CapabilitiesResponse)
def get_capabilities(service: CortiaAIService = Depends(get_ai_service)):
    return CapabilitiesResponse(**service.get_capabilities())


@router.get("/config/cloud", response_model=CloudConfigResponse)
def get_cloud_config():
    return get_current_ai_config()


@router.post("/config/cloud")
def save_cloud_config(req: CloudConfigRequest):
    try:
        success = write_env_file(
            provider=req.provider,
            api_key=req.api_key,
            model_name=req.model_name,
            endpoint_url=req.endpoint_url,
        )
        if success:
            return {"status": "saved", "provider": req.provider}
        raise HTTPException(status_code=500, detail="Failed to write configuration file")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/config/cloud/test", response_model=CloudTestResponse)
def test_cloud_connection(req: CloudTestRequest):
    return test_cloud_provider(
        provider=req.provider,
        api_key=req.api_key,
        model_name=req.model_name,
        endpoint_url=req.endpoint_url,
    )
