# My dev setup notes

## What I use

- Python 3.12+
- Windows on HP EliteBook
- Editable install: `pip install -e .`

## First-time setup (me)

1. `python -m venv .venv`
2. `.venv\Scripts\Activate.ps1`
3. `pip install -e .`
4. Copy `.env.example` → `.env` if I need path overrides

## SpaCy models — I sideload, never pull at runtime

Presidio needs SpaCy. In air-gapped / submission mode I must **not** hit the web when the app runs.

What I do:

1. On a machine with internet: `python -m spacy download en_core_web_sm` (once)
2. Copy the model folder to something like `./data/models/spacy/en_core_web_sm/`
3. Point Presidio/SpaCy at that local path in config — no `spacy download` in production
4. Note the exact model version in my submission appendix

When `cloud.enabled` is false, I treat runtime downloads as a hard no.

## Gateway vs Streamlit — I keep them separate

Streamlit only in `app/`. `orchestration/gateway.py` stays plain Python (no `st.*`) so I can wrap it in a background `.exe` later. See `architecture/004-ui-state-isolation.md`.

## Boundary check (after P1b)

```powershell
python scripts/verify_boundaries.py
```

## Config files I touch

- `config/default.yaml` — baseline, cloud off, 1MB hash chunks
- `config/local.yaml` — my machine paths
- `config/cloud.example.yaml` — template only; real secrets stay local
