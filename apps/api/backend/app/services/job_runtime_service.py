import asyncio
from collections import defaultdict
from typing import AsyncIterator

from backend.app.core.schemas import JobState
from backend.app.services.job_service import JobService
from backend.orchestrator import Orchestrator


TERMINAL_STATUSES = {"COMPLETED", "FAILED", "CANCELLED"}


class JobRuntimeService:
    def __init__(self):
        self.job_service = JobService()
        self._lock = asyncio.Lock()
        self._tasks: dict[str, asyncio.Task] = {}
        self._cancel_events: dict[str, asyncio.Event] = {}
        self._subscribers: dict[str, set[asyncio.Queue[JobState]]] = defaultdict(set)

    async def start_job(self, job_id: str) -> bool:
        async with self._lock:
            task = self._tasks.get(job_id)
            if task and not task.done():
                return False

            cancel_event = self._cancel_events.get(job_id)
            if cancel_event is None or cancel_event.is_set():
                cancel_event = asyncio.Event()
                self._cancel_events[job_id] = cancel_event

            task = asyncio.create_task(
                self._run_job(job_id, cancel_event),
                name=f"job-runtime:{job_id}",
            )
            self._tasks[job_id] = task
            return True

    async def cancel_job(self, job_id: str) -> JobState:
        state = await self.job_service.get_job_state(job_id)

        if state.status in TERMINAL_STATUSES:
            return state

        cancel_event = self._cancel_events.setdefault(job_id, asyncio.Event())
        cancel_event.set()

        state.status = "CANCELLED"
        state.error = "Job cancelled by user."
        await self.job_service.update_job_state(state)
        await self.publish_state(state)

        task = self._tasks.get(job_id)
        if task and not task.done():
            task.cancel()

        return state

    async def subscribe(self, job_id: str) -> AsyncIterator[JobState]:
        queue: asyncio.Queue[JobState] = asyncio.Queue()
        self._subscribers[job_id].add(queue)

        try:
            initial_state = await self.job_service.get_job_state(job_id)
            yield initial_state

            if initial_state.status in TERMINAL_STATUSES:
                return

            while True:
                state = await queue.get()
                yield state

                if state.status in TERMINAL_STATUSES:
                    return
        finally:
            subscribers = self._subscribers.get(job_id)
            if subscribers is not None:
                subscribers.discard(queue)
                if not subscribers:
                    self._subscribers.pop(job_id, None)

    async def publish_state(self, state: JobState) -> None:
        for queue in list(self._subscribers.get(state.job_id, set())):
            await queue.put(state.model_copy(deep=True))

    async def _run_job(self, job_id: str, cancel_event: asyncio.Event) -> None:
        orchestrator = Orchestrator(job_id, cancel_event=cancel_event)
        current_task = asyncio.current_task()

        try:
            async for state in orchestrator.run_full_query():
                await self.publish_state(state)
        finally:
            async with self._lock:
                task = self._tasks.get(job_id)
                if task is current_task:
                    self._tasks.pop(job_id, None)


job_runtime_service = JobRuntimeService()
