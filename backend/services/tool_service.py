from app.tools.web_searcher import WebSearcher
from typing import List, Any, Dict

class ToolService:
    def __init___(self):
        self.web_searcher = WebSearcher()

    def execute(self,tool_name:str,tool_input:str) -> str:
        """
        router to execute the correct tool and return a string observation.
        """
        observation = ""

        try:
            if tool_name == "web_search":
                results = self.web_searcher.search_and_scrape(tool_input)
                observation = self._format_search_results(results)


            else:
                observation = f" Error: unknown tool'{tool_name}."

        except Exception as e:
            observation = f"Error executing tool {tool_name} : {e}"

        return observation

    def _format_search_results(self, results: List[Dict[str,Any]]) -> str:
        """Converts search results into a simple string for the LLM."""

    