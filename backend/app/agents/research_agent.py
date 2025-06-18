import logging
import os
from typing import Any, Dict, List

from app.core.config import settings
from app.tools.web_searcher import WebSearcher
from langchain.agents import AgentExecutor, create_react_agent
from langchain.tools import Tool
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI


logging.basicConfig(
    filename="research_agent.log",
    filemode="a",
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY


class ResearchAgent:
    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-3.5-turbo-16k", temperature=0.3)

        self._web_searcher_instance = WebSearcher()

        def _web_search_tool_func(query: str) -> str:
            logger.info(f"ResearchAgent: Calling WebSearcher for query: '{query}'")
            search_result = self._web_searcher_instance.web_search(query)

            summary = search_result.get("summary", "No summary available.")
            citations = search_result.get("citations", [])

            citation_str = ""
            if citations:
                citation_str = "\nSources:\n" + "\n".join(
                    [f"[{c['id']}] {c['title']} ({c['url']})" for c in citations]
                )

            observation_content = f"Search Result Summary:\n{summary}{citation_str}"
            logger.info(
                f"ResearchAgent: WebSearcher returned observation: {observation_content[:200]}..."
            )
            return observation_content

        self.web_search_tool = Tool(
            name="web_search_tool",
            description="Search the web for up-to-date information. Input should be a concise search query. Returns a summary of findings with explicit citations (e.g., [1] text).",
            func=_web_search_tool_func,
        )

        self.tools = [self.web_search_tool]

        self.prompt = PromptTemplate.from_template(
            """You are a highly intelligent and resourceful research assistant.
Your primary goal is to answer complex user queries comprehensively and accurately by performing web searches.

You have access to the following tools:

{tools}

Use the following format exactly:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, must be EXACTLY one of [{tool_names}]
Action Input: the input to the action, must be on the next line, and must be a valid string
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Follow these guidelines:
1. Analyze the user's query and identify ALL key aspects that need to be researched
2. Break down complex queries into manageable sub-queries
3. Use the web_search_tool effectively with concise search queries
4. If initial results are insufficient, refine your search or perform follow-up searches
5. For multi-part queries (e.g., comparison, analysis, recommendations), perform separate searches for each key aspect
6. Do NOT try to answer complex questions from a single search — run separate searches for each component
7. Synthesize ALL gathered information into clear, comprehensive answers
8. Cite sources clearly by referring to titles and URLs
9. Ensure your Final Answer addresses ALL parts of the original question
10. If the query asks for comparison, analysis, or recommendations, provide detailed responses with supporting evidence

IMPORTANT: Before providing your Final Answer, ensure you have gathered sufficient information about ALL aspects mentioned in the query. If you haven't fully researched all components, perform additional searches.

Question: {input}
{agent_scratchpad}"""
        )

        self.agent = create_react_agent(self.llm, self.tools, self.prompt)

        self.agent_executor = AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=20,
        )

        self.collected_citations: Dict[int, Dict[str, str]] = {}

    def research(self, query: str, chat_history: List[Any] = None) -> Dict[str, Any]:
        if chat_history is None:
            chat_history = []

        self.collected_citations = {}

        class CitationCollectorCallback(BaseCallbackHandler):
            def __init__(self, agent_instance):
                self.agent_instance = agent_instance
                self.final_summary_citations = []

            def on_tool_end(self, output: str, **kwargs: Any) -> Any:
                sources_start = output.find("\nSources:\n")
                if sources_start != -1:
                    sources_raw = output[sources_start + len("\nSources:\n") :].strip()
                    for line in sources_raw.split("\n"):
                        import re

                        match = re.match(r"\[(\d+)\] (.*) \((http.*)\)", line)
                        if match:
                            cit_id = int(match.group(1))
                            title = match.group(2)
                            url = match.group(3)
                            self.agent_instance.collected_citations[cit_id] = {
                                "id": cit_id,
                                "title": title,
                                "url": url,
                            }
                return None

        try:
            citation_collector = CitationCollectorCallback(self)

            is_complex_query = any(
                keyword in query.lower()
                for keyword in [
                    "compare",
                    "comparison",
                    "vs",
                    "versus",
                    "best",
                    "top",
                    "analyze",
                    "analysis",
                    "evaluate",
                    "review",
                    "recommend",
                    "recommendation",
                ]
            )

            result = self.agent_executor.invoke(
                {"input": query, "chat_history": chat_history},
                {"callbacks": [citation_collector]},
            )

            final_answer_text = result.get(
                "output", "I could not generate a comprehensive answer."
            )

            if is_complex_query and len(final_answer_text.strip()) < 300:
                logger.warning("Final answer seems insufficient for a complex query.")
                final_answer_text += "\n\n[Note: This appears to be a brief response. For more comprehensive analysis, additional research may be needed.]"

            logger.info(f"Final answer for query '{query}': {final_answer_text}")

            sorted_citations = sorted(
                self.collected_citations.values(), key=lambda x: x["id"]
            )

            return {
                "summary": final_answer_text,
                "citations": sorted_citations,
                "query": query,
            }
        except Exception as e:
            logger.error(
                f"Error during research execution for query '{query}': {e}",
                exc_info=True,
            )
            return {
                "summary": f"An error occurred while performing research: {e}",
                "citations": [],
                "query": query,
            }



if __name__ == "__main__":
    research_agent = ResearchAgent()

    logger.info("--- Starting Research Agent Demo ---")
    print("\n--- Starting Research Agent Demo ---")

    query1 = "Which early-stage AI startups received funding in 2024, who are their founders, and what other companies have those founders previously built or worked at?"
    response1 = research_agent.research(query1)

    print("\n" + "=" * 80 + "\n")
    print("--- Final Answer ---")
    print(f"Query: {response1['query']}")
    print(f"Summary:\n{response1['summary']}")
    print("\n--- Citations ---")
    for cit in response1["citations"]:
        print(f"[{cit['id']}] {cit['title']} ({cit['url']})")
    print("\n" + "=" * 80 + "\n")
