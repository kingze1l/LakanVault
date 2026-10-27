'''
anonymizer for secrets and PII
to test, go to src folder and run python -m lakanvault.local_core.anonymizer.anonymizer

this do NOT detect if its PII and SECRET, it will just rewrite it. Format perserving for secret and Surrogate anonymizer for pii
'''

import re, sqlite3
from .helper import KEY_PATH, load_key, make_rng
from .secret_fakes import create_fake_secret
from .pii_fakes import PII_GENERATORS, create_fake_pii
from .samples import SAMPLES_SECRET, SAMPLES_PII

def create_fake(real, entity_type, tier, key, attempt=0):
    rng = make_rng(real, key, attempt)
    entity_type = entity_type.upper() if entity_type else None   # llm returns 'ip_address', generators expect 'IP_ADDRESS'
    if entity_type in PII_GENERATORS or (tier is not None and tier != 'SECRET'):
        return create_fake_pii(real, entity_type, rng)
    return create_fake_secret(real, rng)

class Vault:
    def __init__(self, path='vault.db', workspace='default', key_path=KEY_PATH):
        self.workspace = workspace
        self.key = load_key(key_path)
        self.db = sqlite3.connect(path)
        self.db.execute('''CREATE TABLE IF NOT EXISTS mapping (workspace TEXT, fake TEXT, real TEXT, PRIMARY KEY (workspace, fake))''')

    # retry if the fake equals the real value or already exists (only likely for very short secrets)
    def surrogate(self, real, entity_type=None, tier=None):
        for attempt in range(20):
            fake = create_fake(real, entity_type, tier, self.key, attempt)
            row = self.db.execute('SELECT real FROM mapping WHERE workspace=? AND fake=?', (self.workspace, fake)).fetchone()
            if row and row[0] == real:
                return fake
            if fake != real and not row:
                self.db.execute('INSERT INTO mapping VALUES (?, ?, ?)', (self.workspace, fake, real))
                self.db.commit()
                return fake
        raise ValueError('could not generate unique surrogate')

    # findings carry offsets; replace right-to-left so earlier offsets stay valid
    def sanitize(self, text, findings):
        spans = {(f.start, f.end): f for f in findings}
        for f in sorted(findings, key=lambda f: -len(f.text)):   # longest first
            pat = re.escape(f.text) if f.tier == "SECRET" else rf'(?<!\w){re.escape(f.text)}(?!\w)'
            for m in re.finditer(pat, text):
                s, e = m.span()
                if all(e <= a or s >= b for a, b in spans):       # skip overlaps
                    spans[(s, e)] = f
        for (s, e), f in sorted(spans.items(), reverse=True):
            text = text[:s] + self.surrogate(f.text, f.entity_type, f.tier) + text[e:]
        return text

    # run after the external LLM returns its response
    def restore(self, text):
        rows = self.db.execute('SELECT fake, real FROM mapping WHERE workspace=?', (self.workspace,)).fetchall()
        if not rows:
            return text
        m = dict(rows)
        pat = re.compile('|'.join(map(re.escape, sorted(m, key=len, reverse=True))))
        return pat.sub(lambda x: m[x.group()], text)

if __name__ == '__main__':
    vault = Vault(":memory:")
    for secret in SAMPLES_SECRET:
        fake = vault.surrogate(secret)
        print(f'{secret} : {fake}')
        assert vault.restore(fake) == secret
        assert vault.surrogate(secret) == fake

    for real, ent, tier in [("john.smith@acme.com", "EMAIL_ADDRESS", "PII_MODERATE"),
                        ("4111 1111 1111 1111", "CREDIT_CARD", "PII_HIGH"),
                        ("GB82 WEST 1234 5698 7654 32", "IBAN_CODE", "PII_HIGH"),
                        ("+1 415-555-0132", "PHONE_NUMBER", "PII_MODERATE"),
                        ("10.1.2.3", "IP_ADDRESS", "PII_LOW"),
                        ("Priya Sharma", "PERSON", "PII_MODERATE")]:
        fake = vault.surrogate(real, ent, tier)
        print(f'{real} : {fake}')
        assert vault.restore(fake) == real