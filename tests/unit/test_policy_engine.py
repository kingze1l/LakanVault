"""4-tier action matrix — not wired into classify_content yet."""
import pytest

from lakanvault.local_core.policy.engine import decide_action


def test_public_allows() -> None:
    assert decide_action("public") == "allow"


def test_internal_redacts() -> None:
    assert decide_action("internal") == "redact"


def test_confidential_blocks() -> None:
    assert decide_action("confidential") == "block"


def test_secret_blocks() -> None:
    assert decide_action("secret") == "block"


def test_unknown_tier_raises() -> None:
    with pytest.raises(ValueError, match="unknown tier"):
        decide_action("top-secret")
