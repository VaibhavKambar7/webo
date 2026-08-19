import json
import os
import uuid
from pathlib import Path
from typing import Any
from datetime import datetime
from dataclasses import asdict

from backend.app.core import TraceSpan, TraceEvent


class TracerService:
    def __init__(self, job_id: str):
        self.job_id = job_id
        self.trace_id = self._generate_id()
        self.created_at = datetime.utcnow().isoformat()
        trace_dir = Path(__file__).resolve().parent.parent / "traces"
        self.path = str(trace_dir / f"{job_id}.json")
        self.spans: dict[str, TraceSpan] = {}

    def start_span(
        self,
        name: str,
        parent_span_id: str | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> TraceSpan:
        span_id = self._generate_id()
        start_time = datetime.utcnow()

        span = TraceSpan(
            span_id=span_id,
            name=name,
            trace_id=self.trace_id,
            start_time=start_time,
            parent_span_id=parent_span_id,
            attributes=attributes or {},
        )

        self.spans[span_id] = span
        return span

    def finish_span(self, span_id: str, status="ok", error: str | None = None):
        span = self.spans.get(span_id)
        if span is None:
            raise ValueError(f"Span {span_id} not found")

        end_time = datetime.utcnow()
        start_time = span.start_time

        span.end_time = end_time
        span.duration_ms = (end_time - start_time).total_seconds() * 1000
        span.status = status
        span.error = error

        self._save(self._build_trace_data())

    def set_attribute(self, span_id: str, key: str, value: Any):
        span = self.spans.get(span_id)
        if span is None:
            raise ValueError(f"Span {span_id} not found")

        span.attributes[key] = value
        self._save(self._build_trace_data())

    def set_attributes(self, span_id: str, attributes: dict[str, Any] | None):
        span = self.spans.get(span_id)
        if span is None:
            raise ValueError(f"Span {span_id} not found")

        span.attributes.update(attributes or {})
        self._save(self._build_trace_data())

    def add_event(
        self,
        span_id: str,
        name: str,
        attributes: dict[str, Any] | None = None,
    ):
        span = self.spans.get(span_id)
        if span is None:
            raise ValueError(f"Span {span_id} not found")

        event = TraceEvent(
            timestamp=datetime.utcnow(),
            name=name,
            attributes=attributes or {},
        )

        span.events.append(event)
        self._save(self._build_trace_data())

    def record_error(
        self,
        span_id: str,
        error: str,
        attributes: dict[str, Any] | None = None,
    ):
        span = self.spans.get(span_id)
        if span is None:
            raise ValueError(f"Span {span_id} not found")

        span.status = "error"
        span.error = error

        event = TraceEvent(
            timestamp=datetime.utcnow(),
            name="exception",
            attributes={
                "error.message": error,
                **(attributes or {}),
            },
        )

        span.events.append(event)
        self._save(self._build_trace_data())

    def _generate_id(self) -> str:
        return str(uuid.uuid4())

    def _save(self, trace_data: dict):
        os.makedirs(Path(self.path).parent, exist_ok=True)

        with open(self.path, "w") as f:
            json.dump(trace_data, f, indent=2)

    def _serialize_span(self, span: TraceSpan) -> dict:
        data = asdict(span)

        data["start_time"] = span.start_time.isoformat()
        if span.end_time is not None:
            data["end_time"] = span.end_time.isoformat()

        serialized_events = []
        for event in span.events:
            serialized_events.append({
                "timestamp": event.timestamp.isoformat(),
                "name": event.name,
                "attributes": event.attributes,
            })

        data["events"] = serialized_events

        return data

    def _build_trace_data(self) -> dict:
        spans_data = [
            self._serialize_span(s) for s in self.spans.values()
        ]

        return {
            "job_id": self.job_id,
            "trace_id": self.trace_id,
            "created_at": self.created_at,
            "spans": spans_data,
        }
