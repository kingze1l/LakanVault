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
python -m lakanvault.local_core.evaluation.secret_database
'''

import pandas as pd
from ..scan import scan_evaluation
import time

def get_coverage(text, value, findings):
    s =  text.find(value)

    if s == -1:
        return None, None

    e = s + len(value)

    overlaps = [
        (a, b) for _, a, b in findings if a < e and b > s
    ]

    if not overlaps:
        return False, False

    fully_covered = any(
        a <= s and b >= e
        for a, b in overlaps
    )

    return True, not fully_covered

df = pd.read_parquet("hf://datasets/Podric/prowl-secrets-corpus/corpus.parquet")
# Keep only positive samples (actual secrets)
df = df[df['label_binary'] == 1].head(50).copy()

start_time = time.perf_counter()

df['findings'] = df['text'].apply(scan_evaluation)
df[['covered', 'partial_coverage']] = df.apply(
    lambda row: pd.Series(
        get_coverage(row["text"], row["value"], row["findings"])
    ),
    axis=1
)

scored = df[df['covered'].notna()]
print(f"Covered: {scored['covered'].mean():.3f} ({len(scored)} scored, {df['covered'].isna().sum()} skipped)")
print(scored.groupby('label_type')['covered'].agg(['mean', 'count']))

total_time = time.perf_counter() - start_time
print(f'time taken: {total_time}')

from pathlib import Path
OUTPUT_FILE = Path(__file__).parent / 'lakan_vault_secret_results.csv'
df.to_csv(OUTPUT_FILE, index=False)
print(f"Results saved to: {OUTPUT_FILE}")
