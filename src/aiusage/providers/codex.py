"""Codex (ChatGPT) usage provider.

Live limits come from the same endpoint the Codex CLI itself uses
(chatgpt.com/backend-api/wham/usage) with the OAuth token the CLI stores in
~/.codex/auth.json. If that call fails, the most recent `rate_limits`
snapshot embedded in the CLI's own session logs is used instead (every
Codex turn records one), marked stale. Spend is computed locally from the
same logs -- `turn_context` entries carry the model, `token_count` events
carry per-turn usage.
"""
import json
from datetime import datetime, timezone, timedelta
import urllib.request
import urllib.error

from ..config import codex_home_dir
from ..models import MetricLine, ProviderSnapshot
from ..pricing import estimate_codex_cost_usd
from .common import compute_pace, fmt_cost_tokens, epoch_to_iso

PROVIDER_ID = "codex"
USAGE_URL = "https://chatgpt.com/backend-api/wham/usage"


def available() -> bool:
    return codex_home_dir().exists()


def _auth():
    try:
        data = json.loads((codex_home_dir() / "auth.json").read_text())
        tokens = data.get("tokens") or {}
        return tokens.get("access_token"), tokens.get("account_id")
    except Exception:
        return None, None


def _fetch_live_usage():
    token, account_id = _auth()
    if not token:
        return None, "not_logged_in"
    headers = {"Authorization": f"Bearer {token}"}
    if account_id:
        headers["chatgpt-account-id"] = account_id
    req = urllib.request.Request(USAGE_URL, headers=headers)
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


def _session_files():
    home = codex_home_dir()
    for sub in ("sessions", "archived_sessions"):
        root = home / sub
        if root.exists():
            yield from root.rglob("*.jsonl")


def _window_label(window_minutes):
    if window_minutes is None:
        return "Window"
    if window_minutes <= 600:
        return "Session"
    return "Weekly"


def _limit_lines_from(rate_limits, stale_note=None):
    """Normalize a codex rate_limits dict (from the API or from session
    logs -- same shape) into progress MetricLines."""
    lines = []
    for key in ("primary", "secondary"):
        window = rate_limits.get(key)
        if not window or window.get("used_percent") is None:
            continue
        minutes = window.get("window_minutes")
        resets = window.get("resets_at")
        resets_iso = epoch_to_iso(resets) if isinstance(resets, (int, float)) else resets
        window_ms = minutes * 60000 if minutes else None
        lines.append(MetricLine(
            type="progress", label=_window_label(minutes),
            used=window.get("used_percent", 0.0), limit=100.0,
            format={"kind": "percent"}, resets_at=resets_iso,
            period_duration_ms=window_ms,
            pace=compute_pace(window.get("used_percent"), resets_iso, window_ms) if window_ms else None,
        ))
    plan = rate_limits.get("plan_type")
    return lines, (plan.title() if isinstance(plan, str) else None)


def _normalize_live(live):
    """The wham/usage API nests windows under rate_limit.{primary,secondary}_window
    with slightly different field names than the CLI's logged rate_limits.
    Normalize to the logged shape so one renderer handles both."""
    rl = live.get("rate_limit")
    if not isinstance(rl, dict):
        return None
    out = {"plan_type": live.get("plan_type")}
    found = False
    for src, dst in (("primary_window", "primary"), ("secondary_window", "secondary")):
        window = rl.get(src)
        if not isinstance(window, dict) or window.get("used_percent") is None:
            continue
        seconds = window.get("limit_window_seconds")
        out[dst] = {
            "used_percent": window.get("used_percent"),
            "window_minutes": round(seconds / 60) if seconds else None,
            "resets_at": window.get("reset_at"),
        }
        found = True
    return out if found else None


def _latest_logged_rate_limits():
    """Newest rate_limits event across session logs, with its timestamp."""
    best = (None, None)
    for path in _session_files():
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if '"rate_limits"' not in line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    rl = (entry.get("payload") or {}).get("rate_limits")
                    ts = entry.get("timestamp")
                    if rl and ts and (best[1] is None or ts > best[1]):
                        best = (rl, ts)
        except OSError:
            continue
    return best


def _local_spend_tiles():
    now = datetime.now().astimezone()
    today_key = now.date()
    yesterday_key = today_key - timedelta(days=1)
    window_start = today_key - timedelta(days=29)

    per_day = {}
    per_day_models = {}
    for path in _session_files():
        current_model = ""
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    payload = entry.get("payload") or {}
                    if entry.get("type") == "turn_context" and payload.get("model"):
                        current_model = payload["model"]
                        continue
                    if payload.get("type") != "token_count":
                        continue
                    usage = (payload.get("info") or {}).get("last_token_usage")
                    ts = entry.get("timestamp")
                    if not usage or not ts:
                        continue
                    try:
                        day = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone().date()
                    except (ValueError, AttributeError):
                        continue
                    if day < window_start:
                        continue
                    cost = estimate_codex_cost_usd(current_model, usage)
                    tokens = (usage.get("input_tokens", 0) or 0) + (usage.get("output_tokens", 0) or 0)
                    d = per_day.setdefault(day, [0.0, 0])
                    d[0] += cost
                    d[1] += tokens
                    m = per_day_models.setdefault(day, {}).setdefault(current_model or "unknown", [0.0, 0])
                    m[0] += cost
                    m[1] += tokens
        except OSError:
            continue

    def fmt(day):
        if day not in per_day:
            return None
        cost, tokens = per_day[day]
        return fmt_cost_tokens(cost, tokens)

    def model_breakdown(day):
        models = per_day_models.get(day)
        if not models:
            return None
        ranked = sorted(models.items(), key=lambda kv: kv[1][0], reverse=True)
        return [{"model": n, "cost": round(c, 2), "tokens": t} for n, (c, t) in ranked]

    thirty_cost = sum(v[0] for v in per_day.values())
    thirty_tokens = sum(v[1] for v in per_day.values())
    trend = [
        {
            "label": day.strftime("%b %d").replace(" 0", " "),
            "value": per_day[day][1],
            "valueLabel": fmt_cost_tokens(per_day[day][0], per_day[day][1]),
        }
        for day in sorted(per_day)
    ]
    return {
        "today": fmt(today_key),
        "yesterday": fmt(yesterday_key),
        "last30": fmt_cost_tokens(thirty_cost, thirty_tokens) if per_day else None,
        "today_models": model_breakdown(today_key),
        "yesterday_models": model_breakdown(yesterday_key),
        "trend": trend or None,
    }


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

    rate_limits = _normalize_live(live) if live else None
    if rate_limits:
        lines, plan = _limit_lines_from(rate_limits)
        resets = (live.get("rate_limit_reset_credits") or {}).get("available_count")
        if resets is not None:
            lines.append(MetricLine(type="text", label="Rate Limit Resets", value=f"{resets} available"))
        if stale:
            lines.append(MetricLine(
                type="text", label="Live data",
                value=f"Live refresh failed ({error}) — showing last known values",
            ))
    else:
        # No live API data -- fall back to the newest rate_limits the Codex
        # CLI itself recorded in its session logs.
        logged, ts = _latest_logged_rate_limits()
        if logged:
            lines, plan = _limit_lines_from(logged)
            age = ""
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                age = f" from {round((datetime.now(timezone.utc) - dt).total_seconds() / 3600)}h ago"
            except Exception:
                pass
            lines.append(MetricLine(
                type="text", label="Live data",
                value=f"From local Codex logs{age} ({error}) — run `codex` to refresh",
            ))
        else:
            messages = {
                "not_logged_in": "Not logged in — run `codex` and sign in",
                "rate_limited": "Rate limited by OpenAI — will retry shortly",
                "request_failed": "Couldn't reach chatgpt.com — check your connection",
            }
            lines.append(MetricLine(type="text", label="Session", value=messages.get(error, "Unavailable")))

    tiles = _local_spend_tiles()
    for label, key, models_key in (
        ("Today", "today", "today_models"),
        ("Yesterday", "yesterday", "yesterday_models"),
        ("Last 30 Days", "last30", None),
    ):
        lines.append(MetricLine(
            type="text", label=label, value=tiles.get(key) or "No data",
            models=tiles.get(models_key) if models_key else None,
        ))
    if tiles.get("trend"):
        lines.append(MetricLine(
            type="barChart", label="Usage Trend",
            points=tiles["trend"],
            note="Estimated from local Codex CLI logs at API rates.",
        ))

    return ProviderSnapshot(
        provider_id=PROVIDER_ID,
        display_name="Codex",
        plan=plan,
        lines=lines,
        fetched_at=now,
        error=error,
    )
