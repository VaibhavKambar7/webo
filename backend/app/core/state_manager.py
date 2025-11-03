import redis
import json
from .config import settings
from .schemas import JobState,QueryRequest

class StateManager:
    def __init__(self,job_id:str):
        self.job_id = job_id
        try:  
            self.redis_client = redis.Redis(
                host = settings.REDIS_HOST,
                port = settings.REDIS_PORT,
                db=0,
                decode_responses = True
            )
            self.redis_client.ping()
        except Exception as e:
            raise ConnectionError(f"Could not connect to Redis: {e}")


