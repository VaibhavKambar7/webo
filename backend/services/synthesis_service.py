from backend.app.core.config import settings
from backend.app.core.schemas import ReActStep
from typing import AsyncIterator, List
import google.generativeai as genai
from backend.app.core.constants import MAX_RAW_WINDOW_TOKENS
from backend.app.utils.token import count_tokens
from backend.app.core.cache import ChatManager
from fastapi import BackgroundTasks
from backend.app.services.chat_service import ChatService


class SynthesisService:
    def __init__(self, chat_id: str):
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel("gemini-2.5-flash-lite")
        self.chat_manager = ChatManager(chat_id)
        self.chat_service = ChatService()
        self.chat_id = chat_id

    async def summarize_stream(
        self,
        original_query: str,
        memory: List[ReActStep],
        background_tasks: BackgroundTasks = None,
    ) -> AsyncIterator[str]:
        """
        Streams the synthesized answer and triggers background summarization.
        """

        context = self._compile_context(memory)

        content = await self.chat_service.get_chat_state(self.chat_id)

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
            response = await self.model.generate_content_async(prompt, stream=True)

            final_answer = ""

            async for chunk in response:
                if chunk.text:
                    final_answer += chunk.text
                    yield chunk.text

            if background_tasks:
                background_tasks.add_task(
                    self.summarize_chat, original_query, final_answer
                )
            else:
                await self.summarize_chat(original_query, final_answer)

        except Exception as e:
            yield f"Error during synthesis: {e}"

    async def summarize_chat(self, original_query: str, final_answer: str):
        chat_content = await self.chat_service.get_chat_state(self.chat_id)

        recent_convo = chat_content.recent_convo
        older_convo = []

        recent_convo.append({"role": "user", "content": original_query})
        recent_convo.append({"role": "assistant", "content": final_answer})

        while count_tokens(recent_convo) > MAX_RAW_WINDOW_TOKENS:
            if len(recent_convo) <= 2:
                break

            older_convo.append(recent_convo.pop(0))
            older_convo.append(recent_convo.pop(0))

        prompt = f"""
        You are responsible for maintaining memory across a long conversation.

        Summarize the conversation turns provided below so that important details are not lost. Capture:

        - The user’s goals, questions, decisions, or constraints.
        - Relevant facts or reasoning the assistant previously provided.
        - Any key preferences or corrections by the user.

        Do NOT include filler talk or exact quotes.
        Do NOT exceed 6–8 sentences.

        Conversation to summarize:
        ---
        {older_convo}
        ---

        Provide a short memory summary that preserves essential context.
        """

        try:
            response = await self.model.generate_content_async(prompt)

            await self.chat_service.update_chat_summary(
                self.chat_id, summary=response.text, recent_convo=recent_convo
            )
        except Exception as e:
            print(f"Error during summary generation: {e}")

    def _compile_context(self, memory: List[ReActStep]) -> str:
        """Combines all observations into a single context block."""
        observations = [step.observation for step in memory if step.observation]
        if not observations:
            return "No information was gathered."
        return "\n\n---\n\n".join(observations)

    async def respond_from_context_stream(
        self, query: str, route: str
    ) -> AsyncIterator[str]:

        content = await self.chat_service.get_chat_state(self.chat_id)

        summary = content.summary
        recent_convo = content.recent_convo

        formatted_recent_convo = "\n".join(
            f"{m['role'].upper()} : {m['content']}" for m in recent_convo
        )

        prompt = f"""
        You are Webo, a context-aware assistant. Your job is to answer using ONLY conversation context provided below.

        ROUTE_LABEL: {route}
        USER_QUERY: "{query}"

        CONVERSATION SUMMARY (older turns):
        ---
        {summary}
        ---

        RECENT CONVERSATION:
        ---
        {formatted_recent_convo}
        ---

        INSTRUCTIONS:
        1) Use only the context above. Do NOT use external knowledge, web facts, or assumptions.
        2) If ROUTE_LABEL is NO_SEARCH_CHAT:
        - Reply naturally and briefly (1-3 short paragraphs).
        - Be conversational, helpful, and friendly.
        - Do not mention sources, web search, or limitations unless asked.
        3) If ROUTE_LABEL is MEMORY_ONLY:
        - Answer strictly from the provided chat context.
        - If context is insufficient or ambiguous, say exactly what is missing and ask one concise clarifying question.
        - Do not fabricate details.
        4) If the user asks for latest/current/news/prices and ROUTE_LABEL is not WEB_REQUIRED, explicitly state that this requires web lookup and ask for permission to search.
        5) Keep response clear, direct, and concise.
        6) Do not include chain-of-thought or internal reasoning.
        7) Output plain Markdown only.

        Now produce the final assistant response.
        """

        try:
            response = await self.model.generate_content_async(prompt, stream=True)
            final_answer = ""

            async for chunk in response:
                if chunk.text:
                    final_answer += chunk.text
                    yield chunk.text

            await self.summarize_chat(query, final_answer)

        except Exception as e:
            yield f"error during respond from context stream : {e}"
