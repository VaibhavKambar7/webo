from app.core.schemas import ChatState
from repositories.chat_repository import ChatRepository
from repositories.job_repository import JobRepository
from typing import Optional,List
from app.core.cache import ChatManager

class ChatService:
    def __init__(self):
        self.chat_repo = ChatRepository()
        self.job_repo = JobRepository()

    async def create_chat(self,chat_id:str) -> ChatState:

        if not chat_id or not chat_id.strip():
            raise ValueError("Chat ID cannot be empty")

        state = ChatState(chat_id = chat_id)

        chat_manager = ChatManager(chat_id)
        await chat_manager.save_to_redis(state)

        await self.chat_repo.create({
            "chat_id": chat_id,
            "recent_convo": []
        })

        return state

    async def get_chat_state(self,chat_id:str) -> ChatState:

        chat_manager = ChatManager(chat_id)
        state = await chat_manager.get_from_redis()

        if state:
            return state

        db_chat = await self.chat_repo.get_by_id(chat_id)
        if not db_chat:
            raise ValueError(f"Chat not found: {chat_id}")

        return self._db_chat_to_state(db_chat)

    async def update_chat_summary(self,chat_id:str,summary: Optional[str] = None, recent_convo: Optional[List[str]] = None) -> None:

        state = await self.get_chat_state(chat_id)

        if summary is not None:
            state.summary = summary
        if recent_convo is not None:
            state.recent_convo = recent_convo
        
        chat_manager = ChatManager(chat_id)
        await chat_manager.save_to_redis(state)

        updates = {}

        if summary is not None:
            updates["summary"] = summary

        if recent_convo is not None:
            updates["recent_convo"] = recent_convo
        
        if updates:
            await self.chat_repo.update(chat_id,updates)

    async def get_chat_history(self,chat_id:str) -> List[dict]:

        if not await self.chat_repo.exists(chat_id):
            raise ValueError(f"Chat not found: {chat_id}")
        
        jobs = await self.job_repo.get_by_chat_id(chat_id)

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

    def _db_chat_to_state(self,db_chat) -> ChatState:

        return ChatState(
            chat_id = db_chat.chat_id,
            recent_convo = db_chat.recent_convo,
            summary = db_chat.summary,
        )