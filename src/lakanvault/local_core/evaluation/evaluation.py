'''
run lakan vault architecture against combined secret + PII benchmark
(300 positive samples from each)

run :
python -m lakanvault.local_core.evaluation.evaluation

mostly complete
get the latency overhead of extending to local llm 
'''

import time
from datetime import datetime
from pathlib import Path

import pandas as pd
from ..scan import scan

N = 300
SEED = 42
BASE_DIR = Path(__file__).resolve().parent


def scan_row(text, llm):
    '''returns (findings as (text, start, end, entity_type), escalated_to_llm)'''
    findings = scan(text, llm=llm)
    escalated = any(getattr(f, 'source', None) == 'llm' for f in findings)
    return [(f.text, f.start, f.end, f.entity_type) for f in findings], escalated


def get_coverage(text, value, entity_type, findings, check_entity):
    s = text.find(value)
    if s == -1:
        return None, None, None

    e = s + len(value)
    overlaps = [(a, b, t) for _, a, b, t in findings if a < e and b > s]

    if not overlaps:
        return False, False, False

    fully_covered = any(a <= s and b >= e for a, b, _ in overlaps)
    if check_entity:
        entity_matched = any(t == entity_type for _, _, t in overlaps)
    else:
        entity_matched = True  # secrets: entity type doesn't matter

    return True, not fully_covered, entity_matched


# --- secrets: positives only ---
secrets = pd.read_parquet("hf://datasets/Podric/prowl-secrets-corpus/corpus.parquet")
secrets = secrets[secrets['label_binary'] == 1]
secrets = secrets.sample(min(N, len(secrets)), random_state=SEED)
secrets = secrets[['text', 'value', 'label_type']].copy()
secrets['dataset'] = 'secret'
secrets['llm'] = 'unsure'
secrets['check_entity'] = False

# --- PII: already positives only ---
pii = pd.read_csv(BASE_DIR / "pii_benchmark.csv")
pii = pii.sample(min(N, len(pii)), random_state=SEED)
pii = pii[['text', 'value', 'entity_type']].rename(columns={'entity_type': 'label_type'}).copy()
pii['dataset'] = 'pii'
pii['llm'] = 'unsure'
pii['check_entity'] = True

df = pd.concat([secrets, pii], ignore_index=True)

start_time = time.perf_counter()

records = []
escalated_so_far = 0
total_rows = len(df)

for i, (_, row) in enumerate(df.iterrows()):
    findings, escalated = scan_row(row['text'], row['llm'])
    escalated_so_far += int(escalated)

    covered, partial, entity_matched = get_coverage(
        row['text'], row['value'], row['label_type'], findings, row['check_entity']
    )
    records.append({
        'findings': findings,
        'escalated': escalated,
        'covered': covered,
        'partial_coverage': partial,
        'entity_matched': entity_matched,
    })

    if (i + 1) % 50 == 0 or (i + 1) == total_rows:
        print(f"{i + 1}/{total_rows} done, escalated so far: {escalated_so_far}")

df = pd.concat([df, pd.DataFrame(records)], axis=1)

total_time = time.perf_counter() - start_time

scored = df[df['covered'].notna()]
skipped = df['covered'].isna().sum()
escalated_count = int(df['escalated'].sum())
pii_scored = scored[scored['dataset'] == 'pii']
secret_scored = scored[scored['dataset'] == 'secret']

covered_pct = scored['covered'].mean() * 100 if len(scored) else 0
entity_pct = pii_scored['entity_matched'].mean() * 100 if len(pii_scored) else 0

report = f"""LakanVault combined evaluation report
=====================================
file created : {datetime.now().strftime('%d/%m/%Y %I:%M%p')}
time taken   : {total_time:.2f}s

samples
-------
total        : {len(df)}
secret       : {len(secrets)}
pii          : {len(pii)}

results
-------
scored       : {len(scored)}
skipped      : {skipped}
covered      : {scored['covered'].sum():.0f}/{len(scored)} ({covered_pct:.1f}%)
partial      : {scored['partial_coverage'].sum():.0f}/{len(scored)}
escalated to local llm : {escalated_count}/{len(df)} ({escalated_count / len(df) * 100:.1f}%)

by dataset
----------
secret       : covered {secret_scored['covered'].mean() * 100:.1f}% ({len(secret_scored)} scored)
pii          : covered {pii_scored['covered'].mean() * 100:.1f}% ({len(pii_scored)} scored)
pii entity matched : {entity_pct:.1f}%

by entity type
--------------
"""

by_type = scored.groupby(['dataset', 'label_type']).agg(
    covered=('covered', 'mean'),
    count=('covered', 'count'),
)
for (dataset, label), r in by_type.iterrows():
    report += f"{dataset:<8} {str(label):<30} covered {r['covered'] * 100:6.1f}%  ({int(r['count'])})\n"

REPORT_FILE = BASE_DIR / 'combined_report.txt'
REPORT_FILE.write_text(report, encoding='utf-8')
print(report)
print(f"Report saved to: {REPORT_FILE}")

OUTPUT_FILE = BASE_DIR / 'lakan_vault_combined_results.csv'
df.to_csv(OUTPUT_FILE, index=False)
print(f"Results saved to: {OUTPUT_FILE}")