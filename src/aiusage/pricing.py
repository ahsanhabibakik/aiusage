"""Rough per-model $/token rates for estimating local spend from session logs.

Best-effort only -- Anthropic/OpenAI can change list prices at any time.
Rates are USD per token (list price, not cache-adjusted beyond the simple
read/write split below). Unknown models fall back to DEFAULT.
"""

# (input $/Mtok, output $/Mtok, cache_write $/Mtok, cache_read $/Mtok)
CLAUDE_RATES = {
    "opus": (15.00, 75.00, 18.75, 1.50),
    "sonnet": (3.00, 15.00, 3.75, 0.30),
    "haiku": (0.80, 4.00, 1.00, 0.08),
    "fable": (3.00, 15.00, 3.75, 0.30),
}
DEFAULT_CLAUDE_RATE = CLAUDE_RATES["sonnet"]


def rate_for_model(model: str):
    model = (model or "").lower()
    for key, rate in CLAUDE_RATES.items():
        if key in model:
            return rate
    return DEFAULT_CLAUDE_RATE


def estimate_cost_usd(model: str, usage: dict) -> float:
    inp, out, cache_w, cache_r = rate_for_model(model)
    input_tokens = usage.get("input_tokens", 0) or 0
    output_tokens = usage.get("output_tokens", 0) or 0
    cache_write = usage.get("cache_creation_input_tokens", 0) or 0
    cache_read = usage.get("cache_read_input_tokens", 0) or 0
    cost = (
        input_tokens * inp
        + output_tokens * out
        + cache_write * cache_w
        + cache_read * cache_r
    ) / 1_000_000
    return cost
