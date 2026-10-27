from faker import Faker
from .helper import randomize

faker = Faker()

def _seed_faker(rng):
    faker.seed_instance(rng.getrandbits(64))   # seeded from the HMAC -> stable names

def fake_person(real, rng):
    _seed_faker(rng); return faker.name()

def fake_location(real, rng):
    _seed_faker(rng); return faker.city()

def fake_email(real, rng):
    _seed_faker(rng); return faker.safe_email()   # example.* domain, real domain doesn't leak

def fake_card(real, rng):
    s = randomize(real, rng)
    digits = [c for c in s if c.isdigit()]
    total = 0
    for i, d in enumerate(reversed(digits[:-1])):   # Luhn: double every 2nd body digit from the right
        d = int(d)
        total += (d * 2 - 9 if d * 2 > 9 else d * 2) if i % 2 == 0 else d
    digits[-1] = str((10 - total % 10) % 10)
    it = iter(digits)
    return "".join(next(it) if c.isdigit() else c for c in s)

def fake_iban(real, rng):
    clean = real.replace(" ", "")
    cc, bban = clean[:2], randomize(clean[4:], rng)
    num = "".join(str(int(c, 36)) for c in bban + cc + "00")
    new = cc + f"{98 - int(num) % 97:02d}" + bban   # recompute check digits
    return " ".join(new[i:i + 4] for i in range(0, len(new), 4)) if " " in real else new

def fake_ip(real, rng):
    if ":" in real:
        return "2001:db8::" + format(rng.randint(1, 0xffff), "x")
    return rng.choice(["192.0.2.", "198.51.100.", "203.0.113."]) + str(rng.randint(1, 254))

def fake_mac(real, rng):
    # keep the separator (: or -) and produce valid hex pairs
    sep = '-' if '-' in real else ':'
    return sep.join(format(rng.randint(0, 255), '02X') for _ in range(6))


PII_GENERATORS = {
    'PERSON': fake_person, 'LOCATION': fake_location, 'EMAIL_ADDRESS': fake_email,
    'CREDIT_CARD': fake_card, 'IBAN_CODE': fake_iban, 'IP_ADDRESS': fake_ip,
    'MAC_ADDRESS': fake_mac,
    # everything else keeps the format: digits->digits, letters->letters
    **{e: randomize for e in ('PHONE_NUMBER', 'US_SSN', 'US_ITIN', 'US_PASSPORT',
                              'US_DRIVER_LICENSE', 'US_BANK_NUMBER', 'UK_NHS',
                              'MEDICAL_LICENSE')},
}

def create_fake_pii(real, entity_type, rng):
    return PII_GENERATORS.get(entity_type, randomize)(real, rng)