# LakanVault — Demo Guide

One-page instructions for running the MVP without reading source code.

---

## Quick start (recommended — no `.exe` required)

Works on company laptops that block unsigned executables.

### Option A — LMS zip (full demo including chat)

1. Download **`LakanVault_DEMO.zip`** from the LMS or GitHub Release.
2. Unzip to a folder (e.g. `Desktop\LakanVault`).
3. **Double-click `RUN_DEMO.bat`** in the unzipped folder.
4. First run creates a Python virtual environment and installs dependencies (~1–2 minutes).
5. Browser opens at **http://127.0.0.1:8080**.
6. To stop: press **Ctrl+C** in the console window.

The zip includes an offline chat model — no LM Studio or Ollama needed.

### Option B — GitHub clone (security features only, unless you fetch runtime)

1. Clone the repository.
2. Ensure **Python 3.12+** is installed.
3. Double-click **`RUN_DEMO.bat`** (or run `.\scripts\RUN_DEMO.ps1`).
4. Demo integrity models are copied automatically from `demo_assets/models/`.
5. For chat, either:
   - Re-run with `.\scripts\RUN_DEMO.ps1 -FetchRuntime` (needs network, ~450 MB), or
   - Connect LM Studio / Ollama manually (see appendix).

---

## Demo tiers

| Tier | What you need | What works |
|------|---------------|------------|
| **A — Full** | LMS zip + Python + `RUN_DEMO.bat` | Chat, PII masking, injection block, Integrity, Pipeline, Audit |
| **B — Security-only** | GitHub clone + Python + `RUN_DEMO.bat` | Integrity, Pipeline Scan, Audit (no chat) |
| **C — Blocked** | Python also blocked by IT | Use submitted screen recording / demo video |

---

## What to evaluate (4 features)

| # | Page | Action | Expected result |
|---|------|--------|-----------------|
| 1 | **Sanitized Chat** | Click a starter chip or type `hi my name is Sami` | PII masked before model; name restored in reply; injection attempts blocked |
| 2 | **Model Integrity** | Scan models | TRUSTED / POISONED / UNVERIFIED demo cards; poisoned glow on mismatch |
| 3 | **Pipeline Scan** | Select `demo-trusted.gguf` + email in prompt | Four stages animate; audit record created |
| 4 | **Audit Log** | Open after scan | Expandable row with run_id and stage details |

Demo models are pre-loaded — no setup script required when using `RUN_DEMO.bat`.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| "Python not found" | Install Python 3.12+ from python.org, or use LMS zip on a machine with Python |
| Browser does not open | Visit http://127.0.0.1:8080 manually |
| Port 8080 in use | Close other LakanVault windows; restart |
| Chat "Not connected" | Use LMS zip (bundled model), or connect LM Studio/Ollama via top-right Connect |
| Yellow banner on Chat page | Normal without a model — use Integrity and Pipeline Scan instead |
| PowerShell script blocked | Right-click `RUN_DEMO.bat` → Run, or: `powershell -ExecutionPolicy Bypass -File scripts\RUN_DEMO.ps1` |

---

## Appendix — external LLM providers (optional)

| Provider | Default URL |
|----------|-------------|
| LM Studio | http://localhost:1234 |
| Ollama | http://localhost:11434 |
| Bundled (LMS zip) | http://127.0.0.1:8081 |

In UI: **Sanitized Chat → Connect** (top right).

---

## Further reading

- Architecture overview: `docs/demo/PROJECT_OVERVIEW.md`
- ADRs: `docs/architecture/`
