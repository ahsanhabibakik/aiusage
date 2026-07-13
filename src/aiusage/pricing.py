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


# (input $/Mtok, output $/Mtok, cached-input $/Mtok) -- list-price estimates
# for the models the Codex CLI runs. "-mini" variants are matched first.
OPENAI_RATES = {
    "mini": (0.25, 2.00, 0.025),
    "nano": (0.05, 0.40, 0.005),
    "gpt-5": (1.25, 10.00, 0.125),
    "codex": (1.25, 10.00, 0.125),
}
DEFAULT_OPENAI_RATE = OPENAI_RATES["gpt-5"]


def rate_for_model(model: str):
    model = (model or "").lower()
    for key, rate in CLAUDE_RATES.items():
        if key in model:
            return rate
    return DEFAULT_CLAUDE_RATE


def estimate_codex_cost_usd(model: str, usage: dict) -> float:
    """usage is a codex token_count `last_token_usage` dict."""
    model = (model or "").lower()
    inp, out, cached = DEFAULT_OPENAI_RATE
    for key, rate in OPENAI_RATES.items():
        if key in model:
            inp, out, cached = rate
            break
    input_tokens = usage.get("input_tokens", 0) or 0
    cached_tokens = usage.get("cached_input_tokens", 0) or 0
    output_tokens = usage.get("output_tokens", 0) or 0
    # input_tokens includes the cached portion; bill the cached part at the
    # cached rate and the rest at the full rate.
    uncached = max(input_tokens - cached_tokens, 0)
    return (uncached * inp + cached_tokens * cached + output_tokens * out) / 1_000_000


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
