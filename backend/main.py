import uuid
import json
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from app.core.schemas import AskResponse, QueryRequest, StatusResponse
from pydantic import BaseModel
from app.core.state_manager import StateManager,ChatManager
from orchestrator import Orchestrator
from fastapi.responses import StreamingResponse

from contextlib import asynccontextmanager
from app.core.database import engine, Base

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
        chat_manager = ChatManager(request.chat_id)
        jobs = await chat_manager.get_full_history()
        
        messages = []
        for job in jobs:
            messages.append({
                "id": f"{job.job_id}-user",
                "role": "user",
                "content": job.original_query,
                "jobId": job.job_id
            })
            
            if job.final_answer or job.status != "PENDING":
                messages.append({
                    "id": f"{job.job_id}-assistant",
                    "role": "assistant",
                    "content": job.final_answer or "",
                    "sources": job.sources,
                    "thinkingSteps": job.memory, 
                    "subQueries": job.sub_queries,
                    "status": job.status,
                    "jobId": job.job_id,
                    "isExpanded": False, 
                })
        
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
    try:
        state_manager = StateManager(job_id)
        await state_manager.create_job(request.query, request.chat_id)

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
        chat_manager = ChatManager(chat_id)
        await chat_manager.create_chat()
        
        return {"chat_id": chat_id}

    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=f"Service unavailable: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating chat id: {e}")


#  currently not in use
@app.get("/status/{job_id}", response_model=StatusResponse)
async def get_status(job_id: str):
    """
    poll this endpoint to check the status and get the final answer.
    """
    try:
        state_manager = StateManager(job_id)
        state = await state_manager.get_state()

        memory_dicts = (
            [step.model_dump() for step in state.memory] if state.memory else None
        )

        return StatusResponse(
            job_id=state.job_id,
            status=state.status,
            original_query=state.original_query,
            final_answer=state.final_answer,
            sub_queries=state.sub_queries,
            memory=memory_dicts,
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=f"Service unavailable: {e}")


@app.get("/stream/{job_id}")
async def event_streamer(job_id: str):
    async def event_stream():
        orchestrator = Orchestrator(job_id)

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
