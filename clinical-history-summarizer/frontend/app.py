"""
Streamlit Demo UI — Clinical History Summarizer
Stage 8.1

Side-by-side view:
  LEFT  — original notes with line numbers so the audience can see
           exactly what source text was available
  RIGHT — structured summary: each field shows its citation (line + quote)
           if verified, or a red UNVERIFIED badge if the citation was
           missing or invalid

Run:
    cd clinical-history-summarizer
    streamlit run frontend/app.py
"""

import json
import os
import pathlib

import requests
import streamlit as st

# ── Config ─────────────────────────────────────────────────────────────────────
API_BASE = os.environ.get("API_URL", "http://localhost:8000")
REPORTS_PATH = pathlib.Path(__file__).parent.parent / "reports" / "evaluation_report.json"

# ── Page setup ─────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Clinical History Summarizer",
    page_icon="🏥",
    layout="wide",
)

# ── Styling ────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Unverified badge — bright red, hard to miss */
.badge-unverified {
    background: #e53935;
    color: #fff;
    font-size: 0.72em;
    font-weight: 700;
    padding: 2px 7px;
    border-radius: 4px;
    letter-spacing: 0.04em;
    vertical-align: middle;
    margin-left: 6px;
}

/* Verified citation pill */
.cite {
    font-size: 0.72em;
    color: #5c9ec7;
    font-style: italic;
    margin-left: 5px;
    vertical-align: middle;
}

/* Line-numbered notes block */
.notes-block {
    font-family: 'Courier New', monospace;
    font-size: 0.82em;
    white-space: pre-wrap;
    background: #0e1117;
    color: #d0d0d0;
    padding: 14px 16px;
    border-radius: 6px;
    line-height: 1.65;
    overflow-y: auto;
    max-height: 680px;
}
.ln  { color: #555; user-select: none; }                   /* line number  */
.ln-hi { color: #f9a825; font-weight: bold; }              /* cited line   */

/* Section headings in summary */
.sec { font-size: 0.78em; font-weight: 700; color: #9e9e9e;
       letter-spacing: 0.08em; text-transform: uppercase;
       margin: 14px 0 4px; }

/* Individual fact rows */
.fact { padding: 5px 0; border-bottom: 1px solid #1e2a35; }
.fact:last-child { border-bottom: none; }

.stats-box {
    background: #131c27;
    border: 1px solid #1e3050;
    border-radius: 8px;
    padding: 12px 18px;
    margin-bottom: 10px;
}
</style>
""", unsafe_allow_html=True)


# ── Helpers ─────────────────────────────────────────────────────────────────────

def badge_unverified() -> str:
    return '<span class="badge-unverified">⚠ UNVERIFIED</span>'


def cite_span(source: dict | None) -> str:
    """Render a small blue citation pill if source is valid."""
    if not source:
        return ""
    line = source.get("line_number", "?")
    text = source.get("quoted_text", "")
    # Truncate long quoted texts for display
    display = text if len(text) <= 55 else text[:52] + "…"
    return f'<span class="cite">→ L{line}: "{display}"</span>'


def section(label: str) -> str:
    return f'<div class="sec">{label}</div>'


def fact_row(content: str) -> str:
    return f'<div class="fact">{content}</div>'


def render_notes_with_highlights(raw_notes: str, cited_lines: set[int]) -> str:
    """
    Render the raw notes as a monospace block where cited lines are
    highlighted in amber so the audience can immediately see which lines
    were used as sources.
    """
    lines = raw_notes.splitlines()
    html_lines = []
    for i, line in enumerate(lines, 1):
        ln_class = "ln-hi" if i in cited_lines else "ln"
        # Escape HTML special chars
        safe_line = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        html_lines.append(
            f'<span class="{ln_class}">L{i:>3}</span>  {safe_line}'
        )
    return '<div class="notes-block">' + "\n".join(html_lines) + "</div>"


def collect_cited_lines(summary: dict) -> set[int]:
    """Walk the summary dict and collect all referenced line numbers."""
    lines = set()

    def _extract_ln(obj):
        if isinstance(obj, dict):
            if "line_number" in obj:
                lines.add(obj["line_number"])
            for v in obj.values():
                _extract_ln(v)
        elif isinstance(obj, list):
            for item in obj:
                _extract_ln(item)

    _extract_ln(summary)
    return lines


# ── Example note (case 6 — the deliberately ambiguous ACS case) ─────────────
EXAMPLE_NOTE = """\
# SYNTHETIC DATA — NOT A REAL PATIENT

Pt: E9 / DOB ~1958 / seen 8/10/24

CC - chest pain, onset last night around 10pm. Described as pressure,
7/10, radiates L arm. Had similar episode 6mo ago that "went away on its own".
Diaphoresis present. No syncope.

Pmhx: T2DM (on meds), HTN, ex-smoker (quit ~10yrs ago)

Meds (from patient — not verified against GP records):
metformin - not sure of dose, says "the small ones twice a day"
ramipril 5mg od
amlodipine - patient says 5 or 10mg, not certain

Allergies: says he had a bad reaction to "an antibiotic" years ago
but cannot recall which one or what happened. Nothing in the notes
brought today.

Ix:
Trop I: 0.06 (lab ref <0.04) — HIGH — taken at 03:15
ECG: ST depression V3-V5 (done on arrival)

Plan:
- ACS protocol started
- repeat trop at 0h+3 pending
- cardiology to review
"""


# ── Sidebar ─────────────────────────────────────────────────────────────────────
# ── Settings sidebar ──────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Settings")

    patient_id = st.text_input("Patient ID", value="case_demo")

    mode = st.radio(
        "Output mode",
        options=["clinical", "patient"],
        format_func=lambda m: "🩺 Clinical (default)" if m == "clinical" else "👤 Patient-friendly",
        help=(
            "Clinical: structured JSON with citations for clinical staff.\n"
            "Patient: adds a plain-language summary omitting unverified fields."
        ),
    )

    st.divider()
    st.markdown("**API**")
    try:
        r = requests.get(f"{API_BASE}/health", timeout=3)
        if r.status_code == 200:
            st.success("Backend connected ✓")
        else:
            st.warning(f"Backend returned HTTP {r.status_code}")
    except Exception:
        st.error(f"Backend unreachable at {API_BASE}")

    # ── Evaluation report ─────────────────────────────────────────────────────
    st.divider()
    st.markdown("**Evaluation Results**")
    if REPORTS_PATH.exists():
        try:
            report = json.loads(REPORTS_PATH.read_text())
            for k, v in report.items():
                if isinstance(v, float):
                    st.metric(k.replace("_", " ").title(), f"{v:.1%}")
                elif isinstance(v, (int, str)):
                    st.metric(k.replace("_", " ").title(), v)
        except Exception as e:
            st.caption(f"Could not load report: {e}")
    else:
        st.caption("No evaluation_report.json found yet.")
        st.caption("Run `scripts/evaluate.py` first.")


# ── Header ──────────────────────────────────────────────────────────────────────
st.title("🏥 Clinical History Summarizer")
st.caption(
    "Paste multi-source clinical notes. The AI extracts a structured summary and **cites "
    "every claim back to a specific line** in the original text. Fields it cannot trace "
    "are **flagged red** — never silently presented as fact."
)

# ── Input area ─────────────────────────────────────────────────────────────────
notes_input = st.text_area(
    "Paste clinical notes here",
    value=EXAMPLE_NOTE,
    height=280,
    placeholder="Paste admission notes, lab reports, medication lists…",
)

btn_col, _ = st.columns([1, 3])
with btn_col:
    extract_btn = st.button("🔍 Generate Summary", type="primary", use_container_width=True)


# ── Extraction ──────────────────────────────────────────────────────────────────
if extract_btn:
    if not notes_input.strip():
        st.error("Please paste some clinical notes first.")
        st.stop()

    with st.spinner("Extracting and verifying… (this takes ~10 seconds)"):
        try:
            resp = requests.post(
                f"{API_BASE}/extract",
                json={"patient_id": patient_id, "raw_notes": notes_input},
                params={"mode": mode},
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.HTTPError as e:
            st.error(f"API error {e.response.status_code}: {e.response.text[:300]}")
            st.stop()
        except Exception as e:
            st.error(f"Connection error: {e}")
            st.stop()

    summary: dict = data["summary"]
    stats: dict = data["summary_stats"]
    unverified: set = set(summary.get("unverified_fields", []))
    cited_lines = collect_cited_lines(summary)

    # ── Stats banner ────────────────────────────────────────────────────────────
    total = stats["total_fields_extracted"]
    verified = stats["verified_count"]
    unverif  = stats["unverified_count"]
    missing_ct = stats.get("missing_count", 0)
    pct = int(100 * verified / total) if total else 0
    color = "#2e7d32" if pct >= 80 else "#f57c00" if pct >= 50 else "#c62828"

    st.markdown(
        f'<div class="stats-box">'
        f'<b style="font-size:1.05em">Extraction complete</b> &nbsp;|&nbsp; '
        f'<b style="color:{color}">{verified}/{total} fields verified ({pct}%)</b>'
        f'{f" &nbsp;|&nbsp; <b style=\'color:#e53935\'>{unverif} unverified</b>" if unverif else ""}'
        f'{f" &nbsp;|&nbsp; <b style=\'color:#fb8c00\'>{missing_ct} not mentioned</b>" if missing_ct else ""}'
        f'&nbsp;|&nbsp; Stored as summary #{data["stored_summary_id"]}'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── Missing fields banner ───────────────────────────────────────────────────
    missing_fields = summary.get("missing_fields", [])
    if missing_fields:
        readable = ", ".join(
            f.replace("_", " ").title() for f in missing_fields
        )
        st.info(
            f"ℹ️ **This note didn't mention:** {readable}.  "
            f"Consider asking the patient directly or checking other records."
        )

    # ── Patient-friendly summary panel ─────────────────────────────────────────
    if data.get("patient_friendly_summary"):
        with st.expander("👤 Patient-friendly summary (plain language)", expanded=True):
            st.markdown(
                f'<div style="background:#0d2137; border-left: 4px solid #42a5f5; '
                f'padding: 14px 18px; border-radius: 6px; font-size: 0.97em; line-height: 1.7">'
                f'{data["patient_friendly_summary"]}'
                f'</div>',
                unsafe_allow_html=True,
            )
            st.caption(
                "⚠️ This is an AI-generated plain-language summary for the patient. "
                "It contains only fields that were independently verified against "
                "the source notes. Unverified fields are omitted. "
                "This is NOT medical advice."
            )

    # ── Two-column layout ───────────────────────────────────────────────────────
    left_col, right_col = st.columns([1, 1], gap="large")

    # ── LEFT: Original notes with highlighted cited lines ──────────────────────
    with left_col:
        st.subheader("📄 Original Notes")
        if cited_lines:
            st.caption(f"Lines highlighted in amber were cited as sources ({len(cited_lines)} lines used)")
        st.markdown(
            render_notes_with_highlights(notes_input, cited_lines),
            unsafe_allow_html=True,
        )

    # ── RIGHT: Structured summary ───────────────────────────────────────────────
    with right_col:
        st.subheader("✅ Structured Summary")

        html = []

        # ── Chief Complaint ──────────────────────────────────────────────────
        html.append(section("Chief Complaint"))
        cc = summary.get("chief_complaint")
        src = summary.get("chief_complaint_source")
        if cc:
            is_unverified = "chief_complaint" in unverified
            row = f"<b>{cc}</b>"
            if is_unverified:
                row += badge_unverified()
            else:
                row += cite_span(src)
            html.append(fact_row(row))
        else:
            html.append(fact_row('<i style="color:#666">Not found in notes</i>'))

        # ── Active Problems ──────────────────────────────────────────────────
        html.append(section("Active Problems"))
        problems = summary.get("active_problems", [])
        sources  = summary.get("active_problems_sources", [])
        if problems:
            for i, prob in enumerate(problems):
                key = f"active_problems[{i}]"
                is_unv = key in unverified
                src_obj = sources[i] if i < len(sources) else None
                row = f"• {prob}"
                row += badge_unverified() if is_unv else cite_span(src_obj)
                html.append(fact_row(row))
        else:
            html.append(fact_row('<i style="color:#666">None found</i>'))

        # ── Current Medications ──────────────────────────────────────────────
        html.append(section("🚨 Current Medications"))
        meds = summary.get("current_medications", [])
        if meds:
            for i, med in enumerate(meds):
                key = f"current_medications[{i}]"
                is_unv = key in unverified
                detail_parts = [med.get("dose"), med.get("timing")]
                detail = " — " + " ".join(p for p in detail_parts if p) if any(detail_parts) else ""
                row = f"• <b>{med['name']}</b>{detail}"
                row += badge_unverified() if is_unv else cite_span(med.get("source"))
                html.append(fact_row(row))
        else:
            html.append(fact_row('<i style="color:#666">None documented</i>'))

        # ── Allergies ────────────────────────────────────────────────────────
        html.append(section("⚠ Allergies"))
        allergies = summary.get("allergies", [])
        allergy_sources = summary.get("allergies_sources", [])
        if allergies:
            for i, al in enumerate(allergies):
                key = f"allergies[{i}]"
                is_unv = key in unverified
                src_obj = allergy_sources[i] if i < len(allergy_sources) else None
                row = f"• <b>{al}</b>"
                row += badge_unverified() if is_unv else cite_span(src_obj)
                html.append(fact_row(row))
        else:
            html.append(fact_row('<i style="color:#4caf50">✓ No known allergies documented</i>'))

        # ── Recent Labs ──────────────────────────────────────────────────────
        html.append(section("Recent Labs / Investigations"))
        labs = summary.get("recent_labs", [])
        if labs:
            for i, lab in enumerate(labs):
                key = f"recent_labs[{i}]"
                is_unv = key in unverified
                value_str = lab.get("value") or "—"
                date_str  = f" &nbsp;<small>({lab['date']})</small>" if lab.get("date") else ""
                row = f"• <b>{lab['test_name']}</b>: {value_str}{date_str}"
                row += badge_unverified() if is_unv else cite_span(lab.get("source"))
                html.append(fact_row(row))
        else:
            html.append(fact_row('<i style="color:#666">None documented</i>'))

        # ── Pending Items ────────────────────────────────────────────────────
        html.append(section("Pending / Follow-up"))
        pending = summary.get("pending_items", [])
        if pending:
            for item in pending:
                html.append(fact_row(f"• {item}"))
        else:
            html.append(fact_row('<i style="color:#666">None</i>'))

        # ── Unverified fields summary box ────────────────────────────────────
        if unverified:
            html.append("<hr style='border-color:#3a1a1a; margin:16px 0 8px'>")
            html.append(
                '<div style="background:#2a1010; border:1px solid #7b2020; '
                'border-radius:6px; padding:10px 14px; margin-top:8px;">'
                '<b style="color:#e53935">⚠ Unverified fields</b> '
                '<span style="color:#bbb; font-size:0.85em">— '
                'could not be traced to a specific source line. '
                'Do not act on these without independent verification.</span><br>'
            )
            for f in sorted(unverified):
                html.append(f'&nbsp;&nbsp;• <code>{f}</code><br>')
            html.append("</div>")

        st.markdown("\n".join(html), unsafe_allow_html=True)

    # ── Raw JSON expander ───────────────────────────────────────────────────────
    with st.expander("🔧 Raw API Response (for debugging)"):
        st.json(data)
