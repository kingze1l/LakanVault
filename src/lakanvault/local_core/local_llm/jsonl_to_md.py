# personal use file, just to read the sample data to see if its correct
# python -m lakanvault.local_core.local_llm.jsonl_to_md

import json
from pathlib import Path
INPUT_FILE = Path(__file__).parent / 'training_data.jsonl'
OUTPUT_FILE = Path(__file__).parent / 'training_data.md'

with open(INPUT_FILE, "r", encoding="utf-8") as f:
    rows = [json.loads(line) for line in f if line.strip()]

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.write("# Training Data Examples\n\n")
    f.write("| # | Text | Type | Tier | Span | Confidence |\n")
    f.write("|---|---|---|---|---|---|\n")

    for i, row in enumerate(rows, 1):
        text = row["text"].replace("\n", "<br>")
        findings = row["answer"]["findings"]

        if not findings:
            f.write(f"| {i} | {text} | - | - | - | - |\n")
            continue

        for finding in findings:
            f.write(
                f"| {i} "
                f"| {text} "
                f"| {finding['type']} "
                f"| {finding['tier']} "
                f"| {finding['span']} "
                f"| {finding['confidence']} |\n"
            )

print(f"Generated {OUTPUT_FILE} with {len(rows)} examples.")

