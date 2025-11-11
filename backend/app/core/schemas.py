from pydantic import BaseModel
from typing import List, Optional, Literal, Dict, Any

# --- API Schemas ---

class QueryRequest(BaseModel):
    query: str

class AskResponse(BaseModel):
    job_id: str

class StatusResponse(BaseModel):
    job_id: str
    status: Literal["PENDING", "DECOMPOSING", "WORKING", "SYNTHESIZING", "COMPLETED", "FAILED"]
    original_query: str
    final_answer: Optional[str] = None
    sub_queries: Optional[List[str]] = None
    memory: Optional[List[Dict[str, Any]]] = None # For debugging

# --- Internal State Schemas ---

class ReActAction(BaseModel):
    tool: str
    input: Optional[str] = None

class ReActStep(BaseModel):
    thought: str
    action: ReActAction
    observation: Optional[str] = None

class JobState(BaseModel):
    job_id: str
    status: str = "PENDING"
    original_query: str
    sub_queries: List[str] = []
    memory: List[ReActStep] = []
    final_answer: Optional[str] = None
    error: Optional[str] = None