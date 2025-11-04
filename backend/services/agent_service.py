import json
from openai import OpenAI
from app.core.config import settings
from app.core.schemas import ReActStep
from typing import List, Dict, Any

class AgentService:
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)

    def think(self, sub_query: str, memory: List[ReActStep]) -> Dict[str, Any]:
        """
        (PROMPT) This is the "Think" step of the ReAct loop.
        Decides the next action to take.
        """
        
        # Build the prompt
        prompt = self._build_react_prompt(sub_query, memory)
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            action_json = json.loads(response.choices[0].message.content)
            return action_json # Should match {"thought": "...", "action": {"tool": "...", "input": "..."}}
        
        except Exception:
            return {
                "thought": "An error occurred during thinking. Concluding this loop.",
                "action": {"tool": "final_answer", "input": None}
            }

    def _build_react_prompt(self, sub_query: str, memory: List[ReActStep]) -> str:
        """Helper to construct the ReAct prompt."""
        
        history = "\n".join([
            f"Thought: {step.thought}\nAction: {step.action.model_dump_json()}\nObservation: {step.observation}"
            for step in memory
        ])

        prompt = f"""
        You are an AI research assistant. Your current goal is to answer the sub-query: "{sub_query}"
        You will work step-by-step, using a Think-Action-Observation loop.

        Available tools:
        1. web_search(query: str): Searches the web for information.
        2. final_answer(): Call this when you have sufficient information to answer the sub-query.

        Here is your work history (Thought-Action-Observation):
        {history if history else "No history yet."}

        Based on your goal and history, what is your next thought and what single action should you take?
        Respond ONLY with a JSON object in this format:
        {{
          "thought": "Your reasoning for the next step...",
          "action": {{
            "tool": "tool_name",
            "input": "tool_input_or_null"
          }}
        }}
        """
        return prompt