from .helper import randomize
from .keywords import KEYWORDS

WORDS = sorted({k.lower() for k in KEYWORDS}, key=lambda w: (-len(w), w))

def create_fake_secret(secret, rng):
    '''Keep the first matching keyword (e.g. 'sk_live') readable, randomize the rest.'''
    lower = secret.lower()
    for word in WORDS:
        i = lower.find(word)
        if i != -1:
            j = i + len(word)
            # only keep the keyword if something alphanumeric is left to randomize
            if any(c.isalnum() for c in secret[:i] + secret[j:]):
                return randomize(secret[:i], rng) + secret[i:j] + randomize(secret[j:], rng)
    return randomize(secret, rng)