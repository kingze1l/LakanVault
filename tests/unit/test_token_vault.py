"""Unit tests for the in-memory SQLite token vault."""
from __future__ import annotations

import re
import threading
import time
from pathlib import Path

import pytest

from lakanvault.contracts.proxy import OPAQUE_TOKEN_REGEX
from lakanvault.infrastructure.token_vault import (
    InMemoryTokenVault,
    VaultCapacityError,
    generate_opaque_token,
)


def test_mint_token_matches_contract_shape() -> None:
    token = generate_opaque_token()
    assert re.fullmatch(OPAQUE_TOKEN_REGEX, token)


def test_same_request_value_reuses_token() -> None:
    vault = InMemoryTokenVault()
    t1 = vault.mint("alice@corp.io", request_id="r1", ttl_seconds=60)
    t2 = vault.mint("alice@corp.io", request_id="r1", ttl_seconds=60)
    assert t1 == t2
    vault.close()


def test_different_requests_get_isolated_tokens() -> None:
    vault = InMemoryTokenVault()
    t1 = vault.mint("alice@corp.io", request_id="r1", ttl_seconds=60)
    t2 = vault.mint("alice@corp.io", request_id="r2", ttl_seconds=60)
    assert t1 != t2
    vault.close()


def test_expired_token_is_not_restored() -> None:
    vault = InMemoryTokenVault()
    token = vault.mint("secret", request_id="r1", ttl_seconds=0.05)
    time.sleep(0.08)
    assert vault.get(token) is None
    vault.close()


def test_unrecognized_token_is_not_restored() -> None:
    vault = InMemoryTokenVault()
    assert vault.get("[LV_AAAAAAAAAAAAAAAAAAAAAAAAAA]") is None
    vault.close()


def test_hard_cap_raises() -> None:
    vault = InMemoryTokenVault(max_entries=2, max_bytes=10_000)
    vault.mint("a", request_id="r1", ttl_seconds=60)
    vault.mint("b", request_id="r1", ttl_seconds=60)
    with pytest.raises(VaultCapacityError):
        vault.mint("c", request_id="r1", ttl_seconds=60)
    vault.close()


def test_delete_request_drops_only_that_request() -> None:
    vault = InMemoryTokenVault()
    t1 = vault.mint("one", request_id="r1", ttl_seconds=60)
    t2 = vault.mint("two", request_id="r2", ttl_seconds=60)
    assert vault.delete_request("r1") == 1
    assert vault.get(t1) is None
    assert vault.get(t2) == "two"
    vault.close()


def test_concurrent_mints_do_not_corrupt() -> None:
    vault = InMemoryTokenVault()
    errors: list[BaseException] = []

    def worker(i: int) -> None:
        try:
            for j in range(20):
                vault.mint(f"v-{i}-{j}", request_id=f"r{i}", ttl_seconds=60)
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    vault.close()


def test_close_wipes_and_creates_no_db_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    vault = InMemoryTokenVault()
    token = vault.mint("x", request_id="r1", ttl_seconds=60)
    vault.close()
    db_files = list(tmp_path.rglob("*.db")) + list(tmp_path.rglob("*.sqlite"))
    assert db_files == []
    with pytest.raises(Exception):
        vault.get(token)
