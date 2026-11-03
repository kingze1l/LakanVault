'''
print all rule ids from gitleaks.toml and save them to gitleaks_ids.txt (one per line). this is for llm dataset
run :
python -m lakanvault.local_core.secrets.temp
'''
from pathlib import Path
import tomllib  # Python 3.11+

RULES_PATH = Path(__file__).parent / 'gitleaks.toml'
OUTPUT_PATH = Path(__file__).parent / 'gitleaks_ids.txt'

with RULES_PATH.open("rb") as f:
    rules = tomllib.load(f)["rules"]

ids = [r["id"] for r in rules]
with OUTPUT_PATH.open('w', encoding='utf-8') as f:
    f.write("\n".join(ids) + "\n")

print(f"{len(ids)} ids saved to gitleaks_ids.txt")