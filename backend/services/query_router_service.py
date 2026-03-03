import json
import logging

import google.generativeai as genai

from backend.app.core.config import settings
from backend.app.core.schemas import QueryRouteResponse
from backend.app.services.chat_service import ChatService

logger = logging.getLogger(__name__)


class QueryRouterService:
    def __init__(self, chat_id: str):
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel("gemini-2.5-flash-lite")
        self.chat_service = ChatService()
        self.chat_id = chat_id

    async def route(self, query: str) -> QueryRouteResponse:
        """
        Routes the query before workflow execution:
        - NO_SEARCH_CHAT: greeting/chitchat/meta conversation
        - MEMORY_ONLY: answer should come from chat history/context
        - WEB_REQUIRED: external/fresh information is needed
        """
        query = (query or "").strip()
        if not query:
            return QueryRouteResponse(
                route="NO_SEARCH_CHAT",
                reason="Empty query treated as conversational input.",
                confidence=1.0,
            )

        try:
            content = await self.chat_service.get_chat_state(self.chat_id)
            summary = content.summary or ""
            recent_convo = content.recent_convo or []
            formatted_recent_convo = "\n".join(
                f"{m.get('role', '').upper()}: {m.get('content', '')}"
                for m in recent_convo[-8:]
            )

            prompt = f"""
            You are a strict query router for a research assistant.

            Route this user query into exactly one label:
            1) NO_SEARCH_CHAT: greetings, small talk, social niceties, meta-chat.
            2) MEMORY_ONLY: can be answered from conversation memory/context.
            3) WEB_REQUIRED: needs external facts, verification, current info, or citations.

            User Query:
            "{query}"

            Conversation Summary:
            ---
            {summary}
            ---

            Recent Conversation:
            ---
            {formatted_recent_convo}
            ---

            Rules:
            - Prefer MEMORY_ONLY for follow-up questions clearly grounded in prior chat.
            - Use WEB_REQUIRED for requests with unknown entities/facts not in history.
            - Use WEB_REQUIRED for anything requiring "latest/current/recent/news/price".
            - If uncertain, choose WEB_REQUIRED.

            Return JSON only with this schema:
            {{
              "route": "NO_SEARCH_CHAT" | "MEMORY_ONLY" | "WEB_REQUIRED",
              "reason": "brief explanation",
              "confidence": 0.0
            }}
            """

            response = await self.model.generate_content_async(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.0,
                    response_mime_type="application/json",
                    response_schema=QueryRouteResponse,
                ),
            )
            result = json.loads(response.text)
            route = result.get("route")
            if route not in ["NO_SEARCH_CHAT", "MEMORY_ONLY", "WEB_REQUIRED"]:
                route = "WEB_REQUIRED"            
            reason = result.get("reason", "")
            confidence = float(result.get("confidence", 0.0))
            confidence = max(0.0, min(confidence, 1.0))
            parsed = QueryRouteResponse(
                route=route,
                reason=reason,
                confidence=confidence,
            )
            return parsed

        except Exception as e:
            logger.error(f"Query router error: {e}")
            return QueryRouteResponse(
                route="WEB_REQUIRED",
                reason="Router fallback on error.",
                confidence=0.0,
            )
