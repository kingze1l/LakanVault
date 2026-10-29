'''
run lakan vault architecture against secret database
run : 
python -m lakanvault.local_core.evaluation.secret_database
'''

import pandas as pd
from ..scan import scan_evaluation

def is_covered(text, value, findings):
    s = text.find(value)
    if s == -1:
        return None  # dataset value not verbatim in text: skip, don't count as a miss
    e = s + len(value)
    return any(a <= s and e <= b for _, a, b in findings)


df = pd.read_parquet("hf://datasets/Podric/prowl-secrets-corpus/corpus.parquet")
df = df[['value', 'text', 'label_type', 'span']].head(10).copy()

df['findings'] = df['text'].apply(scan_evaluation)
df['covered'] = [is_covered(t, v, f) for t, v, f in zip(df['text'], df['value'], df['findings'])]

scored = df[df['covered'].notna()]
print(f"Covered: {scored['covered'].mean():.3f} ({len(scored)} scored, {df['covered'].isna().sum()} skipped)")
print(scored.groupby('label_type')['covered'].agg(['mean', 'count']))

df.to_csv('lakan_vault_test_results.csv', index=False)
print('finish evaluation! can be seen on sheet file')
