from pydantic import BaseModel
from typing import List, Optional, Literal, Dict, Any

# --- API Schemas ---


class QueryRequest(BaseModel):
    query: str
    chat_id: str
    is_agentic: bool = False


class AskResponse(BaseModel):
    job_id: str


class StatusResponse(BaseModel):
    job_id: str
    status: Literal[
        "PENDING", "DECOMPOSING", "WORKING", "SYNTHESIZING", "COMPLETED", "FAILED"
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
    recent_convo: List[Dict[str, Any]] = []


# internal state schemas


class ReActAction(BaseModel):
    tool: str
    input: Optional[str] = None


class ReActStep(BaseModel):
    thought: str
    action: ReActAction
    observation: Optional[str] = None


class JobState(BaseModel):
    job_id: str
    chat_id: str
    status: str = "PENDING"
    original_query: str
    is_agentic: bool = False
    sub_queries: List[str] = []
    memory: List[ReActStep] = []
    sources: List[Dict[str, Any]] = []
    final_answer: Optional[str] = None
    error: Optional[str] = None
    loop_count: int = 0
    search_count: int = 0
    confidence: float = 0.0
    confidence_history: List[float] = []
    has_new_evidence: bool = False


class Action(BaseModel):
    tool: Literal["web_search", "final_answer"]
    input: str


class AgentResponse(BaseModel):
    thought: str
    action: Action
    confidence: float
