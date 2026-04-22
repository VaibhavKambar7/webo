import uuid
import json
import os
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from backend.app.core.schemas import AskResponse, QueryRequest
from pydantic import BaseModel
from backend.app.services.job_service import JobService
from backend.app.services.chat_service import ChatService
from backend.orchestrator import Orchestrator
from fastapi.responses import StreamingResponse
from contextlib import asynccontextmanager
from backend.app.core.database import engine, Base
from backend.app.guardrails.sanitizer import sanitize_input, contains_encoding_attack
from backend.app.guardrails.injection_guard import detect_injection
from backend.app.guardrails.moderation import check_moderation
from backend.app.guardrails.pii_guard import has_high_risk_pii, redact_medium_pii

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "webo"}


class GetChatRequest(BaseModel):
    chat_id: str


@app.post("/get-chat")
async def get_chats(request: GetChatRequest):
    """
    returns messages for a chat
    """
    try:
        chat_service = ChatService()
        messages = await chat_service.get_chat_history(request.chat_id)

        return messages

    except Exception as e:
        print(f"Error fetching chat history: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching chat history: {e}")


@app.post("/ask", response_model=AskResponse)
async def ask_question(request: QueryRequest, background_tasks: BackgroundTasks):
    """
    submits a new query and returns a job_id for streaming.
    """
    job_id = str(uuid.uuid4())
    
    # 1. Sanitize (remove invisible chars, normalize unicode)
    clean_query = sanitize_input(request.query)

    # 1b. Encoding attack check
    if contains_encoding_attack(clean_query):
        raise HTTPException(status_code=400, detail="Your query could not be processed.")

    # 2. Injection detection (narrow regex)
    is_injection, matched = detect_injection(clean_query)
    if is_injection:
        print(f"Blocked injection attempt. Matched: {matched}")
        raise HTTPException(status_code=400, detail="Your query could not be processed due to safety constraints.")

    # 3. Content Moderation (Toxic, Self-Harm, Violence)
    await check_moderation(clean_query)

    # 4. PII Guard (High-risk blocking, Medium-risk redaction)
    has_high_pii, pii_types = has_high_risk_pii(clean_query)
    if has_high_pii:
        print(f"Blocked query due to high-risk PII: {pii_types}")
        raise HTTPException(status_code=400, detail="Query blocked: Contains highly sensitive personal information.")
    
    clean_query = redact_medium_pii(clean_query)

    try:
        job_service = JobService()
        await job_service.create_job(
            job_id, clean_query, request.chat_id, request.is_agentic
        )

        return AskResponse(job_id=job_id)

    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=f"Service unavailable: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error submitting job: {e}")


@app.post("/create-chatId")
async def create_chat_id():
    """
    creates chat id for frontend param
    """
    chat_id = str(uuid.uuid4())
    try:
        chat_service = ChatService()
        await chat_service.create_chat(chat_id)

        return {"chat_id": chat_id}

    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=f"Service unavailable: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating chat id: {e}")


@app.get("/stream/{job_id}")
async def event_streamer(job_id: uuid.UUID):
    job_id_str = str(job_id)
    async def event_stream():
        orchestrator = Orchestrator(job_id_str)

        try:
            async for state in orchestrator.run_full_query():
                memory_dicts = (
                    [step.model_dump() for step in state.memory] if state.memory else []
                )

                state_dict = {
                    "job_id": state.job_id,
                    "status": state.status,
                    "final_answer": state.final_answer,
                    "sub_queries": state.sub_queries,
                    "sources": state.sources,
                    "memory": memory_dicts,
                }

                yield f"data:{json.dumps(state_dict)}\n\n"

            yield f"data:{json.dumps({'type': 'completed'})}\n\n"

        except Exception as e:
            yield f"data:{json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

@app.get("/traces/{job_id}")
async def get_trace(job_id: uuid.UUID):
    """
    Returns the trace JSON for a given job.
    """
    job_id = str(job_id)
    trace_path = f"backend/traces/{job_id}.json"
    if not os.path.exists(trace_path):
        raise HTTPException(status_code=404, detail="Trace not found")
        
    with open(trace_path, "r") as f:
        trace_data = json.load(f)
        
    return trace_data
