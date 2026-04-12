from backend.app.services.job_service import JobService
from backend.app.core.schemas import ReActStep, ReActAction
from backend.services.agent_service import AgentService
from backend.services.tool_service import ToolService
from backend.services.synthesis_service import SynthesisService
from backend.services.decomposer_service import DecomposerService
from backend.services.query_router_service import QueryRouterService
from backend.services.tracer_service import TracerService
import asyncio
from urllib.parse import urlparse, urlunparse

class Orchestrator:
    def __init__(self, job_id: str):
        self.job_id = job_id
        self.job_service = JobService()
        self.agent = AgentService()
        self.tool = ToolService()
        self.tracer = TracerService(job_id)
        self.synthesis = None
        self.decompose = None
        self.query_router = None
        self.max_iterations = 10

    async def run_full_query(self):
        """main workflow to run the entire query process."""
        root_span = self.tracer.start_span("job.run", attributes={
            "job.id": self.job_id,
        })
        self.root_span_id = root_span.span_id

        try:
            state = await self.job_service.get_job_state(self.job_id)
            self.chat_id = state.chat_id
            self.is_agentic = state.is_agentic

            self.tracer.set_attributes(root_span.span_id, {
                "chat.id": self.chat_id,
                "is_agentic": self.is_agentic,
                "query.length": len(state.original_query),
            })

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

            self.tracer.finish_span(root_span.span_id, status="ok")

        except Exception as e:
            import traceback

            print(f"❌ Error in job {self.job_id}: {e}")
            print(f"Traceback: {traceback.format_exc()}")

            self.tracer.record_error(root_span.span_id, str(e))
            self.tracer.finish_span(root_span.span_id, status="error", error=str(e))

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

                iter_span = self.tracer.start_span("agent.iteration", parent_span_id=self.root_span_id, attributes={
                    "iteration": iteration,
                    "memory.count": len(state.memory),
                    "sources.count": len(state.sources),
                })

                think_span = self.tracer.start_span("agent.think", parent_span_id=iter_span.span_id, attributes={
                    "iteration": iteration,
                    "query.length": len(state.original_query),
                    "memory.count": len(state.memory),
                })

                try:
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

                    self.tracer.set_attributes(think_span.span_id, {
                        "tool.name": tool_name,
                        "confidence": action_decision.confidence,
                    })
                    self.tracer.finish_span(think_span.span_id, status="ok")
                except Exception as e:
                    self.tracer.record_error(think_span.span_id, str(e))
                    self.tracer.finish_span(think_span.span_id, status="error", error=str(e))
                    raise

                current_step = ReActStep(
                    thought=thought,
                    action=ReActAction(tool=tool_name, input=tool_input),
                )

                if tool_name == "final_answer":
                    reflect_span = self.tracer.start_span("agent.reflect", parent_span_id=iter_span.span_id, attributes={
                        "confidence": state.confidence,
                        "loop_count": state.loop_count,
                        "search_count": state.search_count,
                        "sources.count": len(state.sources),
                        "new_evidence_count": state.new_evidence_count,
                        "has_new_evidence": state.has_new_evidence,
                    })

                    result = await self._reflection_policy(state)

                    self.tracer.set_attributes(reflect_span.span_id, {
                        "reflection.decision": result
                    })

                    if result == "RETRY_SEARCH":
                        self.tracer.add_event(reflect_span.span_id, "reflection.retry_triggered")
                        self.tracer.finish_span(reflect_span.span_id, status="ok")

                        feedback_step = ReActStep(
                            thought="System Reflection: Confidence is low. Need more evidence.",
                            action=ReActAction(tool="system_feedback", input="retry"),
                            observation="Confidence is too low. Please perform deeper searches.",
                        )
                        current_step.observation = "Answer rejected: Confidence too low."
                        state.memory.append(current_step)
                        state.memory.append(feedback_step)
                        state.total_retries += 1
                        
                        self.tracer.finish_span(iter_span.span_id, status="ok")
                        continue

                    if result == "FORCE_FINAL_WITH_CAVEATS":
                        self.tracer.add_event(reflect_span.span_id, "reflection.force_final")

                    self.tracer.finish_span(reflect_span.span_id, status="ok")

                    finalize_span = self.tracer.start_span("agent.finalize", parent_span_id=iter_span.span_id, attributes={
                        "mode": "direct" if tool_input else "synthesis"
                    })

                    if tool_input:
                        state.final_answer = tool_input
                        self.tracer.finish_span(finalize_span.span_id, status="ok")
                    else:
                        state.status = "SYNTHESIZING"
                        yield state
                        state.final_answer = ""
                        approx_context_len = sum(len(step.observation) for step in state.memory if step.observation)
                        if approx_context_len > 16000:
                            self.tracer.add_event(finalize_span.span_id, "context.truncated")
                        
                        self.tracer.add_event(finalize_span.span_id, "synthesis.started_stream")
                        async for chunk in self.synthesis.summarize_stream(
                            state.original_query, state.memory
                        ):
                            state.final_answer += chunk
                            yield state
                        self.tracer.add_event(finalize_span.span_id, "synthesis.finished_stream")
                        self.tracer.finish_span(finalize_span.span_id, status="ok")

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
                    self.tracer.finish_span(iter_span.span_id, status="ok")
                    break

                state.status = "WORKING"
                yield state

                state.search_count += 1

                tool_span = self.tracer.start_span("agent.tool_execute", parent_span_id=iter_span.span_id, attributes={
                    "tool.name": tool_name,
                    "tool.input": tool_input,
                })

                try:
                    observation, results = await self.tool.execute(
                        tool_name,
                        tool_input,
                    )

                    new_count = 0
                    new_items = []

                    if results and tool_name == "web_search":
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
                        
                        if results:
                            self.tracer.add_event(tool_span.span_id, "search.results_received")
                        else:
                            self.tracer.add_event(tool_span.span_id, "search.no_results")

                    state.has_new_evidence = new_count > 0
                    state.new_evidence_count = new_count

                    self.tracer.set_attributes(tool_span.span_id, {
                        "results.count": len(results) if results else 0,
                        "new_evidence_count": new_count,
                        "has_new_evidence": new_count > 0,
                    })
                    self.tracer.finish_span(tool_span.span_id, status="ok")
                except Exception as e:
                    self.tracer.record_error(tool_span.span_id, str(e))
                    self.tracer.finish_span(tool_span.span_id, status="error", error=str(e))
                    raise

                current_step.observation = observation
                state.memory.append(current_step)

                await self.job_service.update_job_state(state)
                yield state

                self.tracer.finish_span(iter_span.span_id, status="ok")

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
        router_span = self.tracer.start_span("workflow.route_query", parent_span_id=self.root_span_id, attributes={
            "query.length": len(state.original_query),
            "memory.count": len(state.memory),
        })

        try:
            try:
                response = await self.query_router.route(state.original_query)
            except Exception as e:
                self.tracer.record_error(router_span.span_id, str(e))
                self.tracer.finish_span(router_span.span_id, status="error", error=str(e))
                raise
            state.query_router = response
            
            if response.reason == "Router fallback on error." or response.confidence < 0.3:
                self.tracer.add_event(router_span.span_id, "router.fallback_used")
                
            route = response.route
            state.final_answer = ""

            self.tracer.set_attributes(router_span.span_id, {
                "route.label": route,
                "route.confidence": response.confidence,
                "route.reason": response.reason,
            })
            self.tracer.finish_span(router_span.span_id, status="ok")

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
                decompose_span = self.tracer.start_span("workflow.decompose", parent_span_id=self.root_span_id, attributes={
                    "query.length": len(state.original_query),
                })

                state.status = "DECOMPOSING"
                yield state

                sub_queries = await self.decompose.split_into_search_queries(
                    state.original_query
                )

                if len(sub_queries) > 4:
                    print(f"Throttling parallel subqueries from {len(sub_queries)} down to 4")
                    sub_queries = sub_queries[:4]

                self.tracer.set_attributes(decompose_span.span_id, {
                    "sub_queries.count": len(sub_queries),
                })
                self.tracer.finish_span(decompose_span.span_id, status="ok")

                state.sub_queries = sub_queries
                await self.job_service.update_job_state(state)

                state.status = "WORKING"
                yield state

                async def process_query(query):
                    search_span = self.tracer.start_span("workflow.web_search", parent_span_id=self.root_span_id, attributes={
                        "search.query": query,
                    })

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

                    if results:
                        self.tracer.add_event(search_span.span_id, "search.results_received")
                    else:
                        self.tracer.add_event(search_span.span_id, "search.no_results")

                    self.tracer.set_attributes(search_span.span_id, {
                        "results.count": len(results) if results else 0,
                        "new_evidence_count": new_count,
                        "has_new_evidence": new_count > 0,
                    })
                    self.tracer.finish_span(search_span.span_id, status="ok")

                await asyncio.gather(*[process_query(query) for query in sub_queries])

                await self.job_service.update_job_state(state)
                yield state

                approx_context_len = sum(len(step.observation) for step in state.memory if step.observation)
                synth_span = self.tracer.start_span("workflow.synthesize", parent_span_id=self.root_span_id, attributes={
                    "memory.count": len(state.memory),
                    "sources.count": len(state.sources),
                    "context.char_count": approx_context_len,
                })

                state.status = "SYNTHESIZING"
                yield state

                if approx_context_len > 16000:
                    self.tracer.add_event(synth_span.span_id, "context.truncated")

                self.tracer.add_event(synth_span.span_id, "synthesis.started_stream")
                async for chunk in self.synthesis.summarize_stream(
                    state.original_query,
                    state.memory,
                ):
                    state.final_answer += chunk
                    yield state
                self.tracer.add_event(synth_span.span_id, "synthesis.finished_stream")

                self.tracer.set_attributes(synth_span.span_id, {
                    "answer.char_count": len(state.final_answer),
                })
                self.tracer.finish_span(synth_span.span_id, status="ok")
            
            elif route in ("NO_SEARCH_CHAT", "MEMORY_ONLY"):

                state.status = "WORKING"
                await self.job_service.update_job_state(state)
                yield state

                synth_span = self.tracer.start_span("workflow.synthesize_chat", parent_span_id=self.root_span_id, attributes={
                    "memory.count": len(state.memory),
                })
                
                approx_context_len = sum(len(step.observation) for step in state.memory if step.observation)
                if approx_context_len > 16000:
                    self.tracer.add_event(synth_span.span_id, "context.truncated")

                self.tracer.add_event(synth_span.span_id, "synthesis.started_stream")
                async for chunk in self.synthesis.respond_from_context_stream(
                    state.original_query, route
                ):
                    state.final_answer += chunk
                    yield state
                
                self.tracer.add_event(synth_span.span_id, "synthesis.finished_stream")

                self.tracer.set_attributes(synth_span.span_id, {
                    "answer.char_count": len(state.final_answer),
                })
                self.tracer.finish_span(synth_span.span_id, status="ok")

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
