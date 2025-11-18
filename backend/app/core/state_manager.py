import redis
import json
from .config import settings
from .schemas import JobState


class StateManager:
    def __init__(self, job_id: str):
        self.job_id = job_id
        try:
            self.redis_client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=0,
                decode_responses=True,
            )
            self.redis_client.ping()
        except Exception as e:
            raise ConnectionError(f"Could not connect to Redis: {e}")

    def create_job(self, query: str) -> JobState:
        """Creates and saves the initial job state."""
        state = JobState(job_id=self.job_id, original_query=query, status="PENDING")
        self.save_state(state)
        return state

    def get_state(self) -> JobState:
        """Fetches the current job state from Redis."""
        try:
            state_json = self.redis_client.get(self.job_id)
            if not state_json:
                raise ValueError(f"No job found with ID: {self.job_id}")
            return JobState(**json.loads(state_json))
        except Exception as e:
            raise ValueError(f"Error fetching state: {e}")

    def save_state(self, state: JobState):
        """Saves the entire job state to Redis."""
        try:
            self.redis_client.set(self.job_id, state.model_dump_json())
        except Exception as e:
            raise ValueError(f"Error saving state: {e}")
