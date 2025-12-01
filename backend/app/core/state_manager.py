import json
from .schemas import JobState, ChatState
from .redis import get_redis_client
from .database import AsyncSessionLocal
from app.models.sql_models import Job, Chat
from sqlalchemy.future import select

class StateManager:
    def __init__(self, job_id: str):
        self.job_id = job_id

    async def get_redis(self):
        return await get_redis_client()

    async def create_job(self, query: str, chat_id: str) -> JobState:
        """Creates and saves the initial job state to Redis and Postgres."""
        state = JobState(job_id=self.job_id, chat_id=chat_id, original_query=query, status="PENDING")
        await self.save_state(state)
        
        # Initial save to DB
        async with AsyncSessionLocal() as session:
            db_job = Job(
                job_id=self.job_id,
                chat_id=chat_id,
                original_query=query,
                status="PENDING",
                sub_queries=[],
                memory=[],
                sources=[]
            )
            session.add(db_job)
            await session.commit()
            
        return state

    async def get_state(self) -> JobState:
        """Fetches the current job state from Redis, falling back to DB."""
        redis = await self.get_redis()
        try:
            # Try Redis first
            state_data = await redis.hgetall(f"job:{self.job_id}")
            if state_data and "data" in state_data:
                return JobState(**json.loads(state_data["data"]))
            
            # Fallback to DB
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(Job).filter(Job.job_id == self.job_id))
                job = result.scalars().first()
                if job:
                    return JobState(
                        job_id=job.job_id,
                        chat_id=job.chat_id,
                        status=job.status,
                        original_query=job.original_query,
                        sub_queries=job.sub_queries,
                        memory=job.memory,
                        sources=job.sources,
                        final_answer=job.final_answer,
                        error=job.error
                    )

            raise ValueError(f"No job found with ID: {self.job_id}")
        except Exception as e:
            raise ValueError(f"Error fetching state: {e}")

    async def save_state(self, state: JobState):
        """Saves the entire job state to Redis and updates Postgres."""
        redis = await self.get_redis()
        try:
            # Save to Redis
            await redis.hset(f"job:{self.job_id}", mapping={
                "status": state.status,
                "data": state.model_dump_json()
            })
            
            # Update Postgres (could be background task for performance, but keeping simple for now)
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(Job).filter(Job.job_id == self.job_id))
                job = result.scalars().first()
                if job:
                    job.status = state.status
                    job.sub_queries = state.sub_queries
                    job.memory = [step.model_dump() for step in state.memory]
                    job.sources = state.sources
                    job.final_answer = state.final_answer
                    job.error = state.error
                    await session.commit()
                    
        except Exception as e:
            print(f"Error saving state: {e}") # Log but don't crash if DB fails temporarily?
            # raise ValueError(f"Error saving state: {e}")


class ChatManager:
    def __init__(self, chat_id: str):
        self.chat_id = chat_id

    async def get_redis(self):
        return await get_redis_client()

    async def create_chat(self) -> ChatState:
        state = ChatState(chat_id=self.chat_id)
        await self.save_summary(state)
        
        async with AsyncSessionLocal() as session:
            db_chat = Chat(chat_id=self.chat_id, recent_convo=[])
            session.add(db_chat)
            await session.commit()
            
        return state

    async def save_summary(self, chat_state: ChatState):
        """Saves the entire chat state to Redis and Postgres."""
        redis = await self.get_redis()
        try:
            await redis.set(f"chat:{self.chat_id}", chat_state.model_dump_json())
            
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(Chat).filter(Chat.chat_id == self.chat_id))
                chat = result.scalars().first()
                if chat:
                    chat.summary = chat_state.summary
                    chat.recent_convo = chat_state.recent_convo
                    await session.commit()
                    
        except Exception as e:
            raise ValueError(f"Error saving chat summary: {e}")

    async def get_summary(self) -> ChatState:
        redis = await self.get_redis()
        try:
            state_json = await redis.get(f"chat:{self.chat_id}")
            if state_json:
                return ChatState(**json.loads(state_json))
                
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(Chat).filter(Chat.chat_id == self.chat_id))
                chat = result.scalars().first()
                if chat:
                    return ChatState(
                        chat_id=chat.chat_id,
                        summary=chat.summary,
                        recent_convo=chat.recent_convo
                    )
            
            # If not found, return empty state instead of error for chat?
            # Or raise error as before.
            raise ValueError(f"No chat found with ID: {self.chat_id}")
        except Exception as e:
            raise ValueError(f"Error fetching chat summary: {e}")
