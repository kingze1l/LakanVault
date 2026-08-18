"""Opaque tokens — new module; ReversibleAnonymizer stays untouched."""
from lakanvault.local_core.privacy.opaque_anonymizer import OpaqueAnonymizer


def test_clean_text_unchanged() -> None:
    anon = OpaqueAnonymizer()
    sanitized, mapping, engine = anon.anonymize("hello world")
    assert sanitized == "hello world"
    assert mapping == {}
    assert engine == "opaque"


def test_restore_applies_mapping() -> None:
    restored = OpaqueAnonymizer.restore("Meet TKN_aaaa", {"TKN_aaaa": "Jane"})
    assert restored == "Meet Jane"


def test_restore_empty_mapping_is_identity() -> None:
    assert OpaqueAnonymizer.restore("hello", {}) == "hello"
