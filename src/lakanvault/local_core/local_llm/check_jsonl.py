# python -m lakanvault.local_core.local_llm.check_jsonl
# tmep file to detect corrupted training_data
import json
from pathlib import Path

DATA = Path(__file__).parent / 'training_data.jsonl'

with open(DATA, encoding="utf-8") as f:
    for i, line in enumerate(f, 1):
        if not line.strip():
            continue
        try:
            json.loads(line)
        except json.JSONDecodeError as e:
            print(f"Invalid record at line {i}: {e}")
            print(repr(line[:200]))