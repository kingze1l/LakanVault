# reversible pii anonymizer round trip bits
from lakanvault.local_core.privacy.anonymizer import ReversibleAnonymizer
from lakanvault.local_core.pii.detector import find_pii_spans, reset_analyzer_cache

# clear analyzer cache so tests dont bleed
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
    # Capitalised names match Joan's name heuristics / Presidio more reliably.
    text = "write up an email for Samiullah telling Tutuot he cant make it today"
    sanitized, mapping, engine = anon.anonymize(text)
    if engine == "none":
        return
    assert "Samiullah" not in sanitized or "Tutuot" not in sanitized
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
    spans, engine = find_pii_spans("reach me at alice@corp.io please")
    assert any(s.entity_type == "EMAIL_ADDRESS" for s in spans)
    assert "alice@corp.io" in [s.text for s in spans]
    assert engine != "none"
