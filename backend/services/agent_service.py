import json
from backend.app.core.config import settings
from typing import List
import google.generativeai as genai
from backend.app.core.schemas import ReActStep, AgentResponse, Action

class AgentService:
    def __init__(self):
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel("gemini-2.5-flash-lite")

    async def think(self, sub_query: str, memory: List[ReActStep]) -> AgentResponse:
        """
        (PROMPT) This is the "Think" step of the ReAct loop.
        Decides the next action to take using structured output.
        """

        prompt = self._build_react_prompt(sub_query, memory)

        try:
            response = await self.model.generate_content_async(
                prompt,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    response_schema=AgentResponse
                )
            )
            result = json.loads(response.text)
            
            return AgentResponse(**result)

        except Exception as e:
            print(f"❌ Error in agent.think(): {e}")
            # Fallback safe response
            return AgentResponse(
                thought="An error occurred during thinking. Concluding this loop.",
                action=Action(tool="final_answer", input="Error occurred"),
                confidence=0.0
            )

    def _build_react_prompt(self, sub_query: str, memory: List[ReActStep]) -> str:
        """Enhanced prompt for agentic decision-making."""
        
        history = "\n".join([
            f"Thought: {step.thought}\nAction: {step.action.tool}({step.action.input})\nObservation: {step.observation}"
            for step in memory
        ])
        
        prompt = f"""
        You are an AI research assistant with the ability to decide your next action.
        
        GOAL: Answer this query: "{sub_query}"
        
        AVAILABLE TOOLS:
        1. web_search(query: str): Search the web for information
        
        2. final_answer(answer: str): Call this when you have SUFFICIENT information to answer. 
           Put the comprehensive final answer in the 'input' field.
        
        YOUR WORK SO FAR:
        {history if history else "No actions taken yet."}
        
        DECISION RULES:
        - If you have NO information yet, start with a web search
        - If search results are insufficient, do MORE targeted searches
        - If you have enough information to answer, call final_answer
        - Be efficient: don't search more than necessary
        
        Respond with the JSON schema provided.
        """
        return prompt
