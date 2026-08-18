"""4-tier DLP action matrix. Classifier still hardcodes actions; wire-up is later."""

TIER_ACTIONS: dict[str, str] = {
    "public": "allow",
    "internal": "redact",
    "confidential": "block",
    "secret": "block",
}


def decide_action(tier: str) -> str:
    """Map a data tier to allow / warn / redact / block / log."""
    try:
        return TIER_ACTIONS[tier]
    except KeyError as exc:
        raise ValueError(f"unknown tier: {tier}") from exc
