"""Unit tests for reversible PII anonymization."""
from lakanvault.local_core.privacy.anonymizer import ReversibleAnonymizer
from lakanvault.local_core.privacy.detectors import find_pii_spans, reset_analyzer_cache


def setup_function() -> None:
    reset_analyzer_cache()


def test_name_intro_anonymized() -> None:
    anon = ReversibleAnonymizer()
    sanitized, mapping, engine = anon.anonymize("hi my name is smai")
    assert sanitized == "hi my name is NAME_001"
    assert mapping == {"NAME_001": "smai"}
    assert engine != "none"


def test_email_for_name_anonymized() -> None:
    anon = ReversibleAnonymizer()
    text = "write up an email for samiullah telling tutuot he cant make it today"
    sanitized, mapping, _engine = anon.anonymize(text)
    assert "samiullah" not in sanitized
    assert "tutuot" not in sanitized
    assert "samiullah" in mapping.values()
    assert "tutuot" in mapping.values()
    assert "the" not in mapping.values()


def test_restore_case_insensitive() -> None:
    mapping = {"NAME_001": "sami"}
    assert ReversibleAnonymizer.restore("Hello name_001!", mapping) == "Hello sami!"
    assert ReversibleAnonymizer.restore("Hello NAME_001!", mapping) == "Hello sami!"


def test_restore_placeholders() -> None:
    anon = ReversibleAnonymizer()
    _, mapping, _ = anon.anonymize("hi my name is smai")
    restored = ReversibleAnonymizer.restore("Hello NAME_001, welcome!", mapping)
    assert restored == "Hello smai, welcome!"


def test_email_anonymized() -> None:
    anon = ReversibleAnonymizer()
    sanitized, mapping, _ = anon.anonymize("reach me at alice@corp.io please")
    assert "EMAIL_001" in sanitized
    assert mapping["EMAIL_001"] == "alice@corp.io"


def test_find_pii_spans_email_context() -> None:
    spans, engine = find_pii_spans("email for samiullah", engine="regex")
    assert engine == "regex"
    texts = [s.text for s in spans]
    assert "samiullah" in texts
