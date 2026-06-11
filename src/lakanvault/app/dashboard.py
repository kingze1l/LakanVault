"""LakanVault dashboard — Streamlit UI shell.
Per ADR-004: this file only renders. All logic lives in Gateway.
No imports from local_core or cloud_intelligence here.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import streamlit as st

from lakanvault.contracts.dtos import ScanRequest
from lakanvault.orchestration.gateway import Gateway

logging.basicConfig(level=logging.INFO)

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="LakanVault",
    page_icon="🔒",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Inject custom CSS (monospace, security-tool aesthetic) ────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&display=swap');

html, body, [class*="css"] { font-family: 'JetBrains Mono', monospace; }
.block-container { padding-top: 1.5rem; max-width: 1100px; }
.stage-pill {
    display: inline-block; padding: 3px 12px; border-radius: 12px;
    font-size: 11px; font-weight: 500; margin: 2px;
}
.PASS  { background: #d4edda; color: #155724; }
.WARN  { background: #fff3cd; color: #856404; }
.FAIL  { background: #f8d7da; color: #721c24; }
.ERROR { background: #f8d7da; color: #721c24; }
.SKIPPED { background: #e2e3e5; color: #383d41; }
.metric-box {
    background: #f8f9fa; border: 1px solid #dee2e6;
    border-radius: 8px; padding: 12px 16px; text-align: center;
}
.metric-label { font-size: 10px; color: #6c757d; letter-spacing: .06em; }
.metric-val   { font-size: 22px; font-weight: 500; margin-top: 4px; }
.ok  { color: #198754; }
.err { color: #dc3545; }
.warn-col { color: #d39e00; }
</style>
""", unsafe_allow_html=True)


# ── Gateway (cached so we don't reload config on every rerun) ─────────────────
@st.cache_resource
def get_gateway() -> Gateway:
    config_dir = Path(__file__).parents[4] / "config"
    if not config_dir.exists():
        config_dir = Path("./config")
    return Gateway(config_dir=config_dir)


# ── Sidebar navigation ────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔒 LAKANVAULT")
    st.caption("v0.1.0 · air-gapped")
    st.divider()
    page = st.radio(
        "navigate",
        ["scan", "audit log", "config"],
        label_visibility="collapsed",
    )
    st.divider()
    cfg = get_gateway()._cfg
    cloud_on = cfg.get("cloud", {}).get("enabled", False)
    st.markdown(
        f"**cloud** {'🟢 on' if cloud_on else '🔴 off'}",
        help="Change in config/default.yaml → cloud.enabled",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: SCAN
# ═══════════════════════════════════════════════════════════════════════════════
if page == "scan":
    st.markdown("#### pipeline scan")

    col1, col2 = st.columns([3, 1])
    with col1:
        target = st.text_input(
            "model / file path",
            placeholder="./data/models/llama-3-8b.gguf",
            label_visibility="collapsed",
        )
    with col2:
        run_btn = st.button("▶ run scan", use_container_width=True, type="primary")

    prompt_text = st.text_area(
        "prompt text (optional — scanned for PII)",
        height=80,
        placeholder="Paste a prompt here to test privacy scanning…",
        label_visibility="visible",
    )

    st.divider()

    # Pipeline stage indicator
    stage_names = ["integrity", "threat_scanner", "privacy", "audit"]
    stage_cols = st.columns(len(stage_names))
    stage_placeholders = {}
    for i, name in enumerate(stage_names):
        with stage_cols[i]:
            stage_placeholders[name] = st.empty()
            stage_placeholders[name].markdown(
                f"<div style='text-align:center'>"
                f"<div style='font-size:10px;color:#6c757d;letter-spacing:.06em'>"
                f"{name.upper().replace('_',' ')}</div>"
                f"<div style='font-size:11px;color:#adb5bd'>—</div></div>",
                unsafe_allow_html=True,
            )

    st.divider()

    # Metric row
    m1, m2, m3, m4 = st.columns(4)
    result_ph  = m1.empty()
    pii_ph     = m2.empty()
    hash_ph    = m3.empty()
    cloud_ph   = m4.empty()

    def render_metric(ph, label, val, cls=""):
        ph.markdown(
            f"<div class='metric-box'>"
            f"<div class='metric-label'>{label}</div>"
            f"<div class='metric-val {cls}'>{val}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    render_metric(result_ph, "LAST RESULT", "—")
    render_metric(pii_ph,    "PII SPANS",   "—")
    render_metric(hash_ph,   "HASH",        "—")
    render_metric(cloud_ph,  "CLOUD",       "off")

    st.divider()
    log_ph = st.empty()

    def render_log(lines: list[tuple[str, str]]):
        """lines: list of (text, css_class) tuples."""
        html = "<div style='background:#1e1e1e;border-radius:8px;padding:12px 16px;font-size:11px;min-height:100px;max-height:200px;overflow-y:auto'>"
        for text, cls in lines:
            color = {"ok": "#4ec9b0", "err": "#f44747", "warn": "#dcdcaa", "": "#d4d4d4"}.get(cls, "#d4d4d4")
            html += f"<div style='color:{color};margin-bottom:2px'>{text}</div>"
        html += "</div>"
        log_ph.markdown(html, unsafe_allow_html=True)

    render_log([("awaiting scan…", "")])

    # ── Run ──────────────────────────────────────────────────────────────────
    if run_btn:
        if not target:
            st.warning("Enter a file path to scan.")
        else:
            log_lines: list[tuple[str, str]] = []

            def log(msg, cls=""):
                import time
                ts = time.strftime("%H:%M:%S")
                log_lines.append((f"[{ts}] {msg}", cls))
                render_log(log_lines)

            def update_stage(name, status, label):
                cls_map = {"PASS": "PASS", "WARN": "WARN", "FAIL": "FAIL",
                           "ERROR": "FAIL", "running": "", "—": ""}
                css = cls_map.get(status, "")
                stage_placeholders[name].markdown(
                    f"<div style='text-align:center'>"
                    f"<div style='font-size:10px;color:#6c757d;letter-spacing:.06em'>"
                    f"{name.upper().replace('_',' ')}</div>"
                    f"<span class='stage-pill {css}'>{label}</span></div>",
                    unsafe_allow_html=True,
                )

            log(f"scan started: {Path(target).name}")
            for sn in stage_names:
                update_stage(sn, "—", "—")

            with st.spinner("running pipeline…"):
                try:
                    request = ScanRequest(target_path=target, prompt_text=prompt_text)
                    gateway = get_gateway()
                    response = gateway.receive(request)

                    # Update stages from response
                    for sr in response.stages:
                        update_stage(sr["stage"], sr["status"], sr["status"])
                        cls = {"PASS": "ok", "WARN": "warn", "FAIL": "err", "ERROR": "err"}.get(sr["status"], "")
                        log(f"{sr['stage']}: {sr['message']}", cls)

                    # Metrics
                    ok = response.overall_status == "PASS"
                    warn = response.overall_status == "WARN"
                    render_metric(
                        result_ph, "LAST RESULT", response.overall_status,
                        "ok" if ok else ("warn-col" if warn else "err"),
                    )
                    render_metric(pii_ph, "PII SPANS", str(response.pii_span_count),
                                  "warn-col" if response.pii_span_count > 0 else "ok")
                    render_metric(hash_ph, "HASH", response.hash_summary or "n/a")
                    render_metric(cloud_ph, "CLOUD",
                                  "forwarded" if response.cloud_forwarded else "off",
                                  "" if response.cloud_forwarded else "")

                    log(
                        f"cloud forward: {'YES' if response.cloud_forwarded else 'SKIPPED (cloud.enabled=false)'}",
                        "" if response.cloud_forwarded else "warn",
                    )
                    log(f"run complete — {response.overall_status} (id:{response.run_id})",
                        "ok" if ok else "err")

                    # Stash in session for audit tab
                    if "audit_rows" not in st.session_state:
                        st.session_state.audit_rows = []
                    st.session_state.audit_rows.insert(0, {
                        "run_id": response.run_id,
                        "target": Path(target).name,
                        "overall": response.overall_status,
                        "stages": {s["stage"]: s["status"] for s in response.stages},
                    })

                except Exception as exc:
                    log(f"gateway error: {exc}", "err")
                    st.error(f"Pipeline error: {exc}")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: AUDIT LOG
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "audit log":
    st.markdown("#### audit log")

    rows = st.session_state.get("audit_rows", [])

    # Also load from disk
    audit_dir = Path("./data/audit")
    disk_rows = []
    if audit_dir.exists():
        for f in sorted(audit_dir.glob("*.json"), reverse=True)[:20]:
            try:
                data = json.loads(f.read_text())
                disk_rows.append(data)
            except Exception:
                pass

    if not rows and not disk_rows:
        st.info("No runs yet. Run a scan to see results here.")
    else:
        all_rows = rows + disk_rows

        def pill(status):
            return f"<span class='stage-pill {status}'>{status}</span>"

        for row in all_rows[:20]:
            if "stages" in row and isinstance(row["stages"], list):
                # Disk format
                stages_map = {s["stage"]: s["status"] for s in row["stages"]}
                target = row.get("target_name", row.get("target", "—"))
                overall = row.get("overall_status", "—")
                run_id = row.get("run_id", "—")
            else:
                # Session format
                stages_map = row.get("stages", {})
                target = row.get("target", "—")
                overall = row.get("overall", "—")
                run_id = row.get("run_id", "—")

            cols = st.columns([1, 2, 1, 1, 1, 1, 1])
            cols[0].caption(run_id)
            cols[1].caption(target)
            cols[2].markdown(pill(stages_map.get("integrity", "—")), unsafe_allow_html=True)
            cols[3].markdown(pill(stages_map.get("threat_scanner", "—")), unsafe_allow_html=True)
            cols[4].markdown(pill(stages_map.get("privacy", "—")), unsafe_allow_html=True)
            cols[5].markdown(pill(stages_map.get("audit", "—")), unsafe_allow_html=True)
            cols[6].markdown(pill(overall), unsafe_allow_html=True)

        st.caption("columns: run_id · target · integrity · threat · privacy · audit · overall")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: CONFIG
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "config":
    st.markdown("#### config — default.yaml")
    cfg = get_gateway()._cfg

    rows = [
        ("cloud.enabled",         str(cfg.get("cloud", {}).get("enabled", False))),
        ("pipeline.order",        " → ".join(cfg.get("pipeline", {}).get("order", []))),
        ("local.chunk_size_bytes", f"{cfg.get('local', {}).get('chunk_size_bytes', 0):,}"),
        ("local.models_dir",       cfg.get("local", {}).get("models_dir", "")),
        ("local.audit_dir",        cfg.get("local", {}).get("audit_dir", "")),
        ("privacy.enabled",        str(cfg.get("privacy", {}).get("enabled", True))),
        ("app.log_level",          cfg.get("app", {}).get("log_level", "INFO")),
    ]

    for key, val in rows:
        c1, c2 = st.columns([2, 3])
        c1.markdown(f"`{key}`")
        c2.code(val, language=None)

    st.divider()
    st.caption("Edit `config/default.yaml` or `config/local.yaml` and restart the app to apply changes.")
    st.caption("Cloud is disabled by default — nothing leaves this machine unless you set `cloud.enabled: true`.")
