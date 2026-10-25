"""FastAPI router for CORTIA AI Assistant."""
import os
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from .schemas import CapabilitiesResponse, ChatRequest, ChatResponse, ConversationSummary
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


@router.get("/conversations", response_model=List[ConversationSummary])
def list_conversations(
    limit: int = Query(30, ge=1, le=100),
    service: CortiaAIService = Depends(get_ai_service)
):
    items = service.store.list_conversations(limit=limit)
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
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return conv


@router.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: str, service: CortiaAIService = Depends(get_ai_service)):
    deleted = service.store.delete_conversation(conversation_id)
    if not deleted:
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
