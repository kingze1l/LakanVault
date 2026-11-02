
'''
reminder note: this is what you are going to do next
just copy the same format as the secret database, and then instead of using
df = pd.read_parquet("hf://datasets/Podric/prowl-secrets-corpus/corpus.parquet"), use the PII benchmark link 

make sure that it is all positive samples
in PII probably match the value and also the enitity type
result would probably be something like
matched: TRUE/FALSE : if it manage to find the correct span of PII
entity_matched: TRUE/FALSE : if it manage to find the correct entity 
in a scenario where LakanVault find multiple entity, biut there are only one entity, do a loop of found entity and match the truth entity, if it found it then matched is true
check entity_matched if it the same and retrun tryue as well

data would look something like
[Finding, Finding]
[(text, start, end, entity_type), (), ...]

class Finding:
    entity_type: str               # e.g. "aws-access-token", "EMAIL_ADDRESS"
    text: str = field(repr=False)  # matched value (repr=False: never leak in logs)
    start: int                     # character offset in the prompt (inclusive)
    end: int                       # character offset (exclusive)
    confidence: float              # 0..1
    tier: Tier
    source: str                    # "secrets" | "presidio" | ... (LLM layer adds "llm")

potential dataset : 
- https://huggingface.co/datasets/Pritesh-2711/pii-bench doesnt seem to have enittiy type here

monday, tuesday finishing benchmark
thursday opaque sanitization
friday website 
'''

'''
run lakan vault architecture against secret database

note:
prowl secret corpus has negative example which I filtered as of right now, currently only working with positive example
sometime result may return false, although LakanVault is sucessfull in determining the secret for example:
needed value : postgresql://app:uVbq3JVxZYWnEwWM@mongo-edge.rds.amazonaws.com:5432/auth 
lakanvault finding : [('uVbq3JVxZYWnEwWM', 89, 105)]	
covered : false
this should be true as the sensitive is found, one way I countered this is by making get_coverage function
get_coverage -> retrurn (True, True)
                          |      |
                    if finding is| inside the value
                                 |
                            if finding is only part of the value,
                            not all. (e.g. only 'ab' not 'abcd')
get_coverage help with double checking the data to see if the sensitive information is actually captured even though the value not match completely.

database does not use prompt but is very similar
run : 
python -m lakanvault.local_core.evaluation.pii_database
'''
import pandas as pd
from ..scan import scan_pii_evaluation
import time

def get_coverage(text, value, entity_type, findings):
    s = text.find(value)

    if s == -1:
        return None, None, None

    e = s + len(value)

    overlaps = [
        (a, b, t) for _, a, b, t in findings if a < e and b > s
    ]

    if not overlaps:
        return False, False, False

    fully_covered = any(
        a <= s and b >= e
        for a, b, _ in overlaps
    )

    entity_matched = any(t == entity_type for _, _, t in overlaps)

    return True, not fully_covered, entity_matched

from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
CSV_PATH = BASE_DIR / "pii_benchmark.csv"

df = pd.read_csv(CSV_PATH)

start_time = time.perf_counter()

df['findings'] = df['text'].apply(scan_pii_evaluation)
df[['matched', 'partial_coverage', 'entity_matched']] = df.apply(
    lambda row: pd.Series(
        get_coverage(row["text"], row["value"], row["entity_type"], row["findings"])
    ),
    axis=1
)

scored = df[df['matched'].notna()]
print(f"Matched: {scored['matched'].mean():.3f} | Entity matched: {scored['entity_matched'].mean():.3f} "
      f"({len(scored)} scored, {df['matched'].isna().sum()} skipped)")
print(scored.groupby('entity_type')[['matched', 'entity_matched']].agg(['mean', 'count']))

total_time = time.perf_counter() - start_time
print(f'time taken: {total_time}')

from pathlib import Path
OUTPUT_FILE = Path(__file__).parent / 'lakan_vault_pii_results.csv'
df.to_csv(OUTPUT_FILE, index=False)
print(f"Results saved to: {OUTPUT_FILE}")