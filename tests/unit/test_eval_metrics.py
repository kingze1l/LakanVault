"""RQ1/RQ2 metric helpers — precision/recall/F1 and latency summary."""
import pytest

from lakanvault.eval.metrics import latency_summary, precision_recall_f1


def test_perfect_scores() -> None:
    p, r, f1 = precision_recall_f1(tp=10, fp=0, fn=0)
    assert (p, r, f1) == (1.0, 1.0, 1.0)


def test_precision_recall_f1_known_values() -> None:
    p, r, f1 = precision_recall_f1(tp=8, fp=2, fn=2)
    assert p == pytest.approx(0.8)
    assert r == pytest.approx(0.8)
    assert f1 == pytest.approx(0.8)


def test_zero_predictions_are_zero() -> None:
    p, r, f1 = precision_recall_f1(tp=0, fp=0, fn=5)
    assert (p, r, f1) == (0.0, 0.0, 0.0)


def test_latency_summary() -> None:
    summary = latency_summary([10.0, 20.0, 30.0])
    assert summary["n"] == 3
    assert summary["mean_ms"] == 20.0
    assert summary["p50_ms"] == 20.0


def test_latency_summary_empty() -> None:
    summary = latency_summary([])
    assert summary["n"] == 0
    assert summary["mean_ms"] == 0.0
