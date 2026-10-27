'''
contained function shared with secret and pii
'''

import hmac, hashlib, os, random, secrets, string

KEY_PATH = 'vault.key'

def load_key(path=KEY_PATH):
    '''create (once, owner-only) and load the local secret key.'''
    if not os.path.exists(path):
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as f:
            f.write(secrets.token_bytes(32))
    with open(path, 'rb') as f:
        return f.read()

def make_rng(real, key, attempt=0):
    # HMAC keyed with the local secret -> deterministic seed:
    # same value + same key always gives the same fake
    digest = hmac.new(key, f'{attempt}:{real}'.encode(), hashlib.sha256).digest()
    return random.Random(digest)

def randomize(text, rng):
    '''keep the format: digits->digits, upper->upper, lower->lower, symbols kept.'''
    out = ""
    for ch in text:
        if ch.isdigit():
            out += rng.choice(string.digits)
        elif ch.isupper():
            out += rng.choice(string.ascii_uppercase)
        elif ch.islower():
            out += rng.choice(string.ascii_lowercase)
        else:
            out += ch
    return out