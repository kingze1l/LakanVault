"""Joan's handoff: one string from the IDE request, then regex + Presidio."""
from lakanvault.local_core.dlp.openai_payload import orchestrated_prompt
from lakanvault.local_core.privacy.classifier import classify_content


def test_orchestrated_prompt_joins_ide_messages() -> None:
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "You are a coding assistant."},
            {"role": "user", "content": "Email jane.doe@example.com about the deploy."},
        ],
    }
    text = orchestrated_prompt(payload)
    assert text == (
        "system: You are a coding assistant.\n\n"
        "user: Email jane.doe@example.com about the deploy."
    )


def test_orchestrated_prompt_reads_multipart_text() -> None:
    payload = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Check this key sk-abcdefghijklmnopqrstuvwxyz1234567890"},
                ],
            }
        ]
    }
    text = orchestrated_prompt(payload)
    assert text.startswith("user: Check this key sk-")


def test_regex_and_presidio_run_on_orchestrated_string() -> None:
    payload = {
        "messages": [
            {"role": "system", "content": "Workspace context: repo LakanVault"},
            {"role": "user", "content": "Contact jane.doe@example.com"},
        ]
    }
    result = classify_content(orchestrated_prompt(payload))
    assert result.action == "redact"
    assert "EMAIL_ADDRESS" in result.entity_types


def test_regex_blocks_secret_in_orchestrated_string() -> None:
    payload = {
        "messages": [
            {"role": "user", "content": "My key is sk-abcdefghijklmnopqrstuvwxyz1234567890"},
        ]
    }
    result = classify_content(orchestrated_prompt(payload))
    assert result.action == "block"
    assert result.tier == "confidential"
