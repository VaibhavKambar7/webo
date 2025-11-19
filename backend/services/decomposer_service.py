import json
import google.generativeai as genai
from app.core.config import settings
from typing import List


class DecomposerService:
    def __init__(self):
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel(
            "gemini-2.5-flash-lite",
            generation_config={"response_mime_type": "application/json"},
        )

    def split_into_search_queries(self, query: str) -> List[str]:
        """
        Splits a complex query into a list of specific, searchable queries.
        """

        prompt = f"""
        You are a search query decomposition expert. Analyze the user's query and determine 
        if it should be broken down into multiple searches.

        RULES:
        1. Decompose ONLY if needed.
        2. Simple comparisons → 2–3 focused searches max.
        3. Single-topic questions → return as-is.
        4. If decomposing, produce 2–4 queries max.
        5. Return STRICT JSON with: {{ "search_queries": [...] }}

        User Query: "{query}"
        """

        try:
            response = self.model.generate_content(prompt)
            result = json.loads(response.text)

            if isinstance(result, dict):
                return result.get("search_queries", [query])

            return [query]

        except Exception as e:
            print(f"Decomposer error → fallback: {e}")
            return [query]
