import logging
import json
from typing import Any, Dict, List
from app.core.config import settings
from exa_py import Exa

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Create a file handler for search results
file_handler = logging.FileHandler('search_results.log')
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter('%(asctime)s - %(message)s')
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)


class WebSearcher:
    """
    a dedicated tool for searching the web using the exa api.
    """

    def __init__(self):
        try:
            self.exa_client = Exa(api_key=settings.EXA_API_KEY)
            logger.info("Exa client initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize Exa client: {e}")
            raise

    def _truncate_content(self, text: str, max_chars: int = 1500) -> str:
        """
        helper to truncate text
        """
        if not text:
            return ""
        return text[:max_chars] + "..." if len(text) > max_chars else text

    def search_and_scrape(
        self, query: str, num_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        performs a search and returns a list of processed results.
        """
        print(f"\n🔍 SEARCHING: {query}")
        try:
            search_results = self.exa_client.search_and_contents(
                query=query, text=True, num_results=num_results
            )

            # Log to file with pretty formatting
            logger.info(f"\n{'='*80}\nQUERY: {query}\n{'='*80}")
            logger.info(f"RAW SEARCH RESULTS:\n{json.dumps(search_results.__dict__, indent=2, default=str)}")

            print(f"✅ Got {len(getattr(search_results, 'results', []))} results")
        except Exception as e:
            logger.error(f"Error with Exa API for query '{query}': {e}")
            return []  

        processed_results: List[Dict[str, Any]] = []

        for result in getattr(search_results, "results", []):
            content = getattr(result, "text", None)
            
            if not content:
                logger.warning(f"Skipping result with no content: {result.url}")
                continue

            truncated_content = self._truncate_content(content)

            processed_results.append(
                {
                    "title": getattr(result, "title", "No Title"),
                    "url": getattr(result, "url", "No URL"),
                    "content": truncated_content,
                }
            )

        if not processed_results:
            logger.info(
                f"No relevant documents with content found for query: '{query}'"
            )

        return processed_results