import json
from app.core.config import settings
from app.core.schemas import ReActStep
from typing import List, Dict, Any
import google.generativeai as genai

class AgentService:
    def __init__(self):
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel(
            "gemini-2.5-flash-lite",
            generation_config={"response_mime_type": "application/json"},
        )

    async def think(self, sub_query: str, memory: List[ReActStep]) -> Dict[str, Any]:
        """
        (PROMPT) This is the "Think" step of the ReAct loop.
        Decides the next action to take.
        """

        prompt = self._build_react_prompt(sub_query, memory)

        try:

            response = await self.model.generate_content_async(prompt)
            result = json.loads(response.text)
            return result


        except Exception as e:
            print(f"❌ Error in agent.think(): {e}")
            return {
                "thought": "An error occurred during thinking. Concluding this loop.",
                "action": {"tool": "final_answer", "input": None},
            }

    def _build_react_prompt(self, sub_query: str, memory: List[ReActStep]) -> str:
        """Enhanced prompt for agentic decision-making."""
        
        history = "\n".join([
            f"Thought: {step.thought}\nAction: {step.action.model_dump_json()}\nObservation: {step.observation}"
            for step in memory
        ])
        
        prompt = f"""
        You are an AI research assistant with the ability to decide your next action.
        
        GOAL: Answer this query: "{sub_query}"
        
        AVAILABLE TOOLS:
        1. web_search(query: str): Search the web for information
        - Use this when you need more information
        - Be specific with search queries
        - You can use this multiple times with different queries
        
        2. final_answer(): Call this when you have SUFFICIENT information to answer
        - Only use this when you're confident you can answer the query
        - Don't use this if you need more information
        
        YOUR WORK SO FAR:
        {history if history else "No actions taken yet."}
        
        DECISION RULES:
        - If you have NO information yet, start with a web search
        - If search results are insufficient, do MORE targeted searches
        - If search results are off-topic, try different search terms
        - If you have enough information to answer, call final_answer
        - Be efficient: don't search more than necessary
        - Maximum 5-7 searches for complex queries
        
        Based on your goal and work history, what should you do NEXT?
        
        Respond ONLY with JSON:
        {{
        "thought": "Your reasoning for the next step (1-2 sentences)",
        "action": {{
            "tool": "web_search" or "final_answer",
            "input": "search query" or null
        }}
        }}
        """
        return prompt
