from app.services.job_service import JobService
from app.core.schemas import ReActStep, ReActAction
from services.agent_service import AgentService
from services.tool_service import ToolService
from services.synthesis_service import SynthesisService


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
            
            self.synthesis = SynthesisService(self.chat_id)

            state.status = "THINKING"
            yield state

            iteration = 0

            while iteration < self.max_iterations:
                iteration += 1

                action_decision = await self.agent.think(
                    sub_query = state.original_query,
                    memory = state.memory
                )

                thought = action_decision.get("thought","")
                action = action_decision.get("action",{})
                tool_name = action.get("tool")
                tool_input = action.get("input")

                current_step = ReActStep(
                    thought = thought,
                    action = ReActAction(tool=tool_name,input=tool_input)
                )

                if tool_name == "final_answer":
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
                
                state.status = f"Working (Step {iteration})"
                yield state

                observation, results = self.tool.execute(tool_name,tool_input)

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


            await self.job_service.update_job_state(state)

            print(f"Job {self.job_id} completed.")

        except Exception as e:
            print(f"Error in job {self.job_id}: {e}")
            try:
                state = await self.job_service.get_job_state(self.job_id)
                state.status = "FAILED"
                state.error = str(e)
                await self.job_service.update_job_state(state)
                yield state
            except Exception:
                pass
