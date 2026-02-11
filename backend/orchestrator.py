from backend.app.services.job_service import JobService
from backend.app.core.schemas import ReActStep, ReActAction
from backend.services.agent_service import AgentService
from backend.services.tool_service import ToolService
from backend.services.synthesis_service import SynthesisService
from backend.services.decomposer_service import DecomposerService
import asyncio


class Orchestrator:
    def __init__(self, job_id: str):
        self.job_id = job_id
        self.job_service = JobService()
        self.agent = AgentService()
        self.tool = ToolService()
        self.synthesis = None
        self.max_iterations = 10

    async def run_full_query(self):
        """main workflow to run the entire query process."""
        try:
            state = await self.job_service.get_job_state(self.job_id)
            self.chat_id = state.chat_id
            self.is_agentic = state.is_agentic

            
            self.synthesis = SynthesisService(self.chat_id)
            self.decompose = DecomposerService(self.chat_id)


            state.status = "THINKING"
            yield state

            if state.is_agentic:
                iteration = 0
                while iteration < self.max_iterations:
                    iteration += 1

                    action_decision = await self.agent.think(
                        sub_query = state.original_query,
                        memory = state.memory
                    )

                    thought = action_decision.thought
                    action_object = action_decision.action 
                    tool_name = action_object.tool
                    tool_input = action_object.input

                    current_step = ReActStep(
                        thought = thought,
                        action = ReActAction(tool=tool_name,input=tool_input)
                    )

                    if tool_name == "final_answer":

                        if tool_input:
                            state.final_answer = tool_input
                            state.status = "COMPLETED"
                            await self.job_service.update_job_state(state)
                            yield state
                            break

                        state.status = "SYNTHESIZING"
                        yield state

                        state.final_answer = ""
                        async for chunk in self.synthesis.summarize_stream(
                            state.original_query, state.memory
                        ):
                            state.final_answer += chunk
                            yield state
                        
                        state.status = "COMPLETED"
                        await self.job_service.update_job_state(state)
                        yield state
                        break
                    
                    state.status = "WORKING"
                    yield state


                    observation, results = await self.tool.execute(tool_name, tool_input)

                    if results and tool_name == "web_search":
                        source_citations = [
                            {     
                                "title": r.get("title"),
                                "url": r.get("url"),
                                "favicon": r.get("favicon")
                            }
                            for r in results
                        ]
                        state.sources.extend(source_citations)

                    current_step.observation = observation
                    state.memory.append(current_step)

                    await self.job_service.update_job_state(state)  
                    yield state

                if iteration >= self.max_iterations:
                    state.status = "COMPLETED"
                    state.final_answer = "Maximum iterations reached. Synthesizing available information.."
                    yield state
            else:
                # Default Workflow
                state.status = "DECOMPOSING"
                yield state
                
                sub_queries = await self.decompose.split_into_search_queries(state.original_query)
                state.sub_queries = sub_queries
                await self.job_service.update_job_state(state)
                
                state.status = "WORKING"
                yield state
                
                
                async def process_query(query):
                    observation, results = await self.tool.execute("web_search", query)
                    
                    if results:
                        source_citations = [
                            {     
                                "title": r.get("title"),
                                "url": r.get("url"),
                                "favicon": r.get("favicon")
                            }
                            for r in results
                        ]
                        state.sources.extend(source_citations)
                    
                    # For default workflow, we don't really have "thought" and "action" in the same way,
                    # but we can store observations to memory for synthesis
                    state.memory.append(ReActStep(
                        thought=f"Searching for: {query}",
                        action=ReActAction(tool="web_search", input=query),
                        observation=observation
                    ))

                await asyncio.gather(*[process_query(query) for query in sub_queries])
                
                await self.job_service.update_job_state(state)
                yield state
                
                state.status = "SYNTHESIZING"
                yield state
                
                state.final_answer = ""
                async for chunk in self.synthesis.summarize_stream(
                    state.original_query, state.memory
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
