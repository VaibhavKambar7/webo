import json
from openai import OpenAI
from app.core.config import settings
from typing import List

class DecomposerService:
    def __init__(self):
        self.client = OpenAI(api_key = settings.OPENAI_API_KEY)

    
    def split_into_search_queries(self, query: str) -> List[str]:
        """
        splits a complex query into a list of specific, searchable queries.
        """
        
        if len(query.split()) < 5:
            return [query]

        prompt = f"""
        You are a search query generator. Your job is to break down a complex user query into a list of 3-5 specific, high-quality search queries that can be run on a web search engine.

        User Query: "Compare Rust and Go for web backends in terms of performance and community support"
        
        Example Output:
        {{
          "search_queries": [
            "Rust vs Go web backend performance benchmarks 2025",
            "Go web framework (Gin, Echo) performance",
            "Rust web framework (Actix-web, Rocket) performance",
            "Rust developer community size vs Go community size",
            "Go vs Rust for web backend pros and cons"
          ]
        }}

        Respond ONLY with a JSON object containing a "search_queries" list.
        
        User Query: "{query}"
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            result = json.loads(response.choices[0].message.content)
            
            if isinstance(result, dict):
                key = next(iter(result))
                return result.get(key, [query])
            return result
        
        except Exception as e:
            print(f"Error in decomposer, falling back to single query: {e}")
            return [query]
