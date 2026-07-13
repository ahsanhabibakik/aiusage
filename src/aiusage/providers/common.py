"""Helpers shared by all providers."""
from datetime import datetime, timezone


def compute_pace(used_pct, resets_at, window_ms):
    """Burn-rate projection: if you keep burning at the current rate, where
    does this window land at reset? verdict: ok (>=10% spare), tight (<10%
    spare), over (projected past the limit). Skips windows too young to
    project (<5% elapsed)."""
    if used_pct is None or not resets_at:
        return None
    try:
        reset_dt = datetime.fromisoformat(str(resets_at).replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    remaining_ms = (reset_dt - datetime.now(timezone.utc)).total_seconds() * 1000
    elapsed_ms = window_ms - remaining_ms
    if elapsed_ms < window_ms * 0.05 or elapsed_ms <= 0:
        return None
    projected = used_pct / elapsed_ms * window_ms
    if projected > 100:
        verdict = "over"
    elif projected > 90:
        verdict = "tight"
    else:
        verdict = "ok"
    return {"projected_used_pct": round(min(projected, 999)), "verdict": verdict}


def fmt_cost_tokens(cost, tokens):
    if tokens >= 1_000_000:
        tok_str = f"{tokens / 1_000_000:.1f}M tokens"
    elif tokens >= 1_000:
        tok_str = f"{tokens / 1_000:.1f}K tokens"
    else:
        tok_str = f"{tokens} tokens"
    return f"${cost:.2f} · {tok_str}"


def epoch_to_iso(epoch_seconds):
    try:
        return datetime.fromtimestamp(float(epoch_seconds), tz=timezone.utc).isoformat()
    except (ValueError, TypeError, OSError):
        return None
