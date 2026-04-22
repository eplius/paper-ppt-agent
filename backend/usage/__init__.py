"""Token usage tracking for LLM calls.

Records every LLM invocation (provider, model, tokens, job, stage, cost)
and exposes aggregated views (per-job, per-day, per-model, totals).
Persisted to disk so usage survives backend restarts.
"""

from .tracker import (
    UsageEvent,
    UsageRecord,
    UsageSummary,
    usage_tracker,
)

__all__ = [
    "UsageEvent",
    "UsageRecord",
    "UsageSummary",
    "usage_tracker",
]
