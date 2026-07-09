"""Claude Code usage provider.

Reads the same OAuth token Claude Code itself stores locally and hits the
same usage endpoint the official CLI/desktop app use. Also estimates local
spend by scanning Claude Code's own session logs -- no data leaves the
machine except the same API call Claude Code already makes.
"""
import json
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from ..config import claude_credentials_path, claude_projects_dir
from ..models import MetricLine, ProviderSnapshot
from ..pricing import estimate_cost_usd

USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
PROVIDER_ID = "claude"


def _load_token() -> Optional[str]:
    path = claude_credentials_path()
    if path.exists():
        try:
            data = json.loads(path.read_text())
            token = data.get("claudeAiOauth", {}).get("accessToken")
            if token:
                return token
        except Exception:
            pass
    return os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")


def _fetch_live_usage():
    """Returns (data, error_code). data is None on any failure; error_code
    distinguishes *why* so callers don't misreport a rate limit as a
    logged-out state."""
    token = _load_token()
    if not token:
        return None, "not_logged_in"
    req = urllib.request.Request(
        USAGE_URL,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode()), None
    except urllib.error.HTTPError as e:
        if e.code == 429:
            return None, "rate_limited"
        if e.code in (401, 403):
            return None, "not_logged_in"
        return None, "request_failed"
    except Exception:
        return None, "request_failed"


def _iter_assistant_messages():
    root = claude_projects_dir()
    if not root.exists():
        return
    for jsonl in root.rglob("*.jsonl"):
        try:
            with open(jsonl, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if entry.get("type") != "assistant":
                        continue
                    msg = entry.get("message") or {}
                    usage = msg.get("usage")
                    ts = entry.get("timestamp")
                    if usage and ts:
                        yield ts, msg.get("model", ""), usage
        except OSError:
            continue


def _local_spend_tiles() -> dict:
    now = datetime.now().astimezone()
    today_key = now.date()
    yesterday_key = today_key - timedelta(days=1)
    window_start = today_key - timedelta(days=29)

    per_day = {}  # date -> [cost, tokens]
    for ts, model, usage in _iter_assistant_messages():
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone()
        except (ValueError, AttributeError):
            continue
        day = dt.date()
        if day < window_start:
            continue
        cost = estimate_cost_usd(model, usage)
        tokens = sum(
            usage.get(k, 0) or 0
            for k in ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
        )
        entry = per_day.setdefault(day, [0.0, 0])
        entry[0] += cost
        entry[1] += tokens

    def fmt(day):
        if day not in per_day:
            return None
        cost, tokens = per_day[day]
        return _fmt_cost_tokens(cost, tokens)

    thirty_cost = sum(v[0] for v in per_day.values())
    thirty_tokens = sum(v[1] for v in per_day.values())
    thirty = _fmt_cost_tokens(thirty_cost, thirty_tokens) if per_day else None

    return {
        "today": fmt(today_key),
        "yesterday": fmt(yesterday_key),
        "last30": thirty,
    }


def _fmt_cost_tokens(cost: float, tokens: int) -> str:
    if tokens >= 1_000_000:
        tok_str = f"{tokens / 1_000_000:.1f}M tokens"
    elif tokens >= 1_000:
        tok_str = f"{tokens / 1_000:.1f}K tokens"
    else:
        tok_str = f"{tokens} tokens"
    return f"${cost:.2f} · {tok_str}"


_last_good_live = None
_last_good_at = None


def fetch_snapshot() -> ProviderSnapshot:
    global _last_good_live, _last_good_at
    now = datetime.now(timezone.utc).isoformat()
    live, error = _fetch_live_usage()
    stale = False

    if live:
        _last_good_live = live
        _last_good_at = now
    elif _last_good_live is not None:
        live = _last_good_live
        stale = True

    lines = []
    plan = None

    if live:
        five_hour = live.get("five_hour") or {}
        seven_day = live.get("seven_day") or {}
        if five_hour:
            lines.append(MetricLine(
                type="progress", label="Session",
                used=five_hour.get("utilization", 0.0), limit=100.0,
                format={"kind": "percent"}, resets_at=five_hour.get("resets_at"),
            ))
        if seven_day:
            lines.append(MetricLine(
                type="progress", label="Weekly",
                used=seven_day.get("utilization", 0.0), limit=100.0,
                format={"kind": "percent"}, resets_at=seven_day.get("resets_at"),
            ))
        for limit in live.get("limits") or []:
            scope = limit.get("scope") or {}
            model_name = (scope.get("model") or {}).get("display_name")
            if model_name and limit.get("kind") == "weekly_scoped":
                lines.append(MetricLine(
                    type="progress", label=f"Weekly ({model_name})",
                    used=limit.get("percent", 0.0), limit=100.0,
                    format={"kind": "percent"}, resets_at=limit.get("resets_at"),
                ))
        extra = live.get("extra_usage") or {}
        if extra.get("is_enabled"):
            lines.append(MetricLine(
                type="progress", label="Extra Usage",
                used=extra.get("utilization", 0.0), limit=100.0,
                format={"kind": "percent"},
            ))
        if stale:
            age_min = None
            try:
                age_min = round((datetime.now(timezone.utc) - datetime.fromisoformat(_last_good_at)).total_seconds() / 60)
            except Exception:
                pass
            age_text = f"{age_min} min ago" if age_min is not None else "earlier"
            lines.append(MetricLine(
                type="text", label="Live data",
                value=f"Last refreshed {age_text} ({error}) — showing last known values",
            ))
    else:
        messages = {
            "not_logged_in": "Not logged in — run `claude` and sign in",
            "rate_limited": "Rate limited by Anthropic — will retry shortly",
            "request_failed": "Couldn't reach api.anthropic.com — check your connection",
        }
        lines.append(MetricLine(type="text", label="Session", value=messages.get(error, "Unavailable")))

    tiles = _local_spend_tiles()
    for label, key in (("Today", "today"), ("Yesterday", "yesterday"), ("Last 30 Days", "last30")):
        val = tiles.get(key)
        lines.append(MetricLine(type="text", label=label, value=val or "No data"))

    return ProviderSnapshot(
        provider_id=PROVIDER_ID,
        display_name="Claude",
        plan=plan,
        lines=lines,
        fetched_at=now,
        error=error,
    )
