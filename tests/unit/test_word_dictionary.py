# overlook / flag dictionary + gateway apply
from __future__ import annotations

from pathlib import Path

import pytest

from lakanvault.local_core.findings import Finding, Tier
from lakanvault.orchestration import word_dictionary as wd
from lakanvault.orchestration.gateway import Gateway

EMAIL = "jane.doe@example.com"
PII_PROMPT = f"please email {EMAIL} about the meeting"


def _gateway(tmp_path: Path) -> Gateway:
    src = Path(__file__).resolve().parents[2] / "config" / "default.yaml"
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "default.yaml").write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return Gateway(config_dir=cfg)


@pytest.fixture(autouse=True)
def _dict_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "word_dictionary.json"
    monkeypatch.setattr(wd, "_path", lambda: path)
    return path


@pytest.fixture(autouse=True)
def _pii_without_presidio(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_pii(text: str, layers=("names",)):
        start = text.find(EMAIL)
        if start < 0:
            return []
        return [
            Finding(
                "EMAIL_ADDRESS",
                EMAIL,
                start,
                start + len(EMAIL),
                0.95,
                Tier.PII_MODERATE,
                "presidio",
            )
        ]

    monkeypatch.setattr("lakanvault.local_core.scan.detect_pii", fake_pii)


def test_save_and_load_dictionary(tmp_path: Path) -> None:
    saved = wd.save_dictionary(
        {"overlook": [" Alpha ", "alpha", ""], "flag": ["ProjectX", "ProjectX"]}
    )
    assert saved == {"overlook": ["Alpha"], "flag": ["ProjectX"]}
    assert wd.load_dictionary() == saved


def test_overlook_drops_matching_finding() -> None:
    findings = [
        Finding("EMAIL_ADDRESS", EMAIL, 13, 13 + len(EMAIL), 0.95, Tier.PII_MODERATE, "presidio")
    ]
    wd.save_dictionary({"overlook": [EMAIL], "flag": []})
    out = wd.apply_dictionary(PII_PROMPT, findings)
    assert out == []


def test_flag_adds_custom_finding_when_uncovered() -> None:
    wd.save_dictionary({"overlook": [], "flag": ["CodenameZebra"]})
    text = "ship CodenameZebra tonight"
    out = wd.apply_dictionary(text, [])
    assert len(out) == 1
    assert out[0].entity_type == "CUSTOM_FLAG"
    assert out[0].text.lower() == "codenamezebra"
    assert out[0].source == "dictionary"


def test_gateway_overlook_allows_pii(tmp_path: Path) -> None:
    wd.save_dictionary({"overlook": [EMAIL], "flag": []})
    gw = _gateway(tmp_path)
    out = gw.protect_prompt(PII_PROMPT, session_id="ov1", llm="never")
    assert out.final_action == "allow"
    assert out.sanitized == PII_PROMPT
    assert out.finding_count == 0


def test_gateway_flag_masks_custom_term(tmp_path: Path) -> None:
    wd.save_dictionary({"overlook": [], "flag": ["CodenameZebra"]})
    gw = _gateway(tmp_path)
    text = "please mention CodenameZebra in the doc"
    out = gw.protect_prompt(text, session_id="fl1", llm="never")
    assert out.final_action == "mask"
    assert "CodenameZebra" not in out.sanitized
    assert any(f.entity_type == "CUSTOM_FLAG" for f in out.findings)
