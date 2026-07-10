"""Normalized snapshot shapes shared by every provider and the local HTTP API."""
from dataclasses import dataclass, field, asdict
from typing import Optional, Any


@dataclass
class MetricLine:
    type: str  # "progress" | "text" | "badge" | "barChart"
    label: str
    used: Optional[float] = None
    limit: Optional[float] = None
    format: Optional[dict] = None
    resets_at: Optional[str] = None
    value: Optional[str] = None
    text: Optional[str] = None
    color: Optional[str] = None
    subtitle: Optional[str] = None
    # Burn-rate pacing (progress lines): how the window is projected to end.
    period_duration_ms: Optional[int] = None
    pace: Optional[dict] = None  # {"projected_used_pct", "verdict": "ok"|"tight"|"over"}
    # barChart lines: one {label, value, valueLabel} per day, oldest first.
    points: Optional[list] = None
    note: Optional[str] = None
    # text spend lines: optional per-model breakdown [{model, cost, tokens}]
    models: Optional[list] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None}


@dataclass
class ProviderSnapshot:
    provider_id: str
    display_name: str
    plan: Optional[str]
    lines: list
    fetched_at: str
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "providerId": self.provider_id,
            "displayName": self.display_name,
            "plan": self.plan,
            "lines": [l.to_dict() if isinstance(l, MetricLine) else l for l in self.lines],
            "fetchedAt": self.fetched_at,
            **({"error": self.error} if self.error else {}),
        }
