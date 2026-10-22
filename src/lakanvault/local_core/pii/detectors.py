'''
PII detection: Presidio (NER + pattern recognizers) + low-confidence name heuristics.
sibling of secrets/detector.py. Public entry point: detect_pii(text) -> list[Finding].
'''

import logging
import re
from functools import lru_cache

from ..findings import DISCARD_BELOW, DetectionEngine, Finding, Tier, resolve_overlaps

logger = logging.getLogger(__name__)

# =============================================================================
# config
# =============================================================================
SPACY_MODEL = "en_core_web_sm"   # "en_core_web_md" / "_lg" are more accurate but slower to load

# NIST SP 800-122 does not fix a level per data type (the level depends on
# identifiability, field sensitivity, context of use, ...), so this is a default
# derived from two of its factors:
#   HIGH     fields NIST calls generally more sensitive (SSN, financial account,
#            medical) and government-issued IDs
#   MODERATE directly identifying fields (name, email, phone)
#   LOW      indirectly identifying / linkable data (location, IP, MAC)
PII_ENTITY_TIER: dict[str, Tier] = {
    "US_SSN": Tier.PII_HIGH,
    "US_ITIN": Tier.PII_HIGH,
    "US_PASSPORT": Tier.PII_HIGH,
    "US_DRIVER_LICENSE": Tier.PII_HIGH,
    "US_BANK_NUMBER": Tier.PII_HIGH,
    "CREDIT_CARD": Tier.PII_HIGH,
    "IBAN_CODE": Tier.PII_HIGH,
    "MEDICAL_LICENSE": Tier.PII_HIGH,
    "UK_NHS": Tier.PII_HIGH,
    "PERSON": Tier.PII_MODERATE,
    "EMAIL_ADDRESS": Tier.PII_MODERATE,
    "PHONE_NUMBER": Tier.PII_MODERATE,
    "LOCATION": Tier.PII_LOW,
    "IP_ADDRESS": Tier.PII_LOW,
    "MAC_ADDRESS": Tier.PII_LOW,   # not in every Presidio version: skipped with a warning if missing
    # deliberately NOT enabled: DATE_TIME, URL, AGE, ORGANIZATION, CRYPTO.
    # they fire constantly on ordinary code and are not PII by themselves.
}

# exact strings Presidio must never flag (e.g. your own city or company contact).
PII_ALLOW_LIST: list[str] = []

# name heuristics are weak signals: both confidences are below CONFIDENT_AT,
# so every hit is handed to the local LLM instead of being trusted.
NAME_STRONG = 0.6   # "my name is X", "Dear X", sign-offs
NAME_WEAK = 0.45    # "I am X", "to X"


# =============================================================================
# presidio
# =============================================================================
class PresidioDetector(DetectionEngine):
    layer = "presidio"

    def __init__(self, model: str | None = None):
        self._model = model or SPACY_MODEL
        self._analyzer = None            # built lazily: loading the spaCy model is slow
        self._entities: list[str] = []

    def load(self):
        """Build the analyzer now (call at startup so the first prompt isn't slow)."""
        if self._analyzer is None:
            import tldextract   # used internally by Presidio's email recognizer
            from presidio_analyzer import AnalyzerEngine
            from presidio_analyzer.nlp_engine import NlpEngineProvider

            # tldextract downloads the public-suffix list on first use. A DLP tool must
            # stay fully local, so force the snapshot bundled with the package.
            tldextract.tldextract.TLD_EXTRACTOR = tldextract.TLDExtract(suffix_list_urls=())

            nlp_engine = NlpEngineProvider(nlp_configuration={
                "nlp_engine_name": "spacy",
                "models": [{"lang_code": "en", "model_name": self._model}],
            }).create_engine()
            analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["en"])

            # Only ask for entities this Presidio version actually has.
            supported = set(analyzer.get_supported_entities("en"))
            self._entities = [e for e in PII_ENTITY_TIER if e in supported]
            for missing in sorted(set(PII_ENTITY_TIER) - supported):
                logger.warning("Presidio has no recognizer for %s; skipping it", missing)
            self._analyzer = analyzer
        return self._analyzer

    def detect(self, text: str) -> list[Finding]:
        results = self.load().analyze(
            text=text,
            language="en",
            entities=self._entities,
            score_threshold=DISCARD_BELOW,
            allow_list=PII_ALLOW_LIST or None,
        )
        findings = []
        for r in results:
            start, end = r.start, r.end
            if r.entity_type == "EMAIL_ADDRESS":
                value = text[start:end]
                start += max(value.rfind("="), value.rfind('"')) + 1   # drop "to=" style prefixes
                value = text[start:end]
                start += len(value) - len(value.lstrip("'"))           # drop a leading quote
            findings.append(Finding(r.entity_type, text[start:end], start, end,
                                    float(r.score), PII_ENTITY_TIER[r.entity_type], self.layer))
        return findings


# =============================================================================
# layer 2: name heuristics (catches lowercase / unusual names the small spaCy model misses)
# =============================================================================
_NAME = r"([A-Z][A-Za-z'\-]{1,30})\b"        # a Capitalised word
_NAME_ANYCASE = r"([A-Za-z][A-Za-z'\-]{1,30})\b"

# (pattern, confidence). Only the trigger phrase is case-insensitive, via a scoped (?i:...);
# most patterns require the name itself to be Capitalised, which removes most false
# positives like "I am trying" or "this is working".
_NAME_PATTERNS: list[tuple[re.Pattern[str], float]] = [
    (re.compile(r"\b(?i:my name is)\s+" + _NAME_ANYCASE), NAME_STRONG),     # "my name is bob"
    (re.compile(r"\b(?i:call me)\s+" + _NAME), NAME_STRONG),
    (re.compile(r"\b(?i:dear|hi|hello|hey|attention|regarding|telling)\s+" + _NAME), NAME_STRONG),
    (re.compile(r"(?:^|\n)[ \t]*(?i:thanks|thank you|regards|best regards|sincerely|cheers),?"
                r"[ \t]*\n?[ \t]*([A-Z][a-z]{2,30})\b"), NAME_STRONG),      # sign-offs
    (re.compile(r"\b(?i:i am|i'm|this is)\s+" + _NAME), NAME_WEAK),
    (re.compile(r"\bto\s+" + _NAME), NAME_WEAK),                            # "email to Bob"
]
# deliberately dropped from the first draft: "for <word>" ("for example", "for item in ...").

_NOT_NAMES = frozenset({
    # pronouns / articles / filler
    "the", "a", "an", "my", "your", "his", "her", "their", "our", "this", "that", "me", "you",
    "him", "them", "us", "it", "all", "any", "some", "every", "each", "he", "she", "they", "we", "i",
    "everyone", "anyone", "team", "there", "here", "now", "later", "again", "whom",
    # greetings / politeness / feelings
    "please", "thanks", "hello", "dear", "sir", "madam", "sorry", "fine", "good", "great", "happy",
    "not", "new", "just", "very", "sure", "ready", "back",
    # days / times
    "today", "tomorrow", "yesterday", "monday", "tuesday", "wednesday", "thursday", "friday",
    "saturday", "sunday", "morning", "afternoon", "evening",
    # school/work words from the first draft
    "class", "school", "work", "email", "tutor", "teacher", "student", "cant", "can't", "cannot",
    "make", "write",
    # things that show up in code and docs
    "world", "none", "null", "true", "false", "error", "exception", "string", "int", "list",
    "dict", "object", "value", "item", "example", "test", "main", "function", "class",
})


def _plausible_name(token: str) -> bool:
    low = token.lower().strip("'-")
    return len(low) >= 2 and low not in _NOT_NAMES and not low.isdigit()


class NameHeuristicDetector(DetectionEngine):
    layer = "names"

    def detect(self, text: str) -> list[Finding]:
        findings = []
        for rx, confidence in _NAME_PATTERNS:
            for m in rx.finditer(text):
                name = m.group(1)
                if _plausible_name(name):
                    findings.append(Finding("PERSON", name, m.start(1), m.end(1), confidence,
                                            Tier.PII_MODERATE, self.layer))
        return findings


# =============================================================================
# public API
# =============================================================================
_LAYER_CLASSES = {"presidio": PresidioDetector, "names": NameHeuristicDetector}


@lru_cache(maxsize=None)
def get_engine(layer: str) -> DetectionEngine:
    """One shared instance per layer (model loaded once)."""
    return _LAYER_CLASSES[layer]()


def load_pii_models() -> None:
    """Call at startup so the first prompt doesn't pay for loading spaCy."""
    get_engine("presidio").load()


def detect_pii(text: str, layers: tuple[str, ...] = ("presidio", "names")) -> list[Finding]:
    """
    Scan one prompt. Returns non-overlapping findings ordered by position.
    layers=("names",) runs without Presidio/spaCy (air-gapped CI, quick tests).
    If Presidio or its model is missing this raises instead of silently returning nothing:
    a DLP gateway should fail loudly, not let prompts through unscanned.
    """
    if not text:
        return []
    findings: list[Finding] = []
    for layer in layers:
        findings.extend(get_engine(layer).detect(text))
    return resolve_overlaps(findings)