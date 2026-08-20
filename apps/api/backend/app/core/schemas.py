from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Literal, Dict, Any
from backend.app.utils.token import count_token
import re

# --- API Schemas ---


class QueryRequest(BaseModel):
    query: str = Field(
        ..., min_length=1, max_length=4000
    )  # ... means field is required
    chat_id: str = Field(..., min_length=1, max_length=100)
    is_agentic: bool = False

    @field_validator("query")
    @classmethod
    def sanitize_query(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Query cannot be empty")
        
        token_count = count_token(v)
        if token_count > 1000:
            raise ValueError(f"Query too long ({token_count} tokens, max 1000)")
        return v

    @field_validator("chat_id")
    @classmethod
    def validate_chat_id(cls, v: str) -> str:
        if not re.match(r"^[a-f0-9\-]{36}$", v):
            raise ValueError("Invalid chat_id format - must be a UUID")
        return v

class AskResponse(BaseModel):
    job_id: str


class StatusResponse(BaseModel):
    job_id: str
    status: Literal[
        "PENDING", "DECOMPOSING", "WORKING", "SYNTHESIZING", "COMPLETED", "FAILED", "CANCELLED"
    ]
    original_query: str
    final_answer: Optional[str] = None
    sub_queries: Optional[List[str]] = None
    sources: Optional[List[Dict[str, Any]]] = None
    memory: Optional[List[Dict[str, Any]]] = None


class ChatState(BaseModel):
    chat_id: str
    # job_ids: List[str] = []
    summary: Optional[str] = None
    recent_convo: List[Dict[str, Any]] = Field(default_factory=list)


# internal state schemas


class ReActAction(BaseModel):
    tool: str
    input: Optional[str] = None


class ReActStep(BaseModel):
    thought: str
    action: ReActAction
    observation: Optional[str] = None


class QueryRouteResponse(BaseModel):
    route: Literal["NO_SEARCH_CHAT", "MEMORY_ONLY", "WEB_REQUIRED"]
    reason: str
    confidence: float


class JobState(BaseModel):
    job_id: str
    chat_id: str
    status: str = "PENDING"
    original_query: str
    is_agentic: bool = False
    sub_queries: List[str] = Field(default_factory=list)
    memory: List[ReActStep] = Field(default_factory=list)
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    final_answer: Optional[str] = None
    error: Optional[str] = None
    loop_count: int = 0
    search_count: int = 0
    confidence: float = 0.0
    confidence_history: List[float] = Field(default_factory=list)
    has_new_evidence: bool = False
    new_evidence_count: int = 0
    total_retries: int = 0
    query_router: Optional[QueryRouteResponse] = None

class Action(BaseModel):
    tool: Literal["web_search", "final_answer"]
    input: str


class AgentResponse(BaseModel):
    thought: str
    action: Action
    confidence: float
