'''
run lakan vault architecture against combined secret + PII benchmark
(300 positive samples from each)

run :
python -m lakanvault.local_core.evaluation.evaluation

mostly complete
get the latency overhead of extending to local llm 
'''

import io
import time
from contextlib import redirect_stdout
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


def quiet(fn, *args):
    '''scan() prints on every escalation, silence it so the progress output stays readable'''
    with redirect_stdout(io.StringIO()):
        return fn(*args)


def scan_row(text):
    '''returns (findings as dicts, escalated_to_llm, latency_ms)'''
    before = len(calls)
    t0 = time.perf_counter()
    findings = quiet(scan, text, 'unsure')
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
    pos = sec[sec['label_binary'] == 1]
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


def main():
    df, n_secret, n_pii, n_neg = load_data()

    # warm up, this is so LM Studio loading not getting accounted in the latency 
    for fn in CONFIGS.values():
        quiet(fn, "warm up: contact john@example.com")
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
            quiet(fn, t)
        cfg_ms[name] = (time.perf_counter() - t0) / len(lat_sample) * 1000
    llm_overhead = cfg_ms['full'] - cfg_ms['regex+presidio']
    calls.clear()

    start_time = time.perf_counter()

    records = []
    escalated_so_far = 0
    total_rows = len(df)

    for i, (_, row) in enumerate(df.iterrows()):
        findings, escalated, latency_ms = scan_row(row['text'])
        escalated_so_far += int(escalated)

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