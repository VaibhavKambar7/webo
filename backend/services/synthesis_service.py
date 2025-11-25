from app.core.config import settings
from app.core.schemas import ChatState, ReActStep
from typing import List
import google.generativeai as genai
from app.core.constants import MAX_RAW_WINDOW_TOKENS
from app.utils.token import count_tokens
from app.core.state_manager import ChatManager
from fastapi import BackgroundTasks

class SynthesisService:
    def __init__(self, chat_id: str):
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel("gemini-2.5-flash-lite")
        self.chat_manager = ChatManager(chat_id)

    def summarize_stream(self, original_query: str, memory: List[ReActStep], background_tasks: BackgroundTasks):
        """
        Streams the synthesized answer and triggers background summarization.
        """

        context = self._compile_context(memory)

        content = self.chat_manager.get_summary()

        summary = content.summary
        recent_convo = content.recent_convo

        formatted_recent_convo = "\n".join(
            f"{m['role'].upper()} : {m['content']}" for m in recent_convo
        )

        prompt = f"""
        You are an AI research assistant. Your task is to provide a comprehensive, synthesized answer to the user's original query based on the research context gathered.

        User Query: "{original_query}"

        Research Context (from all searches):
        ---
        {context}
        ---
        Recent conversations:
        {formatted_recent_convo}
        ---
        Summary of older conversations:
        ---
        {summary}
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
            response = self.model.generate_content(prompt, stream=True)

            final_answer = ""

            for chunk in response:
                if chunk.text:
                    final_answer += chunk.text
                    yield chunk.text

            background_tasks.add_task(
                self.summarize_chat,
                original_query,
                final_answer
            )

        except Exception as e:
            return f"Error during synthesis: {e}"

    def summarize_chat(self, original_query: str, final_answer: str):
        chat_content = self.chat_manager.get_summary()

        recent_convo = chat_content.recent_convo
        older_convo = []

        recent_convo.append({"role": "user", "content": original_query})
        recent_convo.append({"role": "assistant", "content": final_answer})

        while count_tokens(recent_convo) > MAX_RAW_WINDOW_TOKENS:

            if len(recent_convo) <= 2:
                break # safety guard

            older_convo.append(recent_convo.pop(0))
            older_convo.append(recent_convo.pop(0))

        # need to feed older_convo into the prompt
        prompt = ""

        try:
            response = self.model.generate_content(prompt)

            chat_state = ChatState(
                chat_id=self.chat_manager.chat_id,
                summary=response.text,
                recent_convo=recent_convo
            )

            self.chat_manager.save_summary(chat_state)

        except Exception as e:
            return f"Error during summary generation: {e}"


    def _compile_context(self, memory: List[ReActStep]) -> str:
        """Combines all observations into a single context block."""
        observations = [step.observation for step in memory if step.observation]
        if not observations:
            return "No information was gathered."
        return "\n\n---\n\n".join(observations)
