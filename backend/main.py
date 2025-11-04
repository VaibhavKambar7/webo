import uuid
import json
import logging
from app.core.schemas import AskResponse, QueryRequest, StatusResponse
from app.core.state_manager import StateManager
from orchestrator import Orchestrator
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_core.callbacks import BaseCallbackHandler
from app.agents.research_agent import ResearchAgent
from datetime import datetime
import asyncio

app = FastAPI()

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Research Agent
research_agent = ResearchAgent()

class StreamingCallbackHandler(BaseCallbackHandler):
    """Custom callback handler to capture and stream agent thoughts and actions"""
    
    def __init__(self, message_queue: asyncio.Queue):
        self.message_queue = message_queue
        self.thoughts = []
        
    def _get_timestamp(self):
        return datetime.now().isoformat()

    async def on_agent_action(self, action, **kwargs):
        """Called when agent decides on an action"""
        step_data = {
            "type": "action",
            "tool": action.tool,
            "tool_input": action.tool_input,
            "log": action.log,
            "timestamp": self._get_timestamp()
        }
        self.thoughts.append(step_data)
        await self.message_queue.put(json.dumps({'type': 'thinking_step', 'data': step_data}))
        
    async def on_agent_finish(self, finish, **kwargs):
        """Called when agent finishes"""
        step_data = {
            "type": "finish",
            "output": finish.return_values.get("output", ""),
            "log": finish.log,
            "timestamp": self._get_timestamp()
        }
        self.thoughts.append(step_data)
        await self.message_queue.put(json.dumps({'type': 'thinking_step', 'data': step_data}))
        
    async def on_tool_start(self, serialized, input_str, **kwargs):
        """Called when a tool starts execution"""
        step_data = {
            "type": "tool_start",
            "tool_name": serialized.get("name", "unknown"),
            "input": input_str,
            "timestamp": self._get_timestamp()
        }
        self.thoughts.append(step_data)
        await self.message_queue.put(json.dumps({'type': 'thinking_step', 'data': step_data}))
        
    async def on_tool_end(self, output, **kwargs):
        """Called when a tool finishes execution"""
        step_data = {
            "type": "tool_end",
            "output": output[:500] + "..." if len(output) > 500 else output,  # Truncate long outputs
            "timestamp": self._get_timestamp()
        }
        self.thoughts.append(step_data)
        await self.message_queue.put(json.dumps({'type': 'thinking_step', 'data': step_data}))
        
    async def on_text(self, text, **kwargs):
        """Called when agent produces text output"""
        if text.strip():
            step_data = {
                "type": "thought",
                "text": text.strip(),
                "timestamp": self._get_timestamp()
            }
            self.thoughts.append(step_data)
            await self.message_queue.put(json.dumps({'type': 'thinking_step', 'data': step_data}))

@app.get("/")
def read_root():
    return {"message": "AI Research Assistant API"}

@app.get("/research")
async def research_endpoint(query: str):
    """Non-streaming research endpoint"""
    try:
        result = research_agent.research(query)
        return {
            "query": result["query"],
            "answer": result["summary"],
            "raw_sources": [
                {
                    "title": citation["title"],
                    "url": citation["url"],
                    "summary": f"Source {citation['id']}: {citation['title']}",
                    "content": f"Referenced source: {citation['title']} - {citation['url']}"
                }
                for citation in result["citations"]
            ],
            "sources": [
                {
                    "title": citation["title"],
                    "url": citation["url"]
                }
                for citation in result["citations"]
            ]
        }
    except Exception as e:
        logging.error(f"Research error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/research/stream")
async def research_stream_endpoint(query: str):
    """Streaming research endpoint that shows thinking process"""
    
    async def generate_research_stream():
        message_queue = asyncio.Queue()
        streaming_handler = StreamingCallbackHandler(message_queue)

        async def run_research():
            try:
                # Reset collected citations
                research_agent.collected_citations = {}
                
                # Citation collector (same as original)
                class CitationCollectorCallback(BaseCallbackHandler):
                    def __init__(self, agent_instance):
                        self.agent_instance = agent_instance

                    def on_tool_end(self, output: str, **kwargs):
                        sources_start = output.find("\nSources:\n")
                        if sources_start != -1:
                            sources_raw = output[sources_start + len("\nSources:\n"):].strip()
                            for line in sources_raw.split("\n"):
                                import re
                                match = re.match(r"\[(\d+)\] (.*) \((http.*)\)", line)
                                if match:
                                    cit_id = int(match.group(1))
                                    title = match.group(2)
                                    url = match.group(3)
                                    self.agent_instance.collected_citations[cit_id] = {
                                        "id": cit_id,
                                        "title": title,
                                        "url": url,
                                    }
                        return None
                
                citation_collector = CitationCollectorCallback(research_agent)
                
                # Execute with both callbacks
                result = await research_agent.agent_executor.ainvoke( # Use ainvoke for async
                    {"input": query, "chat_history": []},
                    {"callbacks": [streaming_handler, citation_collector]}
                )
                
                final_result_data = {
                    "type": "final_result",
                    "query": query,
                    "answer": result.get("output", "No answer generated"),
                    "raw_sources": [
                        {
                            "title": citation["title"],
                            "url": citation["url"],
                            "summary": f"Source {citation['id']}: {citation['title']}",
                            "content": f"Referenced source: {citation['title']} - {citation['url']}"
                        }
                        for citation in sorted(research_agent.collected_citations.values(), key=lambda x: x["id"])
                    ],
                    "sources": [
                        {
                            "title": citation["title"],
                            "url": citation["url"]
                        }
                        for citation in sorted(research_agent.collected_citations.values(), key=lambda x: x["id"])
                    ],
                    "thinking_steps": len(streaming_handler.thoughts)
                }
                await message_queue.put(json.dumps(final_result_data))
                await message_queue.put(json.dumps({'type': 'complete'}))

            except Exception as e:
                logging.error(f"Research error: {e}")
                error_data = {
                    "type": "error",
                    "message": str(e),
                    "query": query
                }
                await message_queue.put(json.dumps(error_data))
                await message_queue.put(json.dumps({'type': 'complete'}))

        # Start the research in a background task
        asyncio.create_task(run_research())

        # Stream messages from the queue
        while True:
            message = await message_queue.get()
            yield f"data: {message}\n\n"
            if json.loads(message).get('type') == 'complete':
                break
            await asyncio.sleep(0.05) # Small delay for smoother streaming

    return StreamingResponse(
        generate_research_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )

# Keep the original web_search endpoint for backward compatibility
@app.get("/web_search")
async def web_search_endpoint(query: str):
    """Redirect to research endpoint for backward compatibility"""
    return await research_endpoint(query)

@app.post("/ask", response_model=AskResponse)
def ask_question(
    request: QueryRequest,
    background_tasks: BackgroundTasks
):
    """
    submits a new query, runs the full process in the background, returns a job_id to check for status.
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
        
        return StatusResponse(
            job_id=state.job_id,
            status=state.status,
            original_query=state.original_query,
            final_answer=state.final_answer,
            memory=state.memory
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=f"Service unavailable: {e}")