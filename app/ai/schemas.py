"""Pydantic schemas for CORTIA AI Assistant (incorporating Medicluster CliniQ)."""
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class Citation(BaseModel):
    title: str
    source_type: str  # 'peer_reviewed_paper', 'textbook', 'dataset_spec', 'documentation'
    url: Optional[str] = None
    doi: Optional[str] = None
    publication_year: Optional[int] = None
    relevance_snippet: str
    verified: bool = True


class AnalysisReference(BaseModel):
    type: Literal["mri", "eeg"]
    id: str
    title: str
    deep_link: str


class ChatMessage(BaseModel):
    id: Optional[str] = None
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: Optional[str] = None
    citations: Optional[List[Citation]] = None
    analysis_references: Optional[List[AnalysisReference]] = None
    tool_invocations: Optional[List[str]] = None
    simulated_warning: Optional[str] = None
    image_base64: Optional[str] = None
    drug_interactions: Optional[Dict[str, Any]] = None
    specialist: Optional[str] = None


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    conversation_id: Optional[str] = Field(None, max_length=64)
    # Context-aware analysis parameters passed server-side
    analysis_type: Optional[Literal["mri", "eeg"]] = None
    analysis_id: Optional[str] = Field(None, max_length=64)
    # Medicluster CliniQ extensions
    language: Optional[str] = Field("en", max_length=10)
    image_base64: Optional[str] = None
    media_type: Optional[str] = Field("image/jpeg", max_length=32)
    medications: Optional[List[str]] = None


class ChatResponse(BaseModel):
    conversation_id: str
    message: ChatMessage
    provider_mode: str  # e.g., 'external_llm (gemini)', 'local_grounded_engine', 'cliniq_rag'
    suggested_followups: List[str] = Field(default_factory=list)
    drug_interactions: Optional[Dict[str, Any]] = None
    specialist: Optional[str] = None


class ConversationSummary(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int


class CapabilitiesResponse(BaseModel):
    assistant_name: str = "CORTIA CliniQ"
    version: str = "2.5"
    provider_configured: bool
    active_provider: str
    grounded_tools: List[str]
    starter_prompts: List[str]
    supported_languages: List[Dict[str, str]]
    disclaimer: str


class CloudConfigResponse(BaseModel):
    active_provider: str
    provider_name: str
    model_name: Optional[str] = None
    is_cloud: bool
    has_api_key: bool


class CloudConfigRequest(BaseModel):
    provider: Literal["openai", "gemini", "anthropic", "groq", "ollama", "none"]
    api_key: Optional[str] = None
    model_name: Optional[str] = None
    endpoint_url: Optional[str] = None


class CloudTestRequest(BaseModel):
    provider: Literal["openai", "gemini", "anthropic", "groq", "ollama"]
    api_key: Optional[str] = None
    model_name: Optional[str] = None
    endpoint_url: Optional[str] = None


class CloudTestResponse(BaseModel):
    success: bool
    latency_ms: Optional[int] = None
    model_used: Optional[str] = None
    error: Optional[str] = None
