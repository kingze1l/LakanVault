# LakanVault — IDE Extension Notes

**Status:** Research / additive track (C1–C4 in [RESEARCH_BACKLOG.md](./RESEARCH_BACKLOG.md))  
**Does not replace:** MCP server or detection pipeline (proposal-locked). The extension is a **client** of local LakanVault.

---

## 1. Why an extension

MCP alone cannot force the agent to use our tools. A VS Code / Cursor-compatible extension can:

- Intercept or mediate **paste** into the editor
- Offer **Classify selection** / **Safe paste** commands
- Show tier / Block status in the status bar
- Call the existing local gateway (`classify_text` / HTTP API) so detection stays in Python

It will **not** (unless a spike proves otherwise) see the final cloud-bound agent prompt.

---

## 2. Suggested architecture

```text
VS Code / Cursor Extension (TypeScript)
    │  localhost only
    ▼
LakanVault FastAPI / gateway  (existing)
    │
    ▼
classifier + Presidio + policy + tokens
```

Do not reimplement regex/Presidio in TypeScript.

---

## 3. MVP extension scope (PoC)

| Feature | Priority |
|---------|----------|
| Command: `LakanVault: Classify Selection` | Must |
| Show Allow / Warn / Mask / Block + reason | Must |
| Optional: on paste, prompt to classify first | Should |
| Status bar: last tier | Should |
| Settings: localhost URL (default `http://127.0.0.1:8080`) | Must |
| Requires LakanVault running locally | Document |

Out of PoC: full agent prompt rewrite, silent keylogging, MITM.

---

## 4. Spike before promising “chat gate”

**C3 spike:** Does this Cursor/VS Code version expose any API for “text about to be sent to the model”?

- If **yes** → design pre-submit classify (huge win).  
- If **no** → document it; keep paste + selection + MCP tools as the story.

Record result in the RESEARCH_BACKLOG spike log.

---

## 5. Sideload demo (capstone-first)

1. Scaffold extension (`yo code` or manual `package.json` + `src/extension.ts`).  
2. `vsce package` → `.vsix`.  
3. Install in VS Code/Cursor: **Install from VSIX**.  
4. Start LakanVault locally; run Classify Selection in a demo file with a fake `sk-` key.

Sideload is enough for CS301 demonstration. Store publish is optional polish.

---

## 6. Publishing to VS Code Marketplace

1. Create a **Publisher** on the Visual Studio Marketplace (Microsoft account / Azure DevOps).  
2. Create a Personal Access Token with Marketplace publish scope.  
3. Install tooling: `npm i -g @vscode/vsce`.  
4. Set `publisher`, `name`, `version`, `engines.vscode` in `package.json`.  
5. Write Marketplace listing: what clipboard/selection access you use; **localhost-only**; companion app required.  
6. `vsce package` then `vsce publish`.  
7. Optional: also publish to **Open VSX** for other editors.

### Cursor note

Cursor is VS Code–compatible but not identical to Microsoft’s store. For the report: primary path = **VS Code Marketplace + VSIX sideload**; verify current Cursor install options at demo time.

### Review / trust expectations

- No keystroke logging  
- Clear consent copy for clipboard  
- No exfil of prompt text to cloud from the extension  
- Open update story for a student PoC  

---

## 7. Effort estimate

| Deliverable | Size |
|-------------|------|
| Sideload PoC (classify selection) | M |
| Paste warn/block UX | M |
| Marketplace listing + publish | M |
| Pre-send hook (if API exists) | Unknown — spike first |

---

## 8. Privacy / pitch one-liner

> “The LakanVault IDE extension asks your local gateway to classify selected or pasted text before it becomes part of an AI chat — it does not send your code to us, and it does not replace the MCP detection pipeline; it is another on-ramp into the same on-device policy engine.”
