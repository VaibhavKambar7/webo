from openai import OpenAI
from app.core.config import settings
from app.core.schemas import ReActStep
from typing import List

class SynthesisService:
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)

    def summarize(self, original_query: str, memory: List[ReActStep]) -> str:
        """
        (PROMPT) Summarizes all observations into a final answer.
        """
        
        context = self._compile_context(memory)
        
        prompt = f"""
        You are an AI research assistant. Your task is to provide a comprehensive, synthesized answer to the user's original query, based *only* on the context provided from your research.

        User Query: "{original_query}"

        Research Context (from all sub-queries):
        ---
        {context}
        ---

        Instructions:
        1. Write a clear, concise, and comprehensive answer to the user's query.
        2. Base your answer *only* on the context provided. Do not use any outside knowledge.
        3. If the context includes sources (e.g., [Source 1]), cite them in your answer.
        4. If the context is insufficient, state that.
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error during final synthesis: {e}"

    def _compile_context(self, memory: List[ReActStep]) -> str:
        """Combines all observations into a single context block."""
        observations = [
            step.observation 
            for step in memory 
            if step.observation
        ]
        if not observations:
            return "No information was gathered."
        
        return "\n\n---\n\n".join(observations)