from app.tools.web_searcher import WebSearcher
from typing import List, Any, Dict
import logging

logger = logging.getLogger(__name__)


class ToolService:
    def __init__(self):
        self.web_searcher = WebSearcher()

    def execute(self, tool_name: str, tool_input: str) -> str:
        """
        router to execute the correct tool and return a string observation.
        """
        observation = ""

        try:
            if tool_name == "web_search":
                results = self.web_searcher.search_and_scrape(tool_input)
                observation = self._format_search_results(results)
                print(f"📝 Formatted observation length: {len(observation)} chars")

            else:
                observation = f"Error: unknown tool '{tool_name}'."

        except Exception as e:
            observation = f"Error executing tool {tool_name}: {e}"
            logger.error(f"Tool execution error: {e}")

        return observation, results

    def _format_search_results(self, results: List[Dict[str, Any]]) -> str:
        """Converts search results into a simple string for the LLM."""
        if not results:
            return "No search results found."

        formatted_parts = []
        for idx, result in enumerate(results, 1):
            formatted_parts.append(
                f"[Source {idx}]\n"
                f"Title: {result.get('title', 'No title')}\n"
                f"URL: {result.get('url', 'No URL')}\n"
                f"Favicon: {result.get('favicon', 'No Favicon')}\n"
                f"Content: {result.get('content', 'No content')}\n"
            )

        return "\n---\n".join(formatted_parts)
