"""Tests for localhost URL policy."""
import pytest

from lakanvault.shared.url_policy import assert_localhost_url


def test_accepts_localhost() -> None:
    assert assert_localhost_url("http://localhost:1234") == "http://localhost:1234"
    assert assert_localhost_url("http://127.0.0.1:11434/") == "http://127.0.0.1:11434"


def test_rejects_remote() -> None:
    with pytest.raises(ValueError, match="localhost"):
        assert_localhost_url("https://api.openai.com/v1")
