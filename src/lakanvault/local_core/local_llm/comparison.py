# python -m lakanvault.local_core.local_llm.eval_llm
import csv, json
from pathlib import Path
from ..findings import Tier
from . import local_llm, train

CSV = Path(__file__).parent / 'eval.csv'    # columns: text, answer
N = 100
BASE = 'google/gemma-4-e4b'
FINETUNED = 'gemma-4-e4b-it'                
CURRENT_PROMPT = local_llm.SYSTEM_PROMPT    # captured before overwrite it

def gold(answer):
    # BENIGN items are not sensitive, so the model should NOT flag them
    return {f['span'] for f in json.loads(answer)['findings'] if f['tier'] != 'BENIGN'}

def predict(text, model, prompt):
    local_llm.MODEL, local_llm.SYSTEM_PROMPT = model, prompt   # ask_llm reads these at call time
    res = local_llm.ask_llm(text)
    if res is None:
        return None                                            # LLM failure (bad JSON / truncated)
    return {f.text for f in res if f.tier != Tier.BENIGN}

def evaluate(name, model, prompt, rows):
    tp = fp = fn = fail = exact = 0
    for text, g in rows:
        p = predict(text, model, prompt)
        if p is None:
            fail += 1
            p = set()
        tp += len(g & p)      # gold found
        fp += len(p - g)      # flagged something that is not gold (incl. BENIGN lookalikes)
        fn += len(g - p)      # gold missed
        exact += (g == p)     # row fully right (also true when nothing to find and nothing flagged)
    prec = tp / (tp + fp) if tp + fp else 0
    rec = tp / (tp + fn) if tp + fn else 0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0
    print(f'{name:<28} TP={tp} FP={fp} FN={fn} P={prec:.2f} R={rec:.2f} F1={f1:.2f} '
        f'row_acc={exact / len(rows):.2f} llm_fail={fail}')

if __name__ == '__main__':
    with open(CSV, encoding='utf-8') as f:
        rows = [(r['text'], gold(r['answer'])) for r in csv.DictReader(f)][:N]

    seen = {json.loads(l)['text'] for l in open(train.DATA, encoding='utf-8') if l.strip()}
    assert not any(t in seen for t, _ in rows), 'eval rows overlap training data'

    print(f'{len(rows)} rows')
    evaluate('base, current prompt', BASE, CURRENT_PROMPT, rows)
    evaluate('base, training prompt', BASE, train.SYSTEM_PROMPT, rows)   # optional  same-conditions comparison
    evaluate('finetuned, training prompt', FINETUNED, train.SYSTEM_PROMPT, rows)