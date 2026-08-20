"""Tests for localhost URL policy."""
import pytest

from lakanvault.shared.url_policy import assert_allowed_upstream, assert_localhost_url


def test_accepts_localhost() -> None:
    assert assert_localhost_url("http://localhost:1234") == "http://localhost:1234"
    assert assert_localhost_url("http://127.0.0.1:11434/") == "http://127.0.0.1:11434"


def test_rejects_remote() -> None:
    with pytest.raises(ValueError, match="localhost"):
        assert_localhost_url("https://api.openai.com/v1")


def test_allowlisted_openai_origin() -> None:
    url = assert_allowed_upstream(
        "https://api.openai.com",
        ["https://api.openai.com", "http://127.0.0.1:11434"],
    )
    assert url == "https://api.openai.com"


def test_rejects_non_allowlisted_upstream() -> None:
    with pytest.raises(ValueError, match="allowlisted"):
        assert_allowed_upstream("https://evil.example", ["https://api.openai.com"])


def test_allowlist_does_not_trust_path_or_host_header_lookalikes() -> None:
    with pytest.raises(ValueError, match="allowlisted"):
        assert_allowed_upstream("https://api.openai.com.evil.test", ["https://api.openai.com"])
