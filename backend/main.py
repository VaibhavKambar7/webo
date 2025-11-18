import uuid
import json
import asyncio
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from app.core.schemas import AskResponse, QueryRequest, StatusResponse
from app.core.state_manager import StateManager
from orchestrator import Orchestrator
from fastapi.responses import StreamingResponse

app = FastAPI()

# Middleware
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


@app.post("/ask", response_model=AskResponse)
def ask_question(request: QueryRequest, background_tasks: BackgroundTasks):
    """
    submits a new query, runs the process in the background,
    and returns a job_id to check status later.
    """
    job_id = str(uuid.uuid4())
    try:
        state_manager = StateManager(job_id)
        state_manager.create_job(request.query)

        orchestrator = Orchestrator(job_id)
        background_tasks.add_task(orchestrator.run_full_query)

        return AskResponse(job_id=job_id)

    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=f"Service unavailable: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error submitting job: {e}")


@app.get("/status/{job_id}", response_model=StatusResponse)
def get_status(job_id: str):
    """
    poll this endpoint to check the status and get the final answer.
    """
    try:
        state_manager = StateManager(job_id)
        state = state_manager.get_state()

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
        last_state = []
        state_manager = StateManager(job_id)

        while True:
            try:
                state = state_manager.get_state()
            except ValueError:
                yield f"data:{json.dumps({'type': 'error', 'message': 'Job not found'})}\n\n"
                break

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

            if state_dict != last_state:
                yield f"data:{json.dumps(state_dict)}\n\n"
                last_state = state_dict

            if state_dict["status"] in ("COMPLETED", "FAILED"):
                yield f"data:{json.dumps({'type': 'completed'})}\n\n"
                break

            # await asyncio.sleep(1.5)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
