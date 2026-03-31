from datetime import datetime
from typing import Optional, Any
from dataclasses import dataclass, field


@dataclass
class TraceEvent:
    timestamp: datetime
    name: str
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class TraceSpan:
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    name: str = ""
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    duration_ms: Optional[float] = None
    status: str = "in_progress"
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[TraceEvent] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class TraceSession:
    job_id: str
    trace_id: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    spans: list[TraceSpan] = field(default_factory=list)