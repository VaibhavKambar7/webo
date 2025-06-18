import json
import logging
from typing import Any, Dict

from app.core.config import settings
from exa_py import Exa
from openai import OpenAI

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)


class WebSearcher:
    def __init__(self):
        self.exa_client = Exa(settings.EXA_API_KEY)
        self.openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)

    def truncate_content(self, text: str, max_chars: int) -> str:
        """Truncates text to max_chars, adding '...' if truncated."""
        if not text:
            return ""
        return text[:max_chars] + "..." if len(text) > max_chars else text

    def web_search(self, query: str, num_results: int = 5) -> Dict[str, Any]:
        logger.info(f"Executing search for query: '{query}'")
        try:
            search_results = self.exa_client.search_and_contents(
                query=query, text=True, num_results=num_results
            )
        except Exception as e:
            logger.error(f"Error with Exa API for query '{query}': {e}")
            return {"summary": f"Error with Exa API: {e}", "citations": []}

        processed_documents_for_llm = []
        source_id_map = {}
        MAX_INTERNAL_LLM_CONTEXT_CHARS = 8000
        total_chars_for_context = 0
        current_id = 1

        for result in getattr(search_results, "results", []):
            if not getattr(result, "text", None):
                continue

            truncated_content = self.truncate_content(result.text, max_chars=1500)
            source_content_str = (
                f"--- Source ID: {current_id} ---\n"
                f"Title: {result.title}\n"
                f"URL: {result.url}\n"
                f"Content: {truncated_content}\n"
            )

            if (
                total_chars_for_context + len(source_content_str)
                > MAX_INTERNAL_LLM_CONTEXT_CHARS
            ):
                logger.info(
                    f"Context limit reached. Stopping at {current_id - 1} documents."
                )
                break

            total_chars_for_context += len(source_content_str)
            processed_documents_for_llm.append(source_content_str)
            source_id_map[current_id] = {
                "id": current_id,
                "title": result.title,
                "url": result.url,
            }
            current_id += 1

        if not processed_documents_for_llm:
            logger.info(
                f"No relevant documents with content found for query: '{query}'"
            )
            return {"summary": "No relevant documents found.", "citations": []}

        context_for_llm_summary = "\n\n".join(processed_documents_for_llm)
        prompt = self._create_comprehensive_prompt(query, context_for_llm_summary)

        try:
            logger.info("Generating comprehensive summary with OpenAI model.")
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert research assistant.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=1500,
                temperature=0.3,
            )

            response_text = response.choices[0].message.content

            try:
                llm_output = json.loads(response_text)
                summary_text = llm_output.get("summary", "Summary not generated.")
                citations_used_by_llm = llm_output.get("citations_used", [])
            except json.JSONDecodeError as e:
                logger.error(
                    f"Failed to decode JSON from OpenAI. Trying fallback approach: {e}"
                )
                return self._generate_fallback_summary(
                    query, context_for_llm_summary, source_id_map
                )

            final_citations = []
            for cit_id in sorted(list(set(citations_used_by_llm))):
                if cit_id in source_id_map:
                    final_citations.append(source_id_map[cit_id])

            if not final_citations and source_id_map:
                final_citations = list(source_id_map.values())
                logger.info(
                    "No citations found in LLM response, including all processed sources as citations."
                )

            return {"summary": summary_text, "citations": final_citations}

        except Exception as e:
            logger.error(f"Error with OpenAI API during summary generation: {e}")
            return self._generate_fallback_summary(
                query, context_for_llm_summary, source_id_map
            )

    def _create_comprehensive_prompt(self, query: str, context: str) -> str:
        return f"""You are an expert research assistant. Analyze the provided sources and create a comprehensive, detailed summary that directly addresses the user's query.

            CRITICAL INSTRUCTIONS:
            1. Create a detailed summary (300-500 words) that thoroughly addresses the query.
            2. Include specific details, comparisons, recommendations, prices, specifications when available and relevant to the query.
            3. For each piece of information, cite the source using [ID] format (e.g., [1], [2]). Ensure IDs correspond to the Source IDs provided.
            4. If the query asks for comparisons, provide detailed comparisons.
            5. If asking for recommendations, provide clear recommendations with reasoning based on the sources.
            6. Synthesize information from multiple sources when possible. Do not just summarize one source at a time.
            7. If crucial information is genuinely missing from all provided sources to answer a part of the query, you can state that for that specific part, but focus on what IS available.
            8. Structure your response clearly with relevant sections/points if it aids readability for a complex query.
            9. Be comprehensive and actionable.

            Query: {query}

            Sources:
            {context}

            Return a JSON object with two keys:
            - "summary": A comprehensive, well-structured summary with inline citations like [1], [2], etc.
            - "citations_used": An array of ONLY the integer Source IDs that you referenced in the summary (e.g., [1, 2, 3]).
            """

    def _generate_fallback_summary(
        self, query: str, context: str, source_id_map: Dict[int, Dict[str, str]]
    ) -> Dict[str, Any]:
        logger.info("Attempting to generate fallback summary.")
        try:
            simple_prompt = f"""Based on the following sources, provide a comprehensive summary (300-400 words) for this query: {query}

            Include citations as [ID] (e.g., [1], [2]) throughout your response, corresponding to the Source IDs in the provided context.

            Sources:
            {context}

            Summary:"""

            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert research assistant.",
                    },
                    {"role": "user", "content": simple_prompt},
                ],
                max_tokens=1000,
                temperature=0.3,
            )

            summary_text = response.choices[0].message.content

            import re

            citations_used_ids = []
            if summary_text:
                citation_matches = re.findall(r"\[(\d+)\]", summary_text)
                for match in citation_matches:
                    try:
                        citations_used_ids.append(int(match))
                    except ValueError:
                        logger.warning(
                            f"Fallback summary produced invalid citation format: [{match}]"
                        )

            final_citations = []
            if citations_used_ids:
                for cit_id in sorted(list(set(citations_used_ids))):
                    if cit_id in source_id_map:
                        final_citations.append(source_id_map[cit_id])
            elif source_id_map:
                logger.info(
                    "No citations extracted from fallback summary, including all processed sources."
                )
                final_citations = list(source_id_map.values())

            return {"summary": summary_text, "citations": final_citations}

        except Exception as e:
            logger.error(f"Fallback summary generation itself failed: {e}")
            return {
                "summary": f"Error generating comprehensive summary: {e}",
                "citations": list(source_id_map.values()) if source_id_map else [],
            }
