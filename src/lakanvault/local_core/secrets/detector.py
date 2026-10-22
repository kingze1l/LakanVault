'''
secret detection: Gitleaks-style rules (regex + keywords + entropy + allowlists).
sibling of pii/detector.py. Public entry point: detect_secrets(text) -> list[Finding].
'''

import logging
import math
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import regex as re  # use regex closer to Go/RE2 syntax used by gitleaks.toml

from ..findings import DISCARD_BELOW, DetectionEngine, Finding, Tier, resolve_overlaps

logger = logging.getLogger(__name__)

# =============================================================================
# config 
# =============================================================================
GITLEAKS_TOML = Path(__file__).with_name("gitleaks.toml")
DEFAULT_SCORE = 0.85
STOPWORD_PENALTY = 0.5   # placeholder-looking value: 0.85 * 0.5 = 0.425 -> "unsure", not dropped
ENTROPY_PENALTY = 0.6    # value below the rule's minimum entropy

# placeholder-looking values: demote the score (-> "unsure" band).
ALLOW_STOPWORDS: tuple[str, ...] = (
    "example", "changeme", "change_me", "your_", "your-", "xxxx",
    "placeholder", "dummy", "sample", "fake", "redacted", "todo",
)
# obvious non-secrets: dropped immediately.
ALLOW_EXACT: set[str] = {"password", "secret", "token", "apikey", "api_key",
                         "string", "null", "none", "true", "false"}
# regexes matched against the extracted secret: dropped. e.g. r"^[0-9a-f]{40}$" ignores git SHAs.
ALLOW_REGEXES: list[str] = []


# =============================================================================
# rule model (mirrors gitleaks.toml semantics)
# =============================================================================
@dataclass(frozen=True)
class Allowlist:
    target: str = "secret"            # "secret" | "match" | "line"  (gitleaks default: secret)
    regexes: tuple[str, ...] = ()
    stopwords: tuple[str, ...] = ()
    condition: str = "OR"             # "OR" | "AND" (gitleaks default: OR); loader must set it


@dataclass(frozen=True)
class SecretRule:
    id: str
    description: str
    regex: str
    keywords: tuple[str, ...]         # lowercase; empty = no prefilter (rule always runs)
    secret_group: int = 0             # 0 = not set
    entropy: float | None = None      # minimum Shannon entropy of the secret
    score: float = DEFAULT_SCORE
    allowlists: tuple[Allowlist, ...] = ()


# added manually, include things gitleaks.toml does not catch.
SECRET_RULES: list[SecretRule] = [
    SecretRule(
        id="uri-credentials",
        description="Password embedded in a connection string or URL.",
        regex=r"""(?i)\b[a-z][a-z0-9+.-]{1,20}://[^\s:/@'"]{0,64}:([^\s@'"/]{3,128})@""",
        keywords=("://",),
        secret_group=1,
        score=0.9,
    )
]


# =============================================================================
# helper function
# =============================================================================
def shannon_entropy(s: str) -> float:
    """Bits per character (random-looking strings score high). Empty string is 0."""
    if not s:
        return 0.0
    n = len(s)
    return -sum(c / n * math.log2(c / n) for c in Counter(s).values())


@lru_cache(maxsize=None)
def _rx(pattern: str):
    return re.compile(pattern)


def line_of(text: str, start: int, end: int) -> str:
    ls = text.rfind("\n", 0, start) + 1
    le = text.find("\n", end)
    return text[ls: len(text) if le == -1 else le]


def pick_secret(m, secret_group: int):
    '''which part of the match is 'the secret' (gitleaks rules): the named group, else the first non-empty group, else the whole match.'''
    if secret_group:
        return m.group(secret_group), m.span(secret_group)
    for i, g in enumerate(m.groups(), start=1):
        if g:
            return g, m.span(i)
    return m.group(0), m.span(0)


def is_allowed(al: Allowlist, secret: str, match: str, line: str) -> bool:
    '''gitleaks allowlist: stopwords and regexes are the checks; `condition` says whether any (OR) or all (AND) of the configured checks must hit.'''
    checks = []
    if al.stopwords:
        low = secret.lower()
        checks.append(any(w.lower() in low for w in al.stopwords))
    if al.regexes:
        target = {"secret": secret, "match": match, "line": line}[al.target]
        checks.append(any(_rx(p).search(target) for p in al.regexes))
    if not checks:
        return False
    return all(checks) if al.condition.upper() == "AND" else any(checks)


# =============================================================================
# the detector 
# =============================================================================
class SecretDetector(DetectionEngine):
    layer = "secrets"

    def __init__(self, rules: list[SecretRule] | None = None):
        self._global_allow: tuple[Allowlist, ...] = ()
        if rules is None:
            from .config_loader import load_secret_rules   # lazy: avoids circular import
            rules, failed, self._global_allow = load_secret_rules(GITLEAKS_TOML)
            for rule_id, err in failed:   # a rule that fails to compile = silent blind spot
                logger.warning("gitleaks rule %r skipped (regex did not compile): %s", rule_id, err)
            rules = rules + SECRET_RULES
        self._rules = [(r, re.compile(r.regex)) for r in rules]
        self._allow_rx = [re.compile(p) for p in ALLOW_REGEXES]

    def detect(self, text: str) -> list[Finding]:
        lowered = text.lower()
        findings: list[Finding] = []
        for rule, rx in self._rules:
            # 1. keyword prefilter: cheap substring test (skipped if the rule has no keywords)
            if rule.keywords and not any(k in lowered for k in rule.keywords):
                continue
            # 2. regex: find secret candidates
            for m in rx.finditer(text):
                value, (start, end) = pick_secret(m, rule.secret_group)
                line = line_of(text, *m.span())
                score = self._score(rule, value, m.group(0), line)
                if score >= DISCARD_BELOW:
                    findings.append(Finding(rule.id, value, start, end, score,
                                            Tier.SECRET, self.layer))
        return findings

    def _score(self, rule: SecretRule, value: str, match_text: str, line: str) -> float:
        low = value.lower()
        if low in ALLOW_EXACT:
            return 0.0
        if any(rx.search(value) for rx in self._allow_rx):
            return 0.0
        allowlists = self._global_allow + rule.allowlists
        if any(is_allowed(al, value, match_text, line) for al in allowlists):
            return 0.0
        score = rule.score
        if any(w in low for w in ALLOW_STOPWORDS):
            score *= STOPWORD_PENALTY
        if rule.entropy and shannon_entropy(value) < rule.entropy:
            score *= ENTROPY_PENALTY
        return round(score, 3)


# =============================================================================
# public api
# =============================================================================
@lru_cache(maxsize=1)
def _default_detector() -> SecretDetector:
    '''one shared instance (rules compiled once). Call detect_secrets("") at startup to warm it.'''
    return SecretDetector()


def detect_secrets(text: str) -> list[Finding]:
    '''scan one prompt. Returns non-overlapping SECRET findings ordered by position.'''
    if not text:
        return []
    return resolve_overlaps(_default_detector().detect(text))