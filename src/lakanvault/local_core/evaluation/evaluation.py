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
from ..findings import Tier, resolve_overlaps
from ..scan import scan
from ..local_llm import detector as llm_detector
from ..secrets.detector import detect_secrets
from ..pii.detector import detect_pii
from ..pii.pii_entity_tier import PII_ENTITY_TIER


N = 300
SEED = 42
LAT_N = 50   # rows used for the per-config latency comparison
BASE_DIR = Path(__file__).resolve().parent

# to see and record everytime ask_llm call
# (works because scan() imports ask_llm lazily, at call time)
calls = []
_orig_ask = llm_detector.ask_llm
llm_detector.ask_llm = lambda text: (calls.append(1), _orig_ask(text))[1]

CONFIGS = {
    'regex': detect_secrets,
    'presidio': detect_pii,
    'regex+presidio': lambda t: resolve_overlaps(detect_secrets(t) + detect_pii(t)),
    'full': lambda t: scan(t, 'unsure'),
}


def scan_row(text):
    '''returns (findings as dicts, escalated_to_llm, latency_ms)'''
    before = len(calls)
    t0 = time.perf_counter()
    findings = scan(text, 'unsure')
    latency_ms = (time.perf_counter() - t0) * 1000
    # count the call itself, so escalations where the llm returned nothing are still seen
    escalated = len(calls) > before
    out = [{
        'text': f.text, 'start': f.start, 'end': f.end,
        'entity_type': f.entity_type, 'tier': f.tier.value,
        'source': getattr(f, 'source', None),
    } for f in findings]
    return out, escalated, latency_ms


'''
gold = [
    (start, end, tier)
    (10, 20, Tier.SECRET)
]

findings = [
    {'start': 12, 'end': 18, 'tier': 'SECRET', ...}
    {'start': 20, 'end': 45, 'tier': 'PII', ...}
]
'''
def score(gold, findings):
    ''' 
        return (kind, tier) events: TP of FN by gold tier, FP by finding tier
        like [('fp', 'SECRET')]
        overlap with a gold span counts as a hit (partial coverage = TP)
    '''
    ev, hit = [], set()
    for f in findings:
        m = [i for i, (s, e, _) in enumerate(gold) if f['start'] < e and f['end'] > s]
        if m:
            hit.update(m)
        else:
            ev.append(('fp', f['tier']))
    for i, (_, _, tier) in enumerate(gold):
        ev.append(('tp' if i in hit else 'fn', tier.value))
    return ev


def entity_matched(gold, entity_type, findings):
    '''pii only: does a finding overlapping the gold span have the right entity type'''
    s, e, _ = gold[0]
    return any(f['entity_type'] == entity_type for f in findings if f['start'] < e and f['end'] > s)


def load_data():
    # the corpus, gold = list of (start, end, tier) per text
    sec = pd.read_parquet("hf://datasets/Podric/prowl-secrets-corpus/corpus.parquet")
    pos = sec[(sec['label_binary'] == 1) & sec['span'].notna()]
    spans = pos.groupby('text')['span'].apply(list) # all secret in the text, not just the sampled row

    secrets = pos.drop_duplicates('text').sample(N, random_state=SEED)[['text']].copy()
    secrets['gold'] = secrets['text'].map(lambda t: [(int(s), int(e), Tier.SECRET) for s, e in spans[t]])
    secrets['dataset'] = 'secret'
    secrets['entity_type'] = 'secret'

    neg_sec = (sec[sec['label_binary'] == 0].drop_duplicates('text')
               .sample(N, random_state=SEED)[['text']].copy())

    pii = pd.read_csv(BASE_DIR / "pii_benchmark.csv").sample(N, random_state=SEED)
    pii['gold'] = pii.apply(
        lambda r: [(r.text.find(r.value), r.text.find(r.value) + len(r.value), PII_ENTITY_TIER[r.entity_type])]
        if r.value in r.text else [], axis=1
    )
    pii = pii[pii['gold'].map(bool)].copy()
    pii['dataset'] = 'pii'
    pii['entity_type'] = pii['entity_type']
    pii = pii[['text', 'gold', 'dataset', 'entity_type']]

    neg_pii = pd.read_csv(BASE_DIR / "pii_benchmark_negative.csv")[['text']].copy()
    neg_pii = neg_pii.sample(min(N, len(neg_pii)), random_state=SEED)

    neg = pd.concat([neg_sec, neg_pii], ignore_index=True)
    neg['gold'] = [[] for _ in range(len(neg))]       # any finding here = false positive
    neg['dataset'] = 'negative'
    neg['entity_type'] = 'negative'
    df = pd.concat([secrets, pii, neg], ignore_index=True)
    print(f"secret {len(secrets)} | pii {len(pii)} | negative {len(neg)}")
    return df, len(secrets), len(pii), len(neg)

def to_dict(f):
    return {'text': f.text, 'start': f.start, 'end': f.end, 'entity_type': f.entity_type, 'tier': f.tier.value, 'source': getattr(f, 'source', None)}

BASELINES = {k: v for k, v in CONFIGS.items() if k != 'full'} # no llm

def prf(events_per_row):
    ev = pd.DataFrame([(k, t) for evs in events_per_row for k, t in evs], columns=['kind', 'tier'])
    c = (ev.groupby(['tier', 'kind']).size().unstack(fill_value=0).reindex(columns=['tp', 'fp', 'fn'], fill_value=0))
    c.loc['ALL'] = c.sum()
    c['precision'] = c.tp / (c.tp + c.fp).replace(0, float('nan'))
    c['recall'] = c.tp / (c.tp + c.fn).replace(0, float('nan'))
    c['f1'] = 2 * c.precision * c.recall / (c.precision + c.recall)
    return c.round(3)

def row_correct(r):
    fp_tiers = [t for k, t in r['events'] if k == 'fp']
    if r['dataset'] == 'negative':
        return len(r['findings']) == 0
    if r['dataset'] == 'secret':
        # a secret row is judged on secret findings only
        return bool(r['covered']) and 'SECRET' not in fp_tiers
    # pii rows: right entity type, and no false positives at all
    return bool(r['entity_matched']) and len(fp_tiers) == 0

def main():
    df, n_secret, n_pii, n_neg = load_data()

    # warm up, this is so LM Studio loading not getting accounted in the latency 
    for fn in CONFIGS.values():
        fn("warm up: contact john@example.com")
    llm_detector.ask_llm("warm up")

    '''
    lats = {'regex': 3.1, 'full': 95.2}   ms per row, per config
    '''
    # per-config latency on the same rows, gives the llm overhead directly
    # (runs before the main loop, then calls is cleared so these runs don't skew escalation counts)
    lat_sample = df['text'].sample(min(LAT_N, len(df)), random_state=SEED)
    cfg_ms = {}
    for name, fn in CONFIGS.items():
        t0 = time.perf_counter()
        for t in lat_sample:
            fn(t)
        cfg_ms[name] = (time.perf_counter() - t0) / len(lat_sample) * 1000
    llm_overhead = cfg_ms['full'] - cfg_ms['regex+presidio']
    calls.clear()

    start_time = time.perf_counter()

    records = []
    escalated_so_far = 0
    total_rows = len(df)

    base_events = {name: [] for name in BASELINES}
    full_events = []    
    for i, (_, row) in enumerate(df.iterrows()):
        findings, escalated, latency_ms = scan_row(row['text'])
        escalated_so_far += int(escalated)
        full_events.append(score(row['gold'], findings))
        for name, fn in BASELINES.items():
            base = [to_dict(f) for f in fn(row['text'])]
            base_events[name].append(score(row['gold'], base))

        records.append({
            'findings': findings,
            'events': score(row['gold'], findings),
            'entity_matched': entity_matched(row['gold'], row['entity_type'], findings) if row['dataset'] == 'pii' else None,
            'escalated': escalated,
            'latency_ms': latency_ms,
        })

        if (i + 1) % 50 == 0 or (i + 1) == total_rows:
            print(f"{i + 1}/{total_rows} done, escalated so far: {escalated_so_far}")

    df = pd.concat([df, pd.DataFrame(records)], axis=1)
    df['covered'] = df['events'].map(lambda ev: any(k == 'tp' for k, _ in ev))   # any gold span hit

    df['correct'] = df.apply(row_correct, axis=1)
    overall_acc = df['correct'].mean() * 100
    acc_by_ds = df.groupby('dataset')['correct'].mean() * 100

    comparison = pd.concat(
        {**{n: prf(e) for n, e in base_events.items()}, 'full': prf(full_events)}, 
        names=['config', 'tier']
    )


    total_time = time.perf_counter() - start_time

    # tp / fp / fn per tier
    ev = pd.DataFrame(
        [(d, k, t) for d, evs in zip(df['dataset'], df['events']) for k, t in evs],
        columns=['dataset', 'kind', 'tier'])
    counts = (ev.groupby(['tier', 'kind']).size().unstack(fill_value=0)
                .reindex(columns=['tp', 'fp', 'fn'], fill_value=0))
    counts['precision'] = counts.tp / (counts.tp + counts.fp).replace(0, float('nan'))
    counts['recall'] = counts.tp / (counts.tp + counts.fn).replace(0, float('nan'))
    counts['f1'] = 2 * counts.precision * counts.recall / (counts.precision + counts.recall)

    escalated_count = int(df['escalated'].sum())
    pos_rows = df[df['dataset'] != 'negative']
    secret_rows = df[df['dataset'] == 'secret']
    pii_rows = df[df['dataset'] == 'pii']
    neg_rows = df[df['dataset'] == 'negative']
    neg_fp = int(neg_rows['findings'].map(bool).sum())

    lat = df.groupby('escalated')['latency_ms'].agg(
        count='count', mean='mean', median='median', p95=lambda s: s.quantile(0.95))

    entity_pct = pii_rows['entity_matched'].astype(float).mean() * 100 if len(pii_rows) else 0

    report = f"""LakanVault combined evaluation report
=====================================
file created : {datetime.now().strftime('%d/%m/%Y %I:%M%p')}
time taken   : {total_time:.2f}s

samples
-------
total        : {len(df)}
secret       : {n_secret}
pii          : {n_pii}
negative     : {n_neg}

results
-------
covered      : {pos_rows['covered'].sum()}/{len(pos_rows)} ({pos_rows['covered'].mean() * 100:.1f}%)
escalated to local llm : {escalated_count}/{len(df)} ({escalated_count / len(df) * 100:.1f}%)
negative rows with any finding : {neg_fp}/{len(neg_rows)} ({neg_fp / max(len(neg_rows), 1) * 100:.1f}%)

by dataset
----------
secret       : covered {secret_rows['covered'].mean() * 100:.1f}% ({len(secret_rows)} rows)
pii          : covered {pii_rows['covered'].mean() * 100:.1f}% ({len(pii_rows)} rows)
pii entity matched : {entity_pct:.1f}%

precision / recall / f1 by tier
-------------------------------
{counts.round(3).to_string()}

latency per row (ms) by escalated
---------------------------------
{lat.round(1).to_string()}

latency per config (ms/row, {len(lat_sample)} rows)
--------------------------------------------------
""" + "\n".join(f"{k:<16} {v:8.1f}" for k, v in cfg_ms.items()) + f"""

local llm overhead (full - regex+presidio): {llm_overhead:.1f} ms/row
overall accuracy (row-level) : {overall_acc:.1f}%
accuracy by dataset          : {acc_by_ds.round(1).to_dict()}
by entity type
--------------
"""

    by_type = pos_rows.groupby(['dataset', 'entity_type']).agg(
        covered=('covered', 'mean'),
        count=('covered', 'count'),
    )
    for (dataset, label), r in by_type.iterrows():
        report += f"{dataset:<8} {str(label):<30} covered {r['covered'] * 100:6.1f}%  ({int(r['count'])})\n"

    report += "\nprecision / recall / f1 by config and tier\n" + comparison.to_string() + "\n"

    REPORT_FILE = BASE_DIR / 'combined_report.txt'
    REPORT_FILE.write_text(report, encoding='utf-8')
    print(report)
    print(f"Report saved to: {REPORT_FILE}")

    OUTPUT_FILE = BASE_DIR / 'evaluation_result.csv'
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"Results saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()