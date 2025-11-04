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
            self.state_manager.save_state(state)
            
            search_queries = self.decomposer.split_into_search_queries(state.original_query)
            state.sub_queries = search_queries
            self.state_manager.save_state(state)

            state.status = "WORKING"
            self.state_manager.save_state(state)
                        
            for query in search_queries:

                action = ReActAction(tool="web_search", input=query)
                current_step = ReActStep(
                    thought=f"Executing planned search: {query}", 
                    action=action
                )
                
                observation = self.tool.execute(action.tool, action.input)
                
                current_step.observation = observation
                state.memory.append(current_step)
                self.state_manager.save_state(state)
            
            state = self.state_manager.get_state()
            state.status = "SYNTHESIZING"
            self.state_manager.save_state(state)
            
            final_answer = self.synthesis.summarize(state.original_query, state.memory)
            
            state.final_answer = final_answer
            state.status = "COMPLETED"
            self.state_manager.save_state(state)
            print(f"Job {self.job_id} completed.")

        except Exception as e:
            print(f"Error in job {self.job_id}: {e}")
            try:
                state = self.state_manager.get_state()
                state.status = "FAILED"
                state.error = str(e)
                self.state_manager.save_state(state)
            except Exception:
                pass
    
    # def _run_react_loop(self, sub_query: str, max_steps: int = 4):
        
    #     """Runs the think act observe loop for a single subquery."""
    #     for i in range(max_steps):
    #         state = self.state_manager.get_state()

    #         action_data = self.agent.think(sub_query, state.memory)
            
    #         thought = action_data.get("thought", "No thought provided.")
    #         action = ReActAction(**action_data.get("action", {"tool": "final_answer"}))
            
    #         current_step = ReActStep(thought=thought, action=action)

    #         if action.tool == "final_answer":
    #             state.memory.append(current_step)
    #             self.state_manager.save_state(state)
    #             break
            
    #         observation = self.tool.execute(action.tool, action.input)
            
    #         current_step.observation = observation
    #         state.memory.append(current_step)
    #         self.state_manager.save_state(state)