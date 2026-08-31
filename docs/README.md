# LakanVault documentation index

Start here. Each folder has a single purpose.

## Quick links

| I want to… | Read |
|------------|------|
| Run the demo | [`demo/GUIDE.md`](demo/GUIDE.md) |
| Understand the product (markers) | [`demo/PROJECT_OVERVIEW.md`](demo/PROJECT_OVERVIEW.md) |
| See current sprint status | [`v2/PHASE2_PLAN.md`](v2/PHASE2_PLAN.md) |
| Understand Option 3 gateway | [`architecture/005-option3-hybrid-gateway.md`](architecture/005-option3-hybrid-gateway.md) |
| Configure Continue / Cursor / MCP | [`v2/CLIENT_COMPAT.md`](v2/CLIENT_COMPAT.md) |
| Navigate the codebase | [`REPO_STRUCTURE.md`](REPO_STRUCTURE.md) |
| CS301 discovery notes | [`cs301/repo-audit.md`](cs301/repo-audit.md) |

## Folder map

```
docs/
├── README.md                 ← you are here
├── REPO_STRUCTURE.md         ← code layout (src/, tests/, scripts/)
├── architecture/             ← ADRs (decisions, boundaries, Option 3)
├── cs301/                    ← CS301 course / discovery artifacts
├── demo/                     ← LMS marker guides (public in zip)
└── v2/                       ← Phase 2 plans, backlog, client compat
```

## Architecture decisions (`architecture/`)

| ADR | Topic |
|-----|--------|
| [001](architecture/001-hybrid-boundary.md) | Layer boundaries (app → orchestration → local_core) |
| [002](architecture/002-pipeline-order.md) | Pipeline stage order |
| [003](architecture/003-cryptographic-provenance.md) | Model hashing / provenance |
| [004](architecture/004-ui-state-isolation.md) | UI shell vs gateway logic |
| [005](architecture/005-option3-hybrid-gateway.md) | **CS301 Option 3** — proxy, vault, MCP shim |

## Phase 2 planning (`v2/`)

| File | Purpose |
|------|---------|
| [PHASE2_PLAN.md](v2/PHASE2_PLAN.md) | Sprint tickets, done/remaining checklist |
| [PLAN.md](v2/PLAN.md) | High-level execution plan |
| [CLIENT_COMPAT.md](v2/CLIENT_COMPAT.md) | Continue, Cursor, Claude Code hooks |
| [RESEARCH_BACKLOG.md](v2/RESEARCH_BACKLOG.md) | RQ1/RQ2 research items |
| [IDE_EXTENSION_NOTES.md](v2/IDE_EXTENSION_NOTES.md) | Future IDE extension notes |

## Not in git (local / LMS only)

- `docs/submission/` — assessment reports (gitignored)
- `docs/internal/` — team-only wiring maps (gitignored)
- `docs/SYSTEM_GUIDE.md`, `docs/PROJECT_FILES.md` — dev guides (gitignored)

## Peer review

Sprint gates: **Joan Allysen** (detection, anonymizer, RQ1). See [`v2/PHASE2_PLAN.md`](v2/PHASE2_PLAN.md).
