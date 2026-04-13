# Pricing per 1M tokens (USD) — update when model pricing changes
MODEL_PRICING = {
    "gemini-2.5-flash-lite": {
        "input_per_1m": 0.075,
        "output_per_1m": 0.30,
    },
}

# Exa API cost per search call (USD)
EXA_COST_PER_SEARCH = 0.001


def estimate_llm_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost in USD for a single LLM call."""
    pricing = MODEL_PRICING.get(model)
    if not pricing:
        return 0.0

    input_cost = (input_tokens / 1_000_000) * pricing["input_per_1m"]
    output_cost = (output_tokens / 1_000_000) * pricing["output_per_1m"]
    return round(input_cost + output_cost, 8)
