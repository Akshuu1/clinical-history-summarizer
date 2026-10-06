"""
Streamlit Demo UI — Clinical History Summarizer

Side-by-side view:
  LEFT  — original normalised notes with line numbers
  RIGHT — structured clinical summary with source citations and unverified flags

Run:
  streamlit run frontend/app.py
"""

import json
import os
import sys

import streamlit as st
import httpx

# Allow importing project modules if run from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

API_URL = os.environ.get("API_URL", "http://localhost:8000/api/v1")

st.set_page_config(
    page_title="Clinical History Summarizer",
    page_icon="🏥",
    layout="wide",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.unverified-badge {
    background-color: #FF4B4B;
    color: white;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.75em;
    font-weight: bold;
    margin-left: 6px;
}
.source-cite {
    font-size: 0.75em;
    color: #888;
    font-style: italic;
    margin-left: 6px;
}
.line-number {
    color: #888;
    font-size: 0.8em;
    min-width: 40px;
    display: inline-block;
}
.med-item { padding: 4px 0; }
</style>
""", unsafe_allow_html=True)

# ── Header ─────────────────────────────────────────────────────────────────────
st.title("🏥 Clinical History Summarizer")
st.caption(
    "Paste multi-source clinical notes below. The AI extracts a structured summary "
    "and cites every claim back to a specific line in the original text. "
    "Unverified fields are flagged — never silently presented as fact."
)

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Settings")
    patient_id = st.text_input("Patient ID", value="DEMO-001")
    source_label = st.selectbox(
        "Note type",
        ["general", "ED admission", "ward round", "lab report", "discharge summary"],
    )
    st.divider()
    st.markdown("**API Status**")
    try:
        resp = httpx.get(f"{API_URL}/health", timeout=3)
        if resp.status_code == 200:
            st.success("Backend connected ✓")
        else:
            st.warning(f"Backend returned {resp.status_code}")
    except Exception:
        st.error("Backend not reachable — start uvicorn")

# ── Main input ─────────────────────────────────────────────────────────────────
EXAMPLE_NOTE = """Patient: DEMO-001 | DOB: 1972-05-10 | MRN: DM0001
Date: 2024-10-01 | Ward: Medical

CHIEF COMPLAINT:
Patient presents with 3-day history of worsening shortness of breath and bilateral leg swelling.

ALLERGIES:
- Penicillin: hives and angioedema
- Contrast dye: anaphylactoid reaction (2022)

CURRENT MEDICATIONS:
- Furosemide 40mg oral once daily
- Carvedilol 6.25mg oral twice daily
- Spironolactone 25mg oral once daily
- Lisinopril 5mg oral once daily

ACTIVE PROBLEMS:
1. Decompensated heart failure (EF 30% — echo 2024-08-15)
2. Hypertension
3. Chronic kidney disease Stage 3a

RECENT LABS (2024-10-01):
- BNP: 980 pg/mL (HIGH)
- Creatinine: 165 umol/L (HIGH)
- K: 5.2 mmol/L (borderline high)
- Na: 136 mmol/L
- Chest X-ray: Cardiomegaly, bilateral pleural effusions

PENDING:
- Echocardiogram repeat
- Cardiology review
- Nephrology input re: worsening renal function
"""

notes_input = st.text_area(
    "Paste clinical notes here",
    value=EXAMPLE_NOTE,
    height=320,
    placeholder="Paste admission notes, lab reports, medication lists...",
)

extract_btn = st.button("🔍 Extract Summary", type="primary", use_container_width=True)

# ── Results ────────────────────────────────────────────────────────────────────
if extract_btn:
    if not notes_input.strip():
        st.error("Please enter some clinical notes first.")
    else:
        with st.spinner("Extracting and verifying clinical summary..."):
            try:
                response = httpx.post(
                    f"{API_URL}/extract",
                    json={
                        "patient_id": patient_id,
                        "notes": notes_input,
                        "source_label": source_label,
                    },
                    timeout=60,
                )
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPStatusError as e:
                st.error(f"API error {e.response.status_code}: {e.response.text}")
                st.stop()
            except Exception as e:
                st.error(f"Connection error: {e}")
                st.stop()

        summary = data["summary"]
        raw_lines = data["raw_normalised_lines"]
        warnings = data.get("warnings", [])
        unverified = set(summary.get("unverified_fields", []))

        # Warnings
        for w in warnings:
            st.warning(w)

        # ── Side-by-side layout ────────────────────────────────────────────────
        left_col, right_col = st.columns([1, 1], gap="large")

        # LEFT: Original notes
        with left_col:
            st.subheader("📄 Original Notes (line-numbered)")
            lines_display = []
            for i, line in enumerate(raw_lines, start=1):
                lines_display.append(f"L{i:>3}: {line}")
            st.code("\n".join(lines_display), language=None)

        # RIGHT: Structured summary
        with right_col:
            st.subheader("✅ Verified Clinical Summary")

            def cite(item):
                return (
                    f'<span class="source-cite">→ L{item["source_line"]}: '
                    f'"{item["source_text"]}"</span>'
                )

            def unverified_badge():
                return '<span class="unverified-badge">⚠ UNVERIFIED</span>'

            # Chief Complaint
            st.markdown("**Chief Complaint**")
            cc = summary.get("chief_complaint")
            if cc:
                st.markdown(
                    f'{cc["value"]} {cite(cc)}',
                    unsafe_allow_html=True,
                )
            elif "chief_complaint" in unverified:
                st.markdown(
                    f"Not verifiable {unverified_badge()}",
                    unsafe_allow_html=True,
                )
            else:
                st.caption("Not found in notes")

            # Allergies
            st.markdown("**🚨 Allergies**")
            if "allergies" in unverified and not summary.get("allergies"):
                st.markdown(
                    f"Citation failed {unverified_badge()}",
                    unsafe_allow_html=True,
                )
            elif summary.get("allergies"):
                for a in summary["allergies"]:
                    reaction = f" — {a['reaction']}" if a.get("reaction") else ""
                    st.markdown(
                        f"• **{a['substance']}**{reaction} {cite(a)}",
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("None documented")

            # Active Problems
            st.markdown("**🩺 Active Problems**")
            for p in summary.get("active_problems", []):
                st.markdown(f"• {p['value']} {cite(p)}", unsafe_allow_html=True)
            if not summary.get("active_problems"):
                st.caption("None found")

            # Current Medications
            st.markdown("**💊 Current Medications**")
            if "current_medications" in unverified and not summary.get("current_medications"):
                st.markdown(
                    f"Citation failed {unverified_badge()}",
                    unsafe_allow_html=True,
                )
            for m in summary.get("current_medications", []):
                dose = m.get("dose", "")
                freq = m.get("frequency", "")
                route = m.get("route", "")
                detail = " ".join(filter(None, [dose, freq, route]))
                st.markdown(
                    f'<div class="med-item">• <b>{m["name"]}</b>'
                    f'{" — " + detail if detail else ""} {cite(m)}</div>',
                    unsafe_allow_html=True,
                )

            # Recent Labs
            st.markdown("**🔬 Recent Labs**")
            for lab in summary.get("recent_labs", []):
                flag = f" [{lab['flag']}]" if lab.get("flag") else ""
                unit = f" {lab['unit']}" if lab.get("unit") else ""
                date = f" ({lab['date']})" if lab.get("date") else ""
                color = "red" if lab.get("flag") in ("HIGH", "LOW", "CRITICAL") else "inherit"
                st.markdown(
                    f'• {lab["test"]}: <span style="color:{color}"><b>{lab["result"]}'
                    f'{unit}{flag}</b></span>{date} {cite(lab)}',
                    unsafe_allow_html=True,
                )

            # Pending Items
            st.markdown("**📋 Pending Items**")
            for item in summary.get("pending_items", []):
                st.markdown(f"• {item['value']} {cite(item)}", unsafe_allow_html=True)

            # Unverified fields summary
            if unverified:
                st.divider()
                st.markdown("**⚠️ Fields with citation failures (treat as unconfirmed)**")
                for f in unverified:
                    st.markdown(f"• `{f}`")

        # Raw JSON expander
        with st.expander("🔧 Raw API Response (JSON)"):
            st.json(data)
