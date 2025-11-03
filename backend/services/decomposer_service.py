import json
from openai import OpenAI
from core.config import settings
from typing import List

class Decomposer:
    def __init__(self):
        self.client = OpenAI(api_key = settings.OPENAI_API_KEY)

    def split(self,query: str) -> List[str]:
        """splits a query into subqueries"""
        if len(query.split()) < 8:
            return [query]

        prompt = f"""
        You are a query decomposer. Your job is to split a complex user query into a series of simpler, logical sub-queries that can be answered sequentially.

        If the query is simple, return it as a single-item list.
        If complex, split it. For example:
        "Compare Rust and Go for web backends in terms of performance and community support"
        Becomes:
        ["What are the performance characteristics of Rust for web backends?", "What are the performance characteristics of Go for web backends?", "How large is the community support for Rust?", "How large is the community support for Go?", "Summary of Rust vs Go for web backends"]

        Respond ONLY with a JSON list of strings.
        
        Query: "{query}"
        """

        try:
            response = self.client.chat.completions(
                model = "gpt-4o-mini",
                messages = [{"role":"user","content":prompt}],
                response_format = {"type":"json_object"}
            )

            result = json.loads(response.choices[0].message.content)

            if isinstance(result,dict):
                key = next(iter(result))
                return result[key]
            return result
        except Exception:
            return query