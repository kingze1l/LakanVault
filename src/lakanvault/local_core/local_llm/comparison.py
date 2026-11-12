# to run just python -m lakanvault.local_core.local_llm.comparison
import csv, json
from pathlib import Path
from ..findings import Tier
from . import detector, train

CSV = Path(__file__).parent / 'model_benchmark.csv'    # columns: text, category, answer
N = 100
BASE = 'google/gemma-4-e4b'
FINETUNED = 'gemma-4-e4b-it@q8_0'                
CURRENT_PROMPT = detector.SYSTEM_PROMPT    # captured before overwrite it

def gold(answer):
    # BENIGN items are not sensitive, so the model should NOT flag them
    try:
        return {
            f['span']
            for f in json.loads(answer)['findings']
            if f['tier'] != 'BENIGN'
        }
    except json.JSONDecodeError as e:
        print('\nINVALID JSON FOUND!')
        print('Error:', e)
        print('Raw answer:', repr(answer))
        print('Around error:', repr(answer[max(0, e.pos-15):e.pos+15]))
        raise

def predict(text, model, prompt):
    detector.MODEL, detector.SYSTEM_PROMPT = model, prompt   # ask_llm reads these at call time
    res = detector.ask_llm(text)
    if res is None:
        return None                                            # LLM failure (bad JSON / truncated)
    return {f.text for f in res if f.tier != Tier.BENIGN}

def evaluate(name, model, prompt, rows):
    by_cat = {}
    for text, g, cat in rows:
        p = predict(text, model, prompt)
        fail = p is None
        p = set() if fail else p
        s = by_cat.setdefault(cat, dict(tp=0, fp=0, fn=0, exact=0, n=0, fail=0))
        s['tp'] += len(g & p)
        s['fp'] += len(p - g)
        s['fn'] += len(g - p)
        s['exact'] += (g == p)
        s['n'] += 1
        s['fail'] += fail
    report(name, by_cat)

def report(name, by_cat):
    print(f'\n{name}')
    total = dict(tp=0, fp=0, fn=0, exact=0, n=0, fail=0)
    for cat, s in sorted(by_cat.items()):
        for k in total:
            total[k] += s[k]
        _print_row(cat, s)
    _print_row('ALL', total)

def _print_row(label, s):
    prec = s['tp'] / (s['tp'] + s['fp']) if s['tp'] + s['fp'] else 0
    rec = s['tp'] / (s['tp'] + s['fn']) if s['tp'] + s['fn'] else 0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0
    print(f'  {label:<16} P={prec:.2f} R={rec:.2f} F1={f1:.2f} '
          f'TP={s["tp"]} FP={s["fp"]} FN={s["fn"]} '
          f'row_acc={s["exact"] / s["n"]:.2f} llm_fail={s["fail"]}')

if __name__ == '__main__':
    with open(CSV, encoding='utf-8') as f:
        rows = [(r['text'], gold(r['answer']), r['category']) for r in csv.DictReader(f)][:N]

    seen = {json.loads(l)['text'] for l in open(train.DATA, encoding='utf-8') if l.strip()}
    assert not any(t in seen for t, _, _ in rows), 'eval rows overlap training data'

    print(f'{len(rows)} rows')
    evaluate('base, current prompt', BASE, CURRENT_PROMPT, rows)
    evaluate('base, training prompt', BASE, train.SYSTEM_PROMPT, rows)   # optional  same-conditions comparison
    evaluate('finetuned, training prompt', FINETUNED, train.SYSTEM_PROMPT, rows)