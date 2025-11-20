from app.core.state_manager import StateManager
from app.core.schemas import ReActStep, ReActAction
from services.decomposer_service import DecomposerService
from services.agent_service import AgentService
from services.tool_service import ToolService
from services.synthesis_service import SynthesisService


class Orchestrator:
    def __init__(self, job_id: str):
        self.job_id = job_id
        self.state_manager = StateManager(job_id)

        self.decomposer = DecomposerService()
        self.agent = AgentService()
        self.tool = ToolService()
        self.synthesis = SynthesisService()

    def run_full_query(self):
        """main workflow to run the entire query process."""
        try:
            state = self.state_manager.get_state()
            state.status = "DECOMPOSING"
            yield state

            search_queries = self.decomposer.split_into_search_queries(
                state.original_query
            )
            state.sub_queries = search_queries

            state.status = "WORKING"
            yield state

            for query in search_queries:
                action = ReActAction(tool="web_search", input=query)
                current_step = ReActStep(
                    thought=f"Executing planned search: {query}", action=action
                )

                observation, results = self.tool.execute(action.tool, action.input)

                if results:
                    source_citations = [
                        {
                            "title": r.get("title"),
                            "url": r.get("url"),
                            "favicon": r.get("favicon"),
                        }
                        for r in results
                    ]

                    state.sources.extend(source_citations)

                current_step.observation = observation
                state.memory.append(current_step)
                self.state_manager.save_state(state)

            state.status = "SYNTHESIZING"
            yield state

            state.final_answer = ""

            for chunk in self.synthesis.summarize_stream(
                state.original_query, state.memory
            ):
                state.final_answer += chunk
                yield state

            state.status = "COMPLETED"
            yield state

            self.state_manager.save_state(state)
            print(f"Job {self.job_id} completed.")

        except Exception as e:
            print(f"Error in job {self.job_id}: {e}")
            try:
                state = self.state_manager.get_state()
                state.status = "FAILED"
                state.error = str(e)
                self.state_manager.save_state(state)
                yield state
            except Exception:
                pass
