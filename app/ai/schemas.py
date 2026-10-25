"""Pydantic schemas for CORTIA AI Assistant."""
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


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    conversation_id: Optional[str] = Field(None, max_length=64)
    # Context-aware analysis parameters passed server-side
    analysis_type: Optional[Literal["mri", "eeg"]] = None
    analysis_id: Optional[str] = Field(None, max_length=64)


class ChatResponse(BaseModel):
    conversation_id: str
    message: ChatMessage
    provider_mode: str  # e.g., 'external_llm (gemini)', 'local_grounded_engine'
    suggested_followups: List[str] = Field(default_factory=list)


class ConversationSummary(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int


class CapabilitiesResponse(BaseModel):
    assistant_name: str = "CORTIA AI"
    version: str = "2.0"
    provider_configured: bool
    active_provider: str
    grounded_tools: List[str]
    starter_prompts: List[str]
    disclaimer: str
