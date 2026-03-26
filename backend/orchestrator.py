from backend.app.services.job_service import JobService
from backend.app.core.schemas import ReActStep, ReActAction
from backend.services.agent_service import AgentService
from backend.services.tool_service import ToolService
from backend.services.synthesis_service import SynthesisService
from backend.services.decomposer_service import DecomposerService
from backend.services.query_router_service import QueryRouterService
import asyncio
from urllib.parse import urlparse, urlunparse

class Orchestrator:
    def __init__(self, job_id: str):
        self.job_id = job_id
        self.job_service = JobService()
        self.agent = AgentService()
        self.tool = ToolService()
        self.synthesis = None
        self.decompose = None
        self.query_router = None
        self.max_iterations = 10

    async def run_full_query(self):
        """main workflow to run the entire query process."""
        try:
            state = await self.job_service.get_job_state(self.job_id)
            self.chat_id = state.chat_id
            self.is_agentic = state.is_agentic

            self.synthesis = SynthesisService(self.chat_id)
            self.decompose = DecomposerService(self.chat_id)
            self.query_router = QueryRouterService(self.chat_id)


            state.status = "WORKING"
            yield state

            if state.is_agentic:
                async for next_state in self._run_agent_loop(state):
                    yield next_state
            else:
                async for next_state in self._run_workflow(state):
                    yield next_state

        except Exception as e:
            import traceback

            print(f"❌ Error in job {self.job_id}: {e}")
            print(f"Traceback: {traceback.format_exc()}")

            try:
                state = await self.job_service.get_job_state(self.job_id)
                state.status = "FAILED"
                state.error = str(e)
                await self.job_service.update_job_state(state)
                yield state
            except Exception:
                pass

    async def _run_agent_loop(self, state):
        try:
            iteration = 0

            while iteration < self.max_iterations:
                iteration += 1
                state.loop_count = iteration 

                action_decision = await self.agent.think(
                    sub_query=state.original_query,
                    memory=state.memory,
                )

                thought = action_decision.thought
                action_object = action_decision.action
                tool_name = action_object.tool
                tool_input = action_object.input

                state.confidence_history.append(action_decision.confidence)
                state.confidence = action_decision.confidence

                current_step = ReActStep(
                    thought=thought,
                    action=ReActAction(tool=tool_name, input=tool_input),
                )

                if tool_name == "final_answer":
                    result = await self._reflection_policy(state)

                    if result == "RETRY_SEARCH":

                        feedback_step = ReActStep(
                            thought="System Reflection: Confidence is low. Need more evidence.",
                            action=ReActAction(tool="system_feedback", input="retry"),
                            observation="Confidence is too low. Please perform deeper searches.",
                        )
                        current_step.observation = "Answer rejected: Confidence too low."
                        state.memory.append(current_step)
                        state.memory.append(feedback_step)
                        state.total_retries += 1
                        continue

                    if tool_input:
                        state.final_answer = tool_input
                    else:
                        state.status = "SYNTHESIZING"
                        yield state
                        state.final_answer = ""
                        async for chunk in self.synthesis.summarize_stream(
                            state.original_query, state.memory
                        ):
                            state.final_answer += chunk
                            yield state

                    if result == "FORCE_FINAL_WITH_CAVEATS":
                        state.final_answer = (
                            (state.final_answer or "")
                            + "\n\nNote: The system confidence was low, so this answer may contain uncertainty."
                        )
                        state.total_retries = 0
                    
                    if result == "ACCEPT": 
                        state.total_retries = 0

                    state.status = "COMPLETED"
                    await self.job_service.update_job_state(state)
                    yield state
                    break

                state.status = "WORKING"
                yield state

                state.search_count += 1

                observation, results = await self.tool.execute(
                    tool_name,
                    tool_input,
                )

                new_count = 0
                new_items = []

                if results and tool_name == "web_search":

                    new_count, new_items = self._count_new_sources(results,state.sources)

                    source_citations = [
                        {
                            "title": r.get("title"),
                            "url": r.get("url"),
                            "favicon": r.get("favicon"),
                        }
                        for r in new_items
                    ]

                    state.sources.extend(source_citations)
                state.has_new_evidence = new_count > 0
                state.new_evidence_count = new_count

                current_step.observation = observation
                state.memory.append(current_step)

                await self.job_service.update_job_state(state)
                yield state

        except Exception as e:
            import traceback

            print(f"❌ Error in job {self.job_id}: {e}")
            print(f"Traceback: {traceback.format_exc()}")

            try:
                state = await self.job_service.get_job_state(self.job_id)
                state.status = "FAILED"
                state.error = str(e)
                await self.job_service.update_job_state(state)
                yield state
            except Exception:
                pass

    async def _run_workflow(self, state):
        try:

            response = await self.query_router.route(state.original_query)
            state.query_router = response
            route = response.route
            state.final_answer = ""
            state.memory.append(
                ReActStep(
                    thought="Routing query before workflow execution.",
                    action=ReActAction(tool="route_query", input=state.original_query),
                    observation=(
                        f"Route={response.route}; "
                        f"Confidence={response.confidence:.2f}; "
                        f"Reason={response.reason}"
                    ),
                )
            )
            state.status = "WORKING"
            await self.job_service.update_job_state(state)
            print(
                f"[ROUTER] job={self.job_id} route={response.route} "
                f"confidence={response.confidence:.2f} reason={response.reason}"
            )


            if route == "WEB_REQUIRED":
                state.status = "DECOMPOSING"
                yield state

                sub_queries = await self.decompose.split_into_search_queries(
                    state.original_query
                )

                state.sub_queries = sub_queries
                await self.job_service.update_job_state(state)

                state.status = "WORKING"
                yield state

                async def process_query(query):
                    observation, results = await self.tool.execute(
                        "web_search",
                        query,
                    )

                    new_count = 0
                    new_items = []

                    if results:
                        new_count, new_items = self._count_new_sources(results, state.sources)
                        source_citations = [
                            {
                                "title": r.get("title"),
                                "url": r.get("url"),
                                "favicon": r.get("favicon"),
                            }
                            for r in new_items
                        ]

                        state.sources.extend(source_citations)

                        state.has_new_evidence = state.has_new_evidence or (
                            new_count > 0
                        )
                        state.new_evidence_count += new_count

                        state.memory.append(
                            ReActStep(
                                thought=f"Searching for: {query}",
                                action=ReActAction(tool="web_search", input=query),
                                observation=observation,
                            )
                        )

                await asyncio.gather(*[process_query(query) for query in sub_queries])

                await self.job_service.update_job_state(state)
                yield state

                state.status = "SYNTHESIZING"
                yield state

                async for chunk in self.synthesis.summarize_stream(
                    state.original_query,
                    state.memory,
                ):
                    state.final_answer += chunk
                    yield state
            
            elif route in ("NO_SEARCH_CHAT", "MEMORY_ONLY"):

                state.status = "WORKING"
                await self.job_service.update_job_state(state)
                yield state

                async for chunk in self.synthesis.respond_from_context_stream(
                    state.original_query, route
                ):
                    state.final_answer += chunk
                    yield state

            state.status = "COMPLETED"
            await self.job_service.update_job_state(state)
            yield state

            print(f"Job {self.job_id} completed.")

        except Exception as e:
            import traceback

            print(f"❌ Error in job {self.job_id}: {e}")
            print(f"Traceback: {traceback.format_exc()}")

            try:
                state = await self.job_service.get_job_state(self.job_id)
                state.status = "FAILED"
                state.error = str(e)
                await self.job_service.update_job_state(state)
                yield state
            except Exception:
                pass

    async def _reflection_policy(self, state):
        try:
            confidence = state.confidence
            loop_count = state.loop_count
            sources = state.sources
            sources_count = len(sources)
            search_count = state.search_count
            new_evidence_count = state.new_evidence_count
            total_retries = state.total_retries
            has_new_evidence = state.has_new_evidence

            if loop_count >= self.max_iterations:
                return "FORCE_FINAL_WITH_CAVEATS"

            if search_count > 0 and not has_new_evidence and total_retries > 3:
                return "FORCE_FINAL_WITH_CAVEATS"

            if sources_count == 0:
                return "RETRY_SEARCH"

            if search_count > 0 and new_evidence_count == 0:
                return "RETRY_SEARCH"

            if confidence >= 0.8:
                return "ACCEPT"

            return "RETRY_SEARCH"

        except Exception:
            print("Error in reflector")
            return "RETRY_SEARCH"

    def _count_new_sources(self, results, existing_sources):
        existing = set()
        for src in existing_sources:
            if url := src.get("url"):
                if norm := self._normalize_url(url):
                    existing.add(norm)

        new_count = 0
        new_items = []

        for r in results:
            url = r.get("url")
            content = r.get("content")

            if not url or not content:
                continue

            norm = self._normalize_url(url)
            if not norm:
                continue
            
            if norm not in existing:
                new_count += 1
                new_items.append(r)
                existing.add(norm)

        return new_count,new_items

    @staticmethod
    def _normalize_url(url: str) -> str | None:
        try:

            parsed = urlparse(url)

            if not parsed.scheme or not parsed.netloc:
                return None
            
            scheme = parsed.scheme.lower()
            netloc = parsed.netloc.lower()

            netloc = netloc.replace("www.","")

            if netloc.endswith(":80") and scheme == "http":
                netloc = netloc[:-3]
            elif netloc.endswith(":443") and scheme == "https":
                netloc = netloc[:-4]

            path = parsed.path or "/"
            if path != "/" and path.endswith("/"):
                path = path[:-1]

            return urlunparse((scheme, netloc, path, "", "", ""))

        except Exception:
            return None
