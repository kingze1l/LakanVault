'''
this file is just to load gitleaks format rules (gitleaks.toml) to SecretRule / Allowlist objects

only plain prompt text is scanned, so file/commit-based parts of gitleaks
(paths, commits) are ignored, and rules that only make sense for a file path are skipped.
gitleaks regexes are Go (RE2) syntax: a few may not compile with `regex` -> reported in `failed`.

'''

import tomllib
from pathlib import Path

import regex as re

from .detector import DEFAULT_SCORE, Allowlist, SecretRule

_TARGETS = {"secret", "match", "line"}


def _parse_allowlist(section: dict) -> Allowlist | None:
    '''one gitleaks allowlist table -> Allowlist, or None if it can never apply to plain text.'''
    condition = str(section.get("condition", "OR")).upper()
    # plain text has no path and no commit, so an AND allowlist that requires
    # either one can never be satisfied: it would never suppress anything.
    if condition == "AND" and (section.get("paths") or section.get("commits")):
        return None
    target = str(section.get("regexTarget") or "secret").lower()   # gitleaks default: secret
    al = Allowlist(
        target=target if target in _TARGETS else "secret",
        regexes=tuple(section.get("regexes", [])),
        stopwords=tuple(w.lower() for w in section.get("stopwords", [])),
        condition=condition,
    )
    return al if (al.regexes or al.stopwords) else None


def load_secret_rules(
    path: str | Path,
) -> tuple[list[SecretRule], list[tuple[str, str]], tuple[Allowlist, ...]]:
    '''returns (rules, failed, global_allowlists). `failed` = [(rule_id, error)] for rules whose regex does not compile.'''
    with open(path, "rb") as f:
        data = tomllib.load(f)

    # global allowlists: legacy [allowlist] and current [[allowlists]].
    # one with `targetRules` applies only to those rules; otherwise it is global.
    global_allow: list[Allowlist] = []
    targeted: dict[str, list[Allowlist]] = {}
    sections = list(data.get("allowlists", []))
    if "allowlist" in data:
        sections.append(data["allowlist"])
    for s in sections:
        al = _parse_allowlist(s)
        if al is None:
            continue
        if s.get("targetRules"):
            for rule_id in s["targetRules"]:
                targeted.setdefault(rule_id, []).append(al)
        else:
            global_allow.append(al)

    rules: list[SecretRule] = []
    failed: list[tuple[str, str]] = []
    for r in data.get("rules", []):
        # path only rules have no regex; rules with a `path` filter only make sense for files
        if "regex" not in r or r.get("path"):
            continue
        try:
            re.compile(r["regex"])
        except re.error as e:
            failed.append((r.get("id", "<no id>"), str(e)))
            continue

        allowlists: list[Allowlist] = []
        if "allowlist" in r:                      # legacy single table
            al = _parse_allowlist(r["allowlist"])
            if al:
                allowlists.append(al)
        for a in r.get("allowlists", []):         # current [[rules.allowlists]]
            al = _parse_allowlist(a)
            if al:
                allowlists.append(al)
        allowlists.extend(targeted.get(r["id"], []))

        rules.append(SecretRule(
            id=r["id"],
            description=r.get("description", ""),
            regex=r["regex"],
            keywords=tuple(k.lower() for k in r.get("keywords", [])),
            secret_group=int(r.get("secretGroup", 0)),
            entropy=float(r["entropy"]) if r.get("entropy") else None,
            score=float(r.get("score", DEFAULT_SCORE)),
            allowlists=tuple(allowlists),
        ))

    return rules, failed, tuple(global_allow)