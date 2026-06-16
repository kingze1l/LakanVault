"""Unit tests for reversible PII anonymization."""
from lakanvault.local_core.privacy.anonymizer import ReversibleAnonymizer


def test_name_intro_anonymized() -> None:
    anon = ReversibleAnonymizer()
    sanitized, mapping = anon.anonymize("hi my name is smai")
    assert sanitized == "hi my name is NAME_001"
    assert mapping == {"NAME_001": "smai"}


def test_restore_placeholders() -> None:
    anon = ReversibleAnonymizer()
    _, mapping = anon.anonymize("hi my name is smai")
    restored = ReversibleAnonymizer.restore("Hello NAME_001, welcome!", mapping)
    assert restored == "Hello smai, welcome!"


def test_email_anonymized() -> None:
    anon = ReversibleAnonymizer()
    sanitized, mapping = anon.anonymize("reach me at alice@corp.io please")
    assert "EMAIL_001" in sanitized
    assert mapping["EMAIL_001"] == "alice@corp.io"
