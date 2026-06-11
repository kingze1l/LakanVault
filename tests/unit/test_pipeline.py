"""Basic smoke tests for the pipeline stages."""
import tempfile
from pathlib import Path

from lakanvault.contracts.dtos import ScanRequest
from lakanvault.contracts.events import StageStatus
from lakanvault.local_core.integrity.stage import IntegrityStage
from lakanvault.local_core.threat_scanner.stage import ThreatScannerStage
from lakanvault.local_core.audit.stage import AuditStage
from lakanvault.contracts.events import PipelineEvent


def test_integrity_missing_file():
    stage = IntegrityStage()
    event = PipelineEvent(run_id="t1", target_path="/nonexistent/file.bin")
    result = stage.run(event)
    assert result.status == StageStatus.FAIL


def test_integrity_real_file():
    with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as f:
        f.write(b"fake model data" * 100)
        tmp = f.name
    stage = IntegrityStage()
    event = PipelineEvent(run_id="t2", target_path=tmp)
    result = stage.run(event)
    assert result.status == StageStatus.PASS
    assert "hash" in result.metadata
    Path(tmp).unlink()


def test_threat_scanner_no_findings():
    import os
    # Remove any risky env vars for this test
    for k in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY"]:
        os.environ.pop(k, None)
    stage = ThreatScannerStage()
    event = PipelineEvent(run_id="t3", target_path="./data/models/test.bin")
    result = stage.run(event)
    # Should be PASS or WARN depending on environment, never ERROR
    assert result.status in (StageStatus.PASS, StageStatus.WARN)


def test_audit_writes_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        stage = AuditStage(audit_dir=tmpdir)
        event = PipelineEvent(run_id="t4", target_path="/fake/model.bin")
        result = stage.run(event)
        assert result.status == StageStatus.PASS
        written = list(Path(tmpdir).glob("*.json"))
        assert len(written) == 1
        import json
        data = json.loads(written[0].read_text())
        assert data["run_id"] == "t4"
        assert "prompt_text" not in str(data)  # never stored
