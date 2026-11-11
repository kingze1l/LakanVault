# secret detector sibling of pii not merged into detectors
from lakanvault.local_core.secrets.detector import detect_secrets, shannon_entropy

# Avoid gitleaks global allowlist stopword "abcdefghijklmnopqrstuvwxyz".
FAKE_SK = "sk-9f8e7d6c5b4a3210fedcba0987654321zz"


def test_clean_text_has_no_secrets() -> None:
    assert detect_secrets("hello world") == []


def test_detects_openai_sk_token() -> None:
    hits = detect_secrets(f"My key is {FAKE_SK}")
    assert len(hits) >= 1
    assert any(h.entity_type in {"openai-sk-generic", "openai-api-key"} or h.tier.value == "SECRET" for h in hits)


def test_detects_uri_credentials() -> None:
    hits = detect_secrets("postgres://admin:SuperSecret99@db.example.com/app")
    assert any(h.entity_type == "uri-credentials" for h in hits)


def test_shannon_entropy_empty_is_zero() -> None:
    assert shannon_entropy("") == 0.0


def test_shannon_entropy_repeated_chars_is_low() -> None:
    assert shannon_entropy("aaaa") < 0.1


def test_shannon_entropy_mixed_is_higher() -> None:
    assert shannon_entropy("sk-9f8e7d6c5b4a3210fedcba0987654321") > 4.0
