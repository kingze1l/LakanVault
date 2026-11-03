
'''
debug the combined secret and PII pipeline
run this from src : python -m lakanvault.local_core.debug_secret_and_pii
'''

import time

from .secrets.detector import detect_secrets
from .pii.detector import detect_pii
from .findings import resolve_overlaps

from .samples import samples


def detect_all(text: str):
    secret_findings = detect_secrets(text)
    pii_findings = detect_pii(text)

    combined = secret_findings + pii_findings
    return resolve_overlaps(combined)


if __name__ == "__main__":
    for prompt in samples:
        print(f"PROMPT: {prompt}")

        findings = detect_all(prompt)

        if not findings:
            print("   (no findings)")

        for f in findings:
            flag = "ESCALATE" if f.needs_escalation else "confident"

            print(f"   {f.entity_type:<16} {f.tier.value:<13} {f.confidence:<5.2f} [{f.start}:{f.end}] {f.preview!r:<28} {flag:<9} <- {f.source}")
        print()

    # Warm-up: model loading and initial setup happen before timing.
    prompt = samples[5] + " " + samples[1]
    detect_all(prompt)

    runs = 50
    t0 = time.perf_counter()

    for _ in range(runs):
        detect_all(prompt)

    elapsed_ms = (time.perf_counter() - t0) / runs * 1000

    print(f"combined detection latency (average of {runs} runs):")
    print(f"   {elapsed_ms:.2f} ms")
