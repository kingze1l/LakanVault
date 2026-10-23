'''
combine regex, presidio, and system to escalate to local llm
run : python -m lakanvault.local_core.scan
'''

from typing import Literal

from .findings import Finding, Tier, resolve_overlaps
from .pii.detector import detect_pii
from .secrets.detector import detect_secrets


def _overlaps(a: Finding, b: Finding) -> bool:
    return a.start < b.end and b.start < a.end


def merge(detector_findings: list[Finding], llm_findings: list[Finding]) -> list[Finding]:
    """
    Combine fast-layer findings with the local LLM's verdicts.

      confident detector finding (>= CONFIDENT_AT)  -> always kept; the LLM never overrides it
      unsure detector finding the LLM spoke about   -> replaced by the LLM's verdict
                                                       (BENIGN verdict = the finding is dropped)
      unsure detector finding the LLM did not cover -> kept as is (conservative: silence is not "safe")
      LLM finding nothing else covers               -> added (the LLM found something the detectors missed)
    BENIGN verdicts are never returned: they only exist to clear unsure findings.
    """

    '''
    combine fast layer with llm verdict
        confident detector finding (>= CONFIDENT_AT) -> always keep, llm never override it
        unsure detector finding the LLM spoke about   -> replaced by the LLM's verdict (BENIGN verdict = the finding is dropped)
        unsure detector finding the LLM did not cover -> kept as is (conservative: silence is not "safe")
        LLM finding nothing else covers               -> added (the LLM found something the detectors missed)
    '''

    confident = [f for f in detector_findings if not f.needs_escalation]
    unsure = [f for f in detector_findings if f.needs_escalation]

    verdicts = [v for v in llm_findings if not any(_overlaps(v, c) for c in confident)]
    kept_unsure = [f for f in unsure if not any(_overlaps(f, v) for v in verdicts)]
    sensitive = [v for v in verdicts if v.tier is not Tier.BENIGN]

    return resolve_overlaps(confident + sensitive + kept_unsure)


# when to call the local LLM:
#   "unsure" - only if a detector produced an unsure finding (fast; the original design)
#   "always" - on every prompt (slower, but the only way to catch things detectors cannot see at all, e.g. "the db password is Tr0ub4dor&3")
#   "never"  - detectors only
LLMPolicy = Literal["unsure", "always", "never"]


def scan(text: str, llm: LLMPolicy = "unsure") -> list[Finding]:
    """Scan one prompt. Returns non-overlapping findings ordered by position."""
    if not text:
        return []
    # one overlap pass over both detectors: an email inside a connection string
    # resolves to the SECRET (higher tier) instead of being reported twice
    findings = resolve_overlaps(detect_secrets(text) + detect_pii(text))

    if llm == "always" or (llm == "unsure" and any(f.needs_escalation for f in findings)):
        from .local_llm.detector import ask_llm   # lazy: scan() works without the openai package
        llm_findings = ask_llm(text)
        # llm_findings is None when the call failed: keep the detectors' result as is.
        if llm_findings is not None:
            findings = merge(findings, llm_findings)
    return findings


if __name__ == "__main__":
    import time
    from .samples import samples

    total_start = time.perf_counter()

    for i, prompt in enumerate(samples, start=1):
        print("=" * 100)
        print(f"SAMPLE {i}/{len(samples)}")
        print(f"PROMPT: {prompt!r}")

        start = time.perf_counter()

        try:
            findings = scan(prompt, llm="unsure")

            for f in findings:
                status = "ESCALATE" if f.needs_escalation else "confident"
                print(
                    f"  {f.entity_type:<20} "
                    f"{f.tier.value:<15} "
                    f"{f.confidence:.2f} "
                    f"[{f.start}:{f.end}] "
                    f"{f.preview!r} "
                    f"{status} <- {f.source}"
                )

            if not findings:
                print("  (no findings)")

        except Exception as exc:
            print(f"  ERROR: {type(exc).__name__}: {exc}")

        print(f"  Time: {(time.perf_counter() - start) * 1000:.2f} ms")

    print("=" * 100)
    print(f"Total time: {(time.perf_counter() - total_start) * 1000:.2f} ms")
