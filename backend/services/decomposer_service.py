import json
import google.generativeai as genai
from backend.app.core.config import settings
from typing import List
from backend.app.services.chat_service import ChatService


class DecomposerService:
    def __init__(self, chat_id: str):
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel(
            "gemini-2.5-flash-lite",
            generation_config={"response_mime_type": "application/json"},
        )
        self.chat_service = ChatService()
        self.chat_id = chat_id

    async def split_into_search_queries(self, query: str) -> List[str]:

        content = await self.chat_service.get_chat_state(self.chat_id)

        summary = content.summary or None
        recent_convo = content.recent_convo or []

        formatted_recent_convo = "\n".join(
            f"{m['role'].upper()}:{m['content']}" for m in recent_convo
        )

        """
        Splits a complex query into a list of specific, searchable queries.
        """

        prompt = f"""
        You are a search query decomposition expert. You MUST maintain conversational context and long-term memory.

        Long-Term Summary:
        ---
        {summary}
        ---

        Recent Conversation:
        ---
        {formatted_recent_convo}
        ---

        User Query:
        "{query}"

        Rules:
        1. Consider ALL context above. If user intent is clarified earlier, use that meaning.
        2. Simple or single-topic questions → return exactly 1 search query.
        3. Comparisons → 2–4 focused search queries max.
        4. Include details from history IF needed to preserve continuity (e.g. specific product names, constraints).
        5. STRICT JSON output:
        {{
        "search_queries": ["..."]
        }}
        6. Queries must target factual, verifiable information — NOT rumors, controversy,
        drama, or unconfirmed speculation.
        7. Extract the smallest meaningful components of the user request
        (attributes, comparisons, measurable properties, contextual constraints).
        8. Avoid sentiment-driven terms unless the user explicitly asks for opinions or reactions.
        9. Use domain-appropriate keywords:
        - For people → job/role, achievements, biography, measurable characteristics
        - For products → specs, pricing, reviews from reputable sources
        - For places → location details, services, access, history
        10. If a comparison is requested, generate balanced, parallel queries
            (same category of information for each subject).


        Output ONLY valid JSON. No explanations.
    """

        try:
            response = await self.model.generate_content_async(prompt)
            result = json.loads(response.text)

            if isinstance(result, dict):
                return result.get("search_queries", [query])

            return [query]

        except Exception as e:
            print(f"Decomposer error → fallback: {e}")
            return [query]
