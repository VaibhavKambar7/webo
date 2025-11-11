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
        You are an AI research assistant. Your task is to provide a comprehensive, synthesized answer to the user's original query based on the research context gathered.

        User Query: "{original_query}"

        Research Context (from all searches):
        ---
        {context}
        ---

        Instructions:
        1. Synthesize the information from ALL provided research context to create a comprehensive answer
        2. If the query asks for a comparison, structure your answer to clearly compare both subjects
        3. Use specific facts, figures, and details from the research context
        4. If sources are mentioned in the context (e.g., [Source 1]), reference them naturally in your answer
        5. Organize your answer with clear sections or bullet points for better readability
        6. If the research context provides relevant information, use it fully - don't claim insufficient information unless truly lacking
        7. For comparison queries, include: key differences, similarities, notable achievements, and relevant metrics

        Provide a well-structured, informative answer that directly addresses the user's query.
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