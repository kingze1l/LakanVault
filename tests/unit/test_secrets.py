"""Secret detector — sibling of PII, not merged into detectors.py."""
from lakanvault.local_core.secrets.detector import detect_secrets, shannon_entropy


def test_clean_text_has_no_secrets() -> None:
    assert detect_secrets("hello world") == []


def test_detects_openai_sk_token() -> None:
    hits = detect_secrets("My key is sk-abcdefghijklmnopqrstuvwxyz1234567890")
    assert len(hits) == 1
    assert hits[0].kind == "API_KEY"


def test_detects_github_pat() -> None:
    token = "ghp_" + ("a" * 36)
    hits = detect_secrets(f"token {token}")
    assert any(h.kind == "API_KEY" for h in hits)


def test_shannon_entropy_empty_is_zero() -> None:
    assert shannon_entropy("") == 0.0


def test_shannon_entropy_repeated_chars_is_low() -> None:
    assert shannon_entropy("aaaa") < 0.1


def test_shannon_entropy_mixed_is_higher() -> None:
    assert shannon_entropy("sk-abcdefghijklmnopqrstuvwxyz123456") > 4.0
