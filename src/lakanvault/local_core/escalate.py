'''
cheap checks that decide if a prompt is suspicious enough to wake the local llm
'''

import math, re
from collections import Counter

MIN_LEN = 16
MIN_ENTROPY = 3.5   # bits per char

CANDIDATE = re.compile(r'[A-Za-z0-9+/=_\-]{16,}')
KEYWORD_VALUE = re.compile(
    r'(?i)\b(?:password|passwd|pwd|passphrase|secret|token|api[_ -]?key|credential|bearer)\b'
    r'\W{0,3}(?:is|=|:)?\s*["\']?(?P<value>\S{6,})'
)

def entropy(s):
    n = len(s)
    return -sum(c / n * math.log2(c / n) for c in Counter(s).values())

def _covered(s, e, spans):
    return any(s < b and a < e for a, b in spans)

def suspicion(text, findings):
    '''returns the reasons this prompt looks suspicious (empty list is not suspicious)'''
    spans = [(f.start, f.end) for f in findings]
    reasons = []

    for m in KEYWORD_VALUE.finditer(text):
        if not _covered(m.start('value'), m.end('value'), spans):
            reasons.append('keyword')
            break

    for m in CANDIDATE.finditer(text):
        tok = m.group()
        if _covered(m.start(), m.end(), spans):
            continue
        if any(c.isdigit() for c in tok) and any(c.isalpha() for c in tok) and entropy(tok) >= MIN_ENTROPY:
            reasons.append('entropy')
            break

    return reasons