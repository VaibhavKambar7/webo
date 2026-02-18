import json
from .schemas import JobState, ChatState
from typing import Optional
from .redis import get_redis_client


class StateManager:
    def __init__(self, job_id: str):
        self.job_id = job_id

    async def get_redis(self):
        return await get_redis_client()

    async def save_to_redis(self, state: JobState) -> None:
        redis = await self.get_redis()

        try:
            await redis.hset(
                f"job:{self.job_id}",
                mapping={"status": state.status, "data": state.model_dump_json()},
            )

        except Exception as e:
            print(f"Error saving to Redis: {e}")
            raise ValueError(f"Error saving to redis: {e}")

    async def get_from_redis(self) -> Optional[JobState]:
        redis = await self.get_redis()

        try:
            state_data = await redis.hgetall(f"job:{self.job_id}")
            if state_data and "data" in state_data:
                return JobState(**json.loads(state_data["data"]))
            return None
        except Exception as e:
            print(f"Error reading from redis:{e}")
            return None

    async def delete_from_redis(self) -> None:
        redis = await self.get_redis()
        await redis.delete(f"job:{self.job_id}")


class ChatManager:
    def __init__(self, chat_id: str):
        self.chat_id = chat_id

    async def get_redis(self):
        return await get_redis_client()

    async def save_to_redis(self, chat_state: ChatState) -> None:
        redis = await self.get_redis()
        try:
            await redis.set(f"chat:{self.chat_id}", chat_state.model_dump_json())
        except Exception as e:
            print(f"Error saving chat to Redis: {e}")
            raise

    async def get_from_redis(self) -> Optional[ChatState]:
        redis = await self.get_redis()
        try:
            state_json = await redis.get(f"chat:{self.chat_id}")
            if state_json:
                return ChatState(**json.loads(state_json))
            return None
        except Exception as e:
            print(f"Error reading chat from Redis: {e}")
            return None

    async def delete_from_redis(self) -> None:
        redis = await self.get_redis()
        await redis.delete(f"chat:{self.chat_id}")
