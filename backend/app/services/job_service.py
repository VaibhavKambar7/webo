from app.core.schemas import JobState, ReActStep
from repositories.job_repository import JobRepository
from app.core.state_manager import StateManager

class JobService:

    def __init__(self):
        self.job_repo = JobRepository()

    async def create_job(self,job_id:str,query:str,chat_id:str) -> JobState:

        if not query or not query.strip():
            raise ValueError("Query cannot be empty.")

        if not chat_id:
            raise ValueError("Chat ID is required.")

        state = JobState(
            job_id = job_id,
            chat_id = chat_id,
            original_query = query.strip(),
            status = "PENDING"
        )

        state_manager = StateManager(job_id)

        await state_manager.save_to_redis(state)

        await self.job_repo.create({
            "job_id": job_id,
            "chat_id": chat_id,
            "original_query": query.strip(),
            "status": "PENDING",
            "sub_queries": [],
            "memory": [],
            "sources": []            
        })

        return state

    async def get_job_state(self,job_id:str) -> JobState:

        state_manager = StateManager(job_id)
        state = await state_manager.get_from_redis()

        if state:
            return state

        db_job = await self.job_repo.get_by_id(job_id)

        if not db_job:
            raise ValueError(f"Job not found: {job_id}")

        return self._db_job_to_state(db_job)

    async def update_job_state(self,state: JobState) -> None:
        self._validate_status(state.status)

        state_manager = StateManager(state.job_id)
        await state_manager.save_to_redis(state)

        await self.job_repo.update(state.job_id, {
            "status": state.status,
            "sub_queries": state.sub_queries,
            "memory": [step.model_dump() for step in state.memory],
            "sources": state.sources,
            "final_answer": state.final_answer,
            "error": state.error
        })

    
    def _validate_status(self,status:str) -> None:
        
        valid_statuses = [
             "PENDING", 
            "DECOMPOSING", 
            "WORKING", 
            "SYNTHESIZING", 
            "COMPLETED", 
            "FAILED"
        ]

        if status not in valid_statuses:
            raise ValueError(f"Invalid status: {status}. Must be on of {valid_statuses} ")


    def _db_job_to_state(self,db_job) -> JobState:

        return JobState(
            job_id = db_job.job_id,
            chat_id = db_job.chat_id,
            status = db_job.status,
            original_query= db_job.original_query,
            sub_queries = db_job.sub_queries or [],
            memory = [ReActStep(**step) for step in (db_job.memory or [])],
            sources = db_job.sources or [],
            final_answer = db_job.final_answer,
            error = db_job.error
        )