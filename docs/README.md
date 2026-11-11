# LakanVault documentation index

Start here. Each folder has a single purpose.

## Quick links

| I want to… | Read |
|------------|------|
| See current sprint status | [`v2/PHASE2_PLAN.md`](v2/PHASE2_PLAN.md) |
| Understand Option 3 gateway | [`architecture/005-option3-hybrid-gateway.md`](architecture/005-option3-hybrid-gateway.md) |
| Configure Continue / Cursor / MCP | [`v2/CLIENT_COMPAT.md`](v2/CLIENT_COMPAT.md) |
| Navigate the codebase (plain map) | [`REPO_STRUCTURE.md`](REPO_STRUCTURE.md) |
| Cursor MCP setup (CS301) | [`cs301/CURSOR_SETUP.md`](cs301/CURSOR_SETUP.md) |
| What shipped recently | [`../WHAT_CHANGED.md`](../WHAT_CHANGED.md) |

## Folder map

```
docs/
├── README.md                 ← you are here
├── REPO_STRUCTURE.md         ← code layout in plain English
├── architecture/             ← ADRs (keep — these are the real decisions)
├── cs301/                    ← course Cursor setup
└── v2/                       ← sprint plan + client compat
```

## Architecture decisions (`architecture/`)

| ADR | Topic |
|-----|--------|
| [001](architecture/001-hybrid-boundary.md) | Layer boundaries (app → orchestration → local_core) |
| [002](architecture/002-pipeline-order.md) | Pipeline stage order |
| [003](architecture/003-cryptographic-provenance.md) | Model hashing / provenance |
| [004](architecture/004-ui-state-isolation.md) | UI shell vs gateway logic |
| [005](architecture/005-option3-hybrid-gateway.md) | **CS301 Option 3** — proxy, vault, MCP shim |

## Phase 2 (`v2/`)

| File | Purpose |
|------|---------|
| [PHASE2_PLAN.md](v2/PHASE2_PLAN.md) | Sprint tickets, done/remaining checklist |
| [CLIENT_COMPAT.md](v2/CLIENT_COMPAT.md) | Continue, Cursor, Claude Code hooks |

## CS301 (`cs301/`)

| File | Purpose |
|------|---------|
| [CURSOR_SETUP.md](CURSOR_SETUP.md) | Dev MCP / Cursor wiring |
| [README.md](cs301/README.md) | Course folder index |

## Not in git (local only)

- `docs/internal/` — team-only wiring maps (gitignored)

## Peer review

Sprint gates: **Joan Allysen** (detection, anonymizer, RQ1). See [`v2/PHASE2_PLAN.md`](v2/PHASE2_PLAN.md).
