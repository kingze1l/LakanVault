"""LakanVault dashboard — Streamlit UI shell.
Per ADR-004: this file only renders. All logic lives in Gateway.
No imports from local_core or cloud_intelligence here.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import streamlit as st

from lakanvault.contracts.dtos import ScanRequest
from lakanvault.orchestration.gateway import Gateway

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="LakanVault",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Theme ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&family=Inter:wght@400;500;600&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.block-container { padding-top: 1.25rem; max-width: 1200px; }
code, pre, .mono { font-family: 'JetBrains Mono', monospace !important; }

.pill {
    display: inline-block; padding: 2px 10px; border-radius: 999px;
    font-size: 11px; font-weight: 600; font-family: 'JetBrains Mono', monospace;
    letter-spacing: .02em;
}
.PASS, .TRUSTED   { background: rgba(0,229,160,0.12); color: #00e5a0; border: 1px solid rgba(0,229,160,0.3); }
.WARN, .UNVERIFIED{ background: rgba(210,153,34,0.12); color: #d29922; border: 1px solid rgba(210,153,34,0.3); }
.FAIL, .ERROR, .POISONED { background: rgba(248,81,73,0.12); color: #f85149; border: 1px solid rgba(248,81,73,0.3); }
.SKIPPED, .QUARANTINED { background: rgba(139,148,158,0.12); color: #8b949e; border: 1px solid rgba(139,148,158,0.3); }

.metric-card {
    border: 1px solid rgba(139,148,158,0.25);
    border-radius: 10px; padding: 14px 18px;
}
.metric-label { font-size: 11px; opacity: 0.6; letter-spacing: .08em; text-transform: uppercase; }
.metric-val   { font-size: 24px; font-weight: 600; margin-top: 6px; font-family: 'JetBrains Mono', monospace; }
.ok   { color: #00e5a0; }
.err  { color: #f85149; }
.warn { color: #d29922; }

.flow-row { display: flex; gap: 0; }
.flow-stage {
    flex: 1; text-align: center; padding: 12px 8px;
    border: 1px solid rgba(139,148,158,0.25);
    position: relative;
}
.flow-stage:first-child { border-radius: 8px 0 0 8px; }
.flow-stage:last-child { border-radius: 0 8px 8px 0; }
.flow-stage:not(:last-child)::after {
    content: '→'; position: absolute; right: -14px; top: 50%;
    transform: translateY(-50%); opacity: 0.4; font-size: 14px; z-index: 2;
}
.flow-name { font-size: 10px; opacity: 0.6; letter-spacing: .08em; text-transform: uppercase; }
.flow-status { margin-top: 6px; }

.chat-bubble {
    border-radius: 10px; padding: 12px 16px; margin-bottom: 10px;
    font-size: 14px; line-height: 1.5;
}
.chat-user { background: rgba(0,229,160,0.07); border: 1px solid rgba(0,229,160,0.2); }
.chat-ai   { border: 1px solid rgba(139,148,158,0.25); }
.chat-label { font-size: 10px; opacity: 0.6; letter-spacing: .08em; text-transform: uppercase; margin-bottom: 6px; }

.console {
    background: #010409; border: 1px solid rgba(139,148,158,0.25); border-radius: 8px;
    padding: 12px 16px; font-family: 'JetBrains Mono', monospace; font-size: 11.5px;
    min-height: 100px; max-height: 220px; overflow-y: auto; color: #e6edf3;
}
.console-line { margin-bottom: 2px; }
</style>
""", unsafe_allow_html=True)


# ── Gateway (cached) ────────────────────────────────────────────────────────
@st.cache_resource
def get_gateway() -> Gateway:
    config_dir = Path(__file__).parents[4] / "config"
    if not config_dir.exists():
        config_dir = Path("./config")
    return Gateway(config_dir=config_dir)


def pill(status: str) -> str:
    return f"<span class='pill {status}'>{status}</span>"


def metric_card(label: str, val: str, cls: str = "") -> str:
    return (
        f"<div class='metric-card'>"
        f"<div class='metric-label'>{label}</div>"
        f"<div class='metric-val {cls}'>{val}</div>"
        f"</div>"
    )


# ── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🛡️ LakanVault")
    st.caption("v0.1.0 · air-gapped security gateway")
    st.divider()

    page = st.radio(
        "navigate",
        ["💬 Chat", "🔍 Model Scan", "🧬 Model Integrity", "📋 Audit Log", "⚙️ Config"],
        label_visibility="collapsed",
    )

    st.divider()
    cfg = get_gateway()._cfg
    cloud_on = cfg.get("cloud", {}).get("enabled", False)
    st.markdown(f"**Cloud** &nbsp; {'🟢 enabled' if cloud_on else '🔴 disabled'}")

    ai_cfg = cfg.get("local_ai", {})
    st.markdown(f"**LM Studio** &nbsp; `{ai_cfg.get('base_url', '')}`")


gateway = get_gateway()


# ═══════════════════════════════════════════════════════════════════════════
# PAGE: CHAT  (sanitized local AI chat)
# ═══════════════════════════════════════════════════════════════════════════
if page == "💬 Chat":
    st.markdown("### Sanitized Chat")
    st.caption("Prompts are scrubbed of PII before reaching the local model, then restored in the reply.")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    models = gateway.lmstudio_models()
    c1, c2 = st.columns([3, 1])
    with c1:
        if models:
            st.success(f"LM Studio connected — {len(models)} model(s) loaded", icon="✅")
            model_choice = st.selectbox("model", models, label_visibility="collapsed")
        else:
            st.warning("LM Studio not reachable. Start the local server (Developer tab → Start Server).", icon="⚠️")
            model_choice = None
    with c2:
        if not gateway._anonymizer.available:
            st.warning("Presidio/spaCy not installed — sanitization disabled", icon="⚠️")

    st.divider()

    for turn in st.session_state.chat_history:
        st.markdown(
            f"<div class='chat-bubble chat-user'><div class='chat-label'>You</div>{turn['prompt']}</div>",
            unsafe_allow_html=True,
        )
        if turn.get("pii_span_count", 0) > 0:
            st.markdown(
                f"<div class='console' style='margin-bottom:10px'>"
                f"<div class='console-line' style='color:#d29922'>"
                f"🔒 sanitized → {turn['sanitized_prompt']}</div></div>",
                unsafe_allow_html=True,
            )
        if turn.get("error"):
            st.error(turn["error"])
        else:
            badge = pill('PASS' if turn['pii_span_count'] == 0 else 'WARN')
            st.markdown(
                f"<div class='chat-bubble chat-ai'><div class='chat-label'>Assistant"
                f" &nbsp;{badge}&nbsp; {turn['pii_span_count']} PII span(s) masked</div>"
                f"{turn['restored_response']}</div>",
                unsafe_allow_html=True,
            )

    prompt = st.chat_input("Type a message — try including a name, email, or phone number…")
    if prompt:
        with st.spinner("sanitizing → sending to local model → restoring PII…"):
            result = gateway.chat(prompt, model=model_choice)
            result["prompt"] = prompt
            st.session_state.chat_history.append(result)
        st.rerun()


# ═══════════════════════════════════════════════════════════════════════════
# PAGE: MODEL SCAN  (file integrity / threat / privacy / audit pipeline)
# ═══════════════════════════════════════════════════════════════════════════
elif page == "🔍 Model Scan":
    st.markdown("### Pipeline Scan")
    st.caption("Run integrity → threat_scanner → privacy → audit on a model or prompt file.")

    col1, col2 = st.columns([3, 1])
    with col1:
        target = st.text_input(
            "path", placeholder="./data/models/llama-3-8b.gguf", label_visibility="collapsed",
        )
    with col2:
        run_btn = st.button("▶ Run scan", use_container_width=True, type="primary")

    st.divider()

    stage_names = ["integrity", "threat_scanner", "privacy", "audit"]
    flow_ph = st.empty()

    def render_flow(statuses: dict[str, str]):
        html = "<div class='flow-row'>"
        for name in stage_names:
            status = statuses.get(name, "—")
            badge = pill(status) if status != "—" else "<span class='pill SKIPPED'>—</span>"
            html += (
                f"<div class='flow-stage'>"
                f"<div class='flow-name'>{name.replace('_',' ')}</div>"
                f"<div class='flow-status'>{badge}</div></div>"
            )
        html += "</div>"
        flow_ph.markdown(html, unsafe_allow_html=True)

    render_flow({})

    st.write("")
    m1, m2, m3 = st.columns(3)
    result_ph, hash_ph, cloud_ph = st.empty(), st.empty(), st.empty()
    with m1: result_ph.markdown(metric_card("RESULT", "—"), unsafe_allow_html=True)
    with m2: hash_ph.markdown(metric_card("HASH", "—"), unsafe_allow_html=True)
    with m3: cloud_ph.markdown(metric_card("CLOUD FORWARD", "off"), unsafe_allow_html=True)

    st.divider()
    log_ph = st.empty()
    log_lines: list[tuple[str, str]] = []

    def render_log():
        html = "<div class='console'>"
        for text, cls in log_lines:
            color = {"ok": "#00e5a0", "err": "#f85149", "warn": "#d29922", "": "#8b949e"}.get(cls, "#8b949e")
            html += f"<div class='console-line' style='color:{color}'>{text}</div>"
        html += "</div>"
        log_ph.markdown(html, unsafe_allow_html=True)

    log_lines.append(("awaiting scan…", ""))
    render_log()

    if run_btn:
        if not target:
            st.warning("Enter a path to scan.")
        else:
            log_lines.clear()

            def log(msg, cls=""):
                log_lines.append((f"[{time.strftime('%H:%M:%S')}] {msg}", cls))
                render_log()

            log(f"scan started: {Path(target).name}")
            with st.spinner("running pipeline…"):
                try:
                    response = gateway.receive(ScanRequest(target_path=target))
                    statuses = {s["stage"]: s["status"] for s in response.stages}
                    render_flow(statuses)

                    for s in response.stages:
                        cls = {"PASS": "ok", "WARN": "warn", "FAIL": "err", "ERROR": "err"}.get(s["status"], "")
                        log(f"{s['stage']}: {s['message']}", cls)

                    ok = response.overall_status == "PASS"
                    warn = response.overall_status == "WARN"
                    result_ph.markdown(metric_card("RESULT", response.overall_status,
                                                     "ok" if ok else "warn" if warn else "err"), unsafe_allow_html=True)
                    hash_ph.markdown(metric_card("HASH", response.hash_summary or "n/a"), unsafe_allow_html=True)
                    cloud_ph.markdown(metric_card("CLOUD FORWARD", "yes" if response.cloud_forwarded else "skipped"), unsafe_allow_html=True)

                    log(f"cloud forward: {'YES' if response.cloud_forwarded else 'SKIPPED (cloud.enabled=false)'}",
                        "" if response.cloud_forwarded else "warn")
                    log(f"run complete — {response.overall_status} (id:{response.run_id})", "ok" if ok else "err")

                    rows = st.session_state.setdefault("audit_rows", [])
                    rows.insert(0, {"run_id": response.run_id, "target": Path(target).name,
                                     "overall": response.overall_status, "stages": statuses})
                except Exception as exc:
                    log(f"gateway error: {exc}", "err")
                    st.error(str(exc))


# ═══════════════════════════════════════════════════════════════════════════
# PAGE: MODEL INTEGRITY  (poisoned model detection + eject)
# ═══════════════════════════════════════════════════════════════════════════
elif page == "🧬 Model Integrity":
    st.markdown("### Model Integrity Monitor")
    st.caption("Hashes every model in `local.models_dir` against `baselines.json`. Mismatches are flagged POISONED.")

    if st.button("🔄 Scan models directory", type="primary"):
        with st.spinner("hashing model files…"):
            st.session_state.model_scan = gateway.scan_models()

    entries = st.session_state.get("model_scan", [])

    if not entries:
        st.info("No models found, or scan not yet run. Click **Scan models directory**.")
        st.caption(f"Looking in: `{gateway._cfg.get('local', {}).get('models_dir', './data/models')}`")
    else:
        poisoned = [e for e in entries if e["status"] == "POISONED"]
        unverified = [e for e in entries if e["status"] == "UNVERIFIED"]
        trusted = [e for e in entries if e["status"] == "TRUSTED"]

        c1, c2, c3 = st.columns(3)
        with c1: st.markdown(metric_card("TRUSTED", str(len(trusted)), "ok"), unsafe_allow_html=True)
        with c2: st.markdown(metric_card("UNVERIFIED", str(len(unverified)), "warn"), unsafe_allow_html=True)
        with c3: st.markdown(metric_card("POISONED", str(len(poisoned)), "err" if poisoned else ""), unsafe_allow_html=True)

        if poisoned:
            st.error(f"⚠️ {len(poisoned)} model(s) failed integrity verification — hash mismatch vs baseline.")

        st.write("")
        for e in entries:
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 2, 1])
                with c1:
                    st.markdown(f"**{e['name']}**  {pill(e['status'])}", unsafe_allow_html=True)
                    st.caption(f"{e['size_bytes']:,} bytes")
                with c2:
                    st.code(e["current_hash"][:16] + "…", language=None)
                    if e["baseline_hash"]:
                        match = "✅ matches" if e["current_hash"] == e["baseline_hash"] else "❌ MISMATCH"
                        st.caption(f"baseline: {e['baseline_hash'][:16]}… ({match})")
                    else:
                        st.caption("no baseline recorded")
                with c3:
                    if e["status"] in ("POISONED", "UNVERIFIED"):
                        if st.button("🚫 Eject", key=f"eject_{e['name']}", use_container_width=True):
                            if gateway.eject_model(e["name"]):
                                st.success(f"{e['name']} quarantined")
                                st.session_state.model_scan = gateway.scan_models()
                                st.rerun()
                    else:
                        st.caption("✓ verified")

        st.divider()
        with st.expander("📌 Pin a new baseline"):
            st.caption("Records the current hash as trusted (ADR-003: trust is out-of-band, never from cloud).")
            target_model = st.selectbox("model", [e["name"] for e in entries])
            if st.button("Pin current hash as baseline"):
                entry = next(e for e in entries if e["name"] == target_model)
                gateway.set_model_baseline(target_model, entry["current_hash"])
                st.success(f"Baseline pinned for {target_model}")
                st.session_state.model_scan = gateway.scan_models()
                st.rerun()


# ═══════════════════════════════════════════════════════════════════════════
# PAGE: AUDIT LOG
# ═══════════════════════════════════════════════════════════════════════════
elif page == "📋 Audit Log":
    st.markdown("### Audit Log")

    rows = st.session_state.get("audit_rows", [])

    audit_dir = Path(gateway._cfg.get("local", {}).get("audit_dir", "./data/audit"))
    disk_rows = []
    if audit_dir.exists():
        for f in sorted(audit_dir.glob("*.json"), reverse=True)[:20]:
            try:
                disk_rows.append(json.loads(f.read_text()))
            except Exception:
                pass

    if not rows and not disk_rows:
        st.info("No runs yet. Run a scan from **Model Scan** to see results here.")
    else:
        header = st.columns([1, 2, 1, 1, 1, 1, 1])
        for c, label in zip(header, ["run_id", "target", "integrity", "threat", "privacy", "audit", "overall"]):
            c.caption(f"**{label}**")

        for row in (rows + disk_rows)[:20]:
            if "stages" in row and isinstance(row["stages"], list):
                stages_map = {s["stage"]: s["status"] for s in row["stages"]}
                target = row.get("target_name", row.get("target", "—"))
                overall = row.get("overall_status", "—")
                run_id = row.get("run_id", "—")
            else:
                stages_map = row.get("stages", {})
                target = row.get("target", "—")
                overall = row.get("overall", "—")
                run_id = row.get("run_id", "—")

            cols = st.columns([1, 2, 1, 1, 1, 1, 1])
            cols[0].code(run_id, language=None)
            cols[1].caption(target)
            for i, stage in enumerate(["integrity", "threat_scanner", "privacy", "audit"]):
                cols[2 + i].markdown(pill(stages_map.get(stage, "—")), unsafe_allow_html=True)
            cols[6].markdown(pill(overall), unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════
# PAGE: CONFIG
# ═══════════════════════════════════════════════════════════════════════════
elif page == "⚙️ Config":
    st.markdown("### Configuration")
    st.caption("Read from `config/default.yaml` + `config/local.yaml`")

    cfg = gateway._cfg
    rows = [
        ("cloud.enabled", str(cfg.get("cloud", {}).get("enabled", False))),
        ("pipeline.order", " → ".join(cfg.get("pipeline", {}).get("order", []))),
        ("local.chunk_size_bytes", f"{cfg.get('local', {}).get('chunk_size_bytes', 0):,}"),
        ("local.models_dir", cfg.get("local", {}).get("models_dir", "")),
        ("local.audit_dir", cfg.get("local", {}).get("audit_dir", "")),
        ("privacy.enabled", str(cfg.get("privacy", {}).get("enabled", True))),
        ("local_ai.base_url", cfg.get("local_ai", {}).get("base_url", "")),
        ("local_ai.model", cfg.get("local_ai", {}).get("model", "") or "(auto)"),
        ("app.log_level", cfg.get("app", {}).get("log_level", "INFO")),
    ]

    for key, val in rows:
        c1, c2 = st.columns([2, 3])
        c1.markdown(f"`{key}`")
        c2.code(val, language=None)

    st.divider()
    st.caption("Edit `config/default.yaml` or `config/local.yaml` and restart to apply changes.")
    st.caption("Cloud is disabled by default — nothing leaves this machine unless `cloud.enabled: true`.")
