import json
from openai import OpenAI
from app.core.config import settings
from typing import List


class DecomposerService:
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)

    def split_into_search_queries(self, query: str) -> List[str]:
        """
        splits a complex query into a list of specific, searchable queries.
        """

        prompt = f"""
        You are a search query decomposition expert. Analyze the user's query and determine if it needs to be broken down into multiple searches.

        IMPORTANT RULES:
        1. ONLY decompose if the query is genuinely complex and requires multiple distinct information searches
        2. Simple comparisons (e.g., "compare X and Y") should become 2-3 focused searches maximum
        3. Single-topic questions should NOT be decomposed - return them as-is
        4. If decomposing, create 2-4 specific search queries (not more than 4)
        5. Each search query should be concise and focused on a specific aspect

        Examples:

        Query: "What is machine learning?"
        Output: {{"search_queries": ["What is machine learning?"]}}

        Query: "Compare Elon Musk and Mukesh Ambani"
        Output: {{"search_queries": ["Elon Musk net worth business ventures 2025", "Mukesh Ambani net worth business ventures 2025"]}}

        Query: "Compare Rust and Go for web backends in terms of performance, community support, and ecosystem"
        Output: {{
          "search_queries": [
            "Rust vs Go web backend performance benchmarks 2025",
            "Rust vs Go community size adoption 2025",
            "Rust vs Go web frameworks ecosystem comparison"
          ]
        }}

        Query: "What are the best AI startups in 2025?"
        Output: {{"search_queries": ["best AI startups 2025"]}}

        Now analyze this query:
        User Query: "{query}"

        Respond ONLY with a JSON object containing a "search_queries" list.
        """

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )
            result = json.loads(response.choices[0].message.content)

            if isinstance(result, dict):
                key = next(iter(result))
                return result.get(key, [query])
            return result

        except Exception as e:
            print(f"Error in decomposer, falling back to single query: {e}")
            return [query]
