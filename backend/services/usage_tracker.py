from backend.app.core.cost import estimate_llm_cost, EXA_COST_PER_SEARCH


class UsageTracker:
    """Tracks token usage and estimated cost per job."""

    def __init__(self):
        self.total_input_tokens: int = 0
        self.total_output_tokens: int = 0
        self.web_search_count: int = 0
        self.llm_calls: list[dict] = []
        self.estimated_cost_usd: float = 0.0

    def record_llm_call(
        self,
        caller: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ):
        """Record a single LLM call's token usage."""
        cost = estimate_llm_cost(model, input_tokens, output_tokens)

        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.estimated_cost_usd += cost

        self.llm_calls.append({
            "caller": caller,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost,
        })

    def record_web_search(self):
        """Record a single web search API call."""
        self.web_search_count += 1
        self.estimated_cost_usd += EXA_COST_PER_SEARCH

    def get_summary(self) -> dict:
        """Return a summary dict suitable for trace attributes."""
        return {
            "usage.total_input_tokens": self.total_input_tokens,
            "usage.total_output_tokens": self.total_output_tokens,
            "usage.total_tokens": self.total_input_tokens + self.total_output_tokens,
            "usage.llm_call_count": len(self.llm_calls),
            "usage.web_search_count": self.web_search_count,
            "usage.estimated_cost_usd": round(self.estimated_cost_usd, 6),
            "usage.llm_calls": self.llm_calls,
        }
