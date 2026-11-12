# Quick LakanVault scan usage guide

Use this to scan a prompt, see what was found, and print a draft with the sensitive values replaced.

1. Create a virtual environment and install the packages in `requirements.txt`.
2. In Command Prompt or PowerShell, change into the `src` folder (`cd src`). The command below is run from there.
3. Open `local_core/samples.py` and put the text you want to scan in the `samples` list. One string is one prompt. You can add more than one.
4. Set up the local model in LM Studio. The scan calls it when a regex or Presidio finding is unsure, or when `escalate.py` flags the prompt. Regex and Presidio still run if this step is skipped. Those unsure cases are then left as the fast layer found them.

   - Install [LM Studio](https://lmstudio.ai) and download `google/gemma-4-e4b`. That id is `MODEL` in `local_llm/detector.py`.
   - Load the model, then start the local server. The detector calls `http://localhost:1234/v1` (OpenAI-compatible). The API key in code is the placeholder `lm_studio`.
   - The model id in LM Studio has to match `MODEL`. If you load a different model, change that line before you scan.
   - Leave the server running while you run the scan. The first call can take several seconds while the model answers.
5. Run:

```
python -m lakanvault.local_core.scan
```

6. Each sample prints like this:

```
====================================================================================================
SAMPLE 1/1
PROMPT: 'My name is Joan Allysen and my api key is sk_23jasgjhbGJHVDSAug23'
  PERSON               PII_MODERATE    0.85 [11:23] 'Joan Allysen' confident <- presidio
  openai-api-key       SECRET          0.60 [42:65] 'sk_23jasgjhbGJHVDSAug23' confident <- llm
  Time: 7442.81 ms
  DRAFT TO SEND TO EXTERNAL LLM: 'My name is Michele Hurst and my api key is sk_39kwlfdxrGZAKOFSjq42'
====================================================================================================
Total time: 7443.62 ms
```

How to read one finding line:

- `PERSON` or `openai-api-key` is the entity type.
- `PII_MODERATE` or `SECRET` is the tier.
- `0.85` is the confidence score.
- `[11:23]` is the character span in the prompt.
- The quoted text is the matched value.
- `confident` means the score was high enough to keep. `ESCALATE` means it was unsure and was sent to the local model.
- `presidio` or `llm` is which detector produced it.

`DRAFT TO SEND TO EXTERNAL LLM` is the same prompt after the anonymizer replaces each finding with a fake. `Total time` is the whole run.

# Quick LakanVault evaluation guide

Use this to benchmark detection accuracy (precision, recall, F1, coverage) across secret and PII datasets and measure latency.

1. Install the evaluation packages:

```
pip install pandas pyarrow fsspec huggingface_hub
```

2. In Command Prompt or PowerShell, change into the `src` folder (`cd src`). The command below is run from there.
3. Make sure LM Studio is running with `google/gemma-4-e4b` on `http://localhost:1234/v1` if you want to test local LLM escalation. If skipped, the fast layer still benchmarks.
4. Run the combined benchmark (1200 samples: 300 secrets, 300 PII, 600 negative):

```
python -m lakanvault.local_core.evaluation.evaluation
```

Or run the secret database benchmark only:

```
python -m lakanvault.local_core.evaluation.secret_database
```

5. When finished, it prints the summary table and saves two files in `local_core/evaluation/`:
   - `combined_report.txt`: Summary of accuracy, coverage, precision/recall/F1, and latencies.
   - `evaluation_result.csv`: Row-by-row findings, latencies, and escalation results.

## Summary of what I did (Joan)

To summarize, I worked on the regex + presidio + local llm (if escalated) pipeline to finds secrets and PII in texts before reaching the external LLM and replaces them with fakes (anonymizer) before the text leaves the machine. Regex catches secrets, Presidio catch personal data. A local model (Gemma, fine-tuned with LoRA) catches the rest (harder cases), including secrets written in plain words. Policy then picks allow, warn, mask, or block. The anonymizer writes format-preserving fakes and can put the real values back after the external model replies. Evaluation scripts score that pipeline on secret and PII samples.

As the fine-tuned local model were tested and proven to perform less accurately compared to original model, I decided to use the base Gemma 4 to do the whole evaluation pipeline across different confident threshold.

Folders I worked on are all inside `local_core`: anonymizer, evaluation, local_llm, pii, policy, secrets. The scan entry points sit next to those folders: `scan.py`, `findings.py`, and `escalate.py`. There's also `debug_secret_and_pii.py` this was mainly a test file to check if the fast layer perform as it should. The rest of the folder or files were from Sami

## scan, findings, escalate

These three files sit in `local_core` itself. `scan.py` is the script in the usage guide above. 

- `scan.py`: The core of the pipeline (regex + presidio + local llm) runs secret detection and PII detection, then asks the local model when a finding is unsure or the prompt looks suspicious. I also added the entrance gateway here for Sami to use in ProtectedPrompt class where there is `process_input` that scans, applies policy, and sanitizes and `process_output` that restores the real values in the reply. Running the file as a module prints the sample report above.
- `findings.py`: Shared types. `Finding` holds the entity, span, score, tier, and source. `Tier` is SECRET, PII_HIGH, PII_MODERATE, PII_LOW, or BENIGN. A score of 0.75 or higher is confident. Below 0.35 is dropped. Anything in between is marked for the local model. `resolve_overlaps` keeps one finding when two hit the same characters and rank them.
- `escalate.py`: Cheap checks that run before the local model. If the prompt has an uncovered password or key phrase, or a long mixed token with high entropy, it escalate the fast layer to the local model.

## anonymizer

Replaces a detected value with a fake and stores the mapping so it can be restored later. Secrets keep their shape (format preserving). PII is swapped for a lookalike (surrogate anonymizer).

- `anonymizer.py`: `Vault` writes each real value to a fake, saves the pair in sqlite, rewrites the prompt, and restores the real values in the reply.
- `helper.py`: Loads a local key and builds a seeded randomizer so the same secret always gets the same fake. Digits stay digits, letters stay letters.
- `keywords.py`: Prefixes and markers for known secret formats (`sk-ant-`, `AKIA`, and similar) so the recognizable part of a key is left in place (used for format preserving).
- `secret_fakes.py`: Builds a fake secret. It keeps the matching keyword and randomizes the rest of the string.
- `pii_fakes.py`: Builds fake PII with Faker and small format fixes (Luhn for cards, check digits for IBANs, reserved ranges for IPs).

## evaluation

Checks whether the detectors actually find the sensitive span, and how often the local model is called.

- `secret_database.py`: Runs the secret scan over the Prowl secrets corpus (positive samples only) and marks a row covered even when the finding is only part of the secret. 
- `pii_database.py`: Deprecated, pretty much the same but for PII csv. It records whether the span was found and whether the entity type matched. 
- `evaluation.py`: Combined run of 1200 samples (300 secrets, 300 PII, 600 negative). Compares regex, Presidio, both, and the full scan, and records latency and how often the local model was asked.

## local_llm

The local model that looks at text the regex and Presidio layers are unsure about.

- `detector.py`: Sends the text to a model on localhost (LM Studio) and turns the JSON reply into findings with a type, tier, span, and confidence.
- `train.py`: Fine-tunes Gemma 4 E4B with LoRA on `training_data.jsonl` and exports a GGUF the detector can load.
- `comparison.py`: Scores the base model against the fine-tuned one on `model_benchmark.csv` (true positives, false positives, misses).
- `jsonl_to_md.py`: Turns `training_data.jsonl` into a markdown table so the examples are easy to read.
- `training_data.md`: That table: example prompts with the expected type, tier, span, and confidence.

## secrets

The regex layer. It finds API keys, tokens, and passwords in plain text and marks them `SECRET`. `scan.py` calls `detect_secrets` before Presidio.

- `detector.py`: Runs the Gitleaks-style rules and a few extra rules (connection strings with a password). Keywords narrow which rules run. Low entropy or a placeholder word lowers the score into the unsure band so the local model can check it. `detect_secrets` is the entry point.
- `config_loader.py`: Reads `gitleaks.toml` into those rules. Path and commit allowlists are skipped because the scan is plain prompt text, not a git repo.
- `gitleaks.toml`: The Gitleaks rule file (regex, keywords, entropy, allowlists) that the loader reads.
- `gitleaks_ids.txt`: The list of rule ids from that file, one per line (for example `aws-access-token`, `anthropic-api-key`).
- `__init__.py`: Re-exports `detect_secrets`, `SecretDetector`, and `shannon_entropy`.

## pii

Finds personal data in a prompt and assigns it a tier.

- `detector.py`: Presidio (spaCy) finds entities such as email, card, and SSN. Extra name patterns catch phrases like "my name is ...". Weak hits are left for the local model.
- `pii_entity_tier.py`: Maps each Presidio entity to `PII_HIGH`, `PII_MODERATE`, or `PII_LOW` (government IDs and financial data high, names and emails moderate, location and IP low).

## policy

Decides the action once findings exist.

- `engine.py`: Maps each tier to an action. Confident secrets are blocked. High and moderate PII are masked. Low PII is a warning. If the local model fails, `FAILURE_MODE` says whether to block or trust the earlier detectors.
- `__init__.py`: Re-exports the older tier-to-action helpers (`public`, `internal`, `confidential`, `secret`).
