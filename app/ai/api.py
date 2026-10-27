"""FastAPI router for CORTIA AI Assistant."""
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
def new_conversation(provider: str = "local"):
    conv_id = cortia_db.create_conversation(provider=provider)
    return {"conversation_id": conv_id}


@router.get("/conversations", response_model=List[ConversationSummary])
def list_conversations(
    limit: int = Query(30, ge=1, le=100),
    service: CortiaAIService = Depends(get_ai_service)
):
    items = service.store.list_conversations(limit=limit)
    if not items:
        db_items = cortia_db.get_conversations(limit=limit)
        return [
            ConversationSummary(
                id=item["id"],
                title=item["title"],
                created_at=item["created_at"],
                updated_at=item["updated_at"],
                message_count=0,
            )
            for item in db_items
        ]
    return [
        ConversationSummary(
            id=item["id"],
            title=item["title"],
            created_at=item["created_at"],
            updated_at=item["updated_at"],
            message_count=item.get("message_count", 0),
        )
        for item in items
    ]


@router.get("/conversations/{conversation_id}")
def get_conversation_history(conversation_id: str, service: CortiaAIService = Depends(get_ai_service)):
    conv = service.store.get_conversation(conversation_id)
    if not conv:
        # Check database.py
        messages = cortia_db.get_messages(conversation_id)
        if not messages:
            raise HTTPException(status_code=404, detail="Conversation not found.")
        return {"id": conversation_id, "messages": messages}
    return conv


@router.get("/conversations/{conv_id}/messages")
def list_messages(conv_id: str):
    return cortia_db.get_messages(conv_id)


@router.post("/conversations/{conv_id}/messages")
def add_message(conv_id: str, body: dict):
    msg_id = cortia_db.insert_message(
        conversation_id=conv_id,
        role=body["role"],
        content=body["content"],
        citations=body.get("citations", []),
    )
    return {"message_id": msg_id}


@router.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: str, service: CortiaAIService = Depends(get_ai_service)):
    deleted_store = service.store.delete_conversation(conversation_id)
    db_existed = False
    try:
        conn = cortia_db.get_connection()
        row = conn.execute("SELECT id FROM ai_conversations WHERE id = ?", (conversation_id,)).fetchone()
        if row:
            db_existed = True
        conn.close()
        cortia_db.delete_conversation(conversation_id)
    except Exception:
        pass
    if not deleted_store and not db_existed:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return {"status": "deleted", "conversation_id": conversation_id}


@router.post("/clear")
def clear_all_conversations(service: CortiaAIService = Depends(get_ai_service)):
    service.store.clear_all()
    return {"status": "cleared"}


@router.get("/capabilities", response_model=CapabilitiesResponse)
def get_capabilities(service: CortiaAIService = Depends(get_ai_service)):
    provider_name = type(service.provider).__name__
    is_cloud = provider_name in ("GeminiProvider", "OpenAIProvider")
    return CapabilitiesResponse(
        assistant_name="CORTIA AI",
        version="2.0",
        provider_configured=is_cloud,
        active_provider=provider_name,
        grounded_tools=[
            "get_eeg_hardware_status",
            "get_latest_eeg_summary",
            "get_eeg_session_summary",
            "get_model_registry",
            "get_latest_mri_scan",
            "get_mri_scan_by_id",
            "get_verified_model_evaluations",
            "get_system_health",
        ],
        starter_prompts=[
            "Explain the difference between raw and filtered EEG signals.",
            "Summarize my latest EEG recording.",
            "Explain the relative alpha power in this session.",
            "Why was this recording marked as insufficient quality?",
            "Explain how Grad-CAM works.",
            "Summarize the results of my latest MRI analysis.",
            "Which AI models are currently available?",
            "Explain the limitations of my current EEG hardware.",
        ],
        disclaimer="CORTIA AI is a research assistant grounded in scientific literature and local application telemetry. It does not provide medical diagnoses.",
    )


@router.get("/config", response_model=CloudConfigResponse)
def get_cloud_config():
    """Retrieve current AI provider configuration and available cloud models."""
    cfg = get_current_ai_config()
    return CloudConfigResponse(**cfg)


@router.post("/config", response_model=CloudConfigResponse)
def update_cloud_config(req: CloudConfigRequest, service: CortiaAIService = Depends(get_ai_service)):
    """Save cloud AI provider and API key, updating .env and reloading service."""
    updates = {"CORTIA_AI_PROVIDER": req.provider}
    if req.api_key is not None and req.api_key.strip():
        key = req.api_key.strip()
        if req.provider == "gemini":
            updates["GEMINI_API_KEY"] = key
            updates["CORTIA_AI_API_KEY"] = key
        elif req.provider == "groq":
            updates["GROQ_API_KEY"] = key
        elif req.provider == "openai":
            updates["OPENAI_API_KEY"] = key
        elif req.provider == "openrouter":
            updates["OPENROUTER_API_KEY"] = key

    if req.model_name and req.model_name.strip():
        model = req.model_name.strip()
        if req.provider == "gemini":
            updates["CORTIA_GEMINI_MODEL"] = model
        elif req.provider == "groq":
            updates["CORTIA_GROQ_MODEL"] = model
        elif req.provider == "openai":
            updates["CORTIA_OPENAI_MODEL"] = model
        elif req.provider == "openrouter":
            updates["CORTIA_OPENROUTER_MODEL"] = model

    # Write to .env and update os.environ
    write_env_file(updates)
    for k, v in updates.items():
        os.environ[k] = v

    # Reload active provider immediately on service
    service.reload_provider()

    cfg = get_current_ai_config()
    return CloudConfigResponse(**cfg)


@router.post("/config/test", response_model=CloudTestResponse)
def test_cloud_key(req: CloudTestRequest):
    """Test connection to cloud provider without persisting."""
    res = test_cloud_provider(req.provider, req.api_key or "", req.model_name)
    return CloudTestResponse(**res)
