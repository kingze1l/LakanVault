"""Eval helpers for RQ1 (precision/recall/F1) and RQ2 (latency)."""
from __future__ import annotations

import statistics


def precision_recall_f1(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    if tp < 0 or fp < 0 or fn < 0:
        raise ValueError("counts must be non-negative")
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    if precision + recall == 0.0:
        f1 = 0.0
    else:
        f1 = 2 * precision * recall / (precision + recall)
    return precision, recall, f1


def _percentile(ordered: list[float], pct: float) -> float:
    if not ordered:
        return 0.0
    if len(ordered) == 1:
        return float(ordered[0])
    rank = (pct / 100.0) * (len(ordered) - 1)
    lo = int(rank)
    hi = min(lo + 1, len(ordered) - 1)
    frac = rank - lo
    return float(ordered[lo] + (ordered[hi] - ordered[lo]) * frac)


def latency_summary(samples_ms: list[float]) -> dict[str, float]:
    if not samples_ms:
        return {"n": 0, "mean_ms": 0.0, "p50_ms": 0.0, "p95_ms": 0.0}
    ordered = sorted(samples_ms)
    return {
        "n": float(len(ordered)),
        "mean_ms": statistics.fmean(ordered),
        "p50_ms": statistics.median(ordered),
        "p95_ms": _percentile(ordered, 95.0),
    }
