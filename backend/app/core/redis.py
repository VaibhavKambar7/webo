import redis.asyncio as redis
import json
from backend.app.core.config import settings

redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

async def get_redis_client():
    return redis_client

async def set_job_status(job_id: str, status: str, data: dict = None):
    await redis_client.hset(f"job:{job_id}", mapping={
        "status": status,
        "data": json.dumps(data) if data else "{}"
    })

async def get_job_status(job_id: str):
    return await redis_client.hgetall(f"job:{job_id}")
