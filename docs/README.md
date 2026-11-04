# LakanVault docs

Everything here describes the code on `main` as of Oct 2026. Start with the root [`README.md`](../README.md); this folder holds the detail.

| I want to… | Read |
|------------|------|
| Block a fake API key in Cursor (sandbox, MCP) | [`cs301/CURSOR_SETUP.md`](cs301/CURSOR_SETUP.md) + [`cs301/examples/cursor-mcp.json`](cs301/examples/cursor-mcp.json) |
| Point Continue / another client at the proxy | [`v2/CLIENT_COMPAT.md`](v2/CLIENT_COMPAT.md) |
| Find a file in `src/` | [`REPO_STRUCTURE.md`](REPO_STRUCTURE.md) |
| See what is done vs remaining | [`v2/PHASE2_PLAN.md`](v2/PHASE2_PLAN.md) |
| See research items / threat matrix for the report | [`v2/RESEARCH_BACKLOG.md`](v2/RESEARCH_BACKLOG.md) |

## Architecture decisions (`architecture/`)

| ADR | Decision | Still true? |
|-----|----------|-------------|
| [001](architecture/001-hybrid-boundary.md) | `app → orchestration → local_core` via `contracts`; enforced by `scripts/verify_boundaries.py` | Yes |
| [002](architecture/002-pipeline-order.md) | Pipeline order integrity → threat → privacy → audit, fail-closed | Yes |
| [003](architecture/003-cryptographic-provenance.md) | Model SHA-256 baseline; signed cloud enrichment | Hashing yes; cloud enrichment not built (cloud off) |
| [004](architecture/004-ui-state-isolation.md) | UI shell holds no security logic | Yes (UI currently API-only) |
| [005](architecture/005-option3-hybrid-gateway.md) | Option 3: explicit localhost proxy + in-memory token map + MCP shim | Yes, implemented |
| [data-classification](architecture/data-classification.md) | What may ever leave the machine (counts/metadata only) | Yes |

## Folder map

```
docs/
├── README.md               this index
├── REPO_STRUCTURE.md       per-file code layout
├── architecture/           ADRs 001-005 + data classification
├── cs301/                  Cursor MCP setup + config template
└── v2/                     sprint plan, client matrix, research backlog
```

`docs/internal/` is gitignored (team-only notes).

## Peer review

Sprint gates: **Joan Allysen** (detection, anonymizer, RQ1). Checklist in [`v2/PHASE2_PLAN.md`](v2/PHASE2_PLAN.md).
