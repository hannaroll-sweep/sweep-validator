import streamlit as st
import anthropic
import base64
import re
import time
from datetime import datetime
from pathlib import Path
import gspread
from google.oauth2.service_account import Credentials

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Brief Validator — Sweep",
    page_icon="https://wearesweep.com/favicon.ico",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── Brand styles (inspired by Sweep SoMe deck) ────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Space Grotesk', sans-serif;
        background-color: #180008;
        color: #ffffff;
    }
    #MainMenu {visibility: hidden;}
    footer     {visibility: hidden;}
    header     {visibility: hidden;}

    .block-container {
        max-width: 820px;
        padding-top: 4rem;
        padding-bottom: 4rem;
    }

    /* ── Wordmark top ── */
    .sweep-wordmark {
        font-family: 'Space Grotesk', sans-serif;
        font-size: 0.7rem;
        font-weight: 700;
        letter-spacing: 0.25em;
        text-transform: uppercase;
        color: #CC99FF;
        margin-bottom: 3rem;
    }

    /* ── Giant headline ── */
    .sweep-headline {
        font-family: 'Space Grotesk', sans-serif;
        font-size: 5.5rem;
        font-weight: 700;
        color: #33FF66;
        line-height: 0.95;
        margin-bottom: 1.5rem;
        letter-spacing: -0.03em;
    }

    /* ── Subline ── */
    .sweep-subline {
        font-family: 'Space Grotesk', sans-serif;
        font-size: 1rem;
        color: rgba(255,255,255,0.6);
        margin-bottom: 3rem;
        line-height: 1.65;
        max-width: 520px;
    }

    /* ── Section label ── */
    .sweep-label {
        font-family: 'Space Grotesk', sans-serif;
        font-size: 0.65rem;
        font-weight: 700;
        letter-spacing: 0.22em;
        text-transform: uppercase;
        color: #CC99FF;
        margin-bottom: 0.6rem;
    }

    /* ── File uploader ── */
    [data-testid="stFileUploader"] {
        border: 1px solid rgba(255,255,255,0.12);
        border-radius: 4px;
        padding: 0.3rem;
        background-color: #240010;
    }

    /* ── Run button — neon green ── */
    div[data-testid="stButton"] > button {
        background-color: #33FF66 !important;
        color: #180008 !important;
        border: none !important;
        border-radius: 250px !important;
        font-family: 'Space Grotesk', sans-serif !important;
        font-weight: 700 !important;
        font-size: 0.8rem !important;
        letter-spacing: 0.15em !important;
        text-transform: uppercase !important;
        padding: 0.65rem 2.4rem !important;
    }
    div[data-testid="stButton"] > button:hover {
        background-color: #CC99FF !important;
        color: #180008 !important;
    }

    /* ── Download button ── */
    div[data-testid="stDownloadButton"] > button {
        background-color: transparent !important;
        color: #33FF66 !important;
        border: 1.5px solid #33FF66 !important;
        border-radius: 250px !important;
        font-family: 'Space Grotesk', sans-serif !important;
        font-weight: 700 !important;
        font-size: 0.8rem !important;
        letter-spacing: 0.15em !important;
        text-transform: uppercase !important;
        padding: 0.65rem 2.4rem !important;
    }
    div[data-testid="stDownloadButton"] > button:hover {
        background-color: #33FF66 !important;
        color: #180008 !important;
    }

    /* ── Selectbox label ── */
    [data-testid="stSelectbox"] label {
        font-family: 'Space Grotesk', sans-serif !important;
        font-size: 0.65rem !important;
        font-weight: 700 !important;
        letter-spacing: 0.22em !important;
        text-transform: uppercase !important;
        color: #CC99FF !important;
    }

    /* ── Result label pill ── */
    .result-label {
        font-family: 'Space Grotesk', sans-serif;
        font-size: 0.65rem;
        font-weight: 700;
        letter-spacing: 0.22em;
        text-transform: uppercase;
        color: #180008;
        background-color: #33FF66;
        display: inline-block;
        padding: 0.3rem 0.9rem;
        border-radius: 100px;
        margin-bottom: 1.5rem;
    }

    /* ── Divider ── */
    hr {
        border-color: rgba(255,255,255,0.08);
        margin: 2.5rem 0;
    }

    /* ── Footer ── */
    .sweep-footer {
        margin-top: 5rem;
        padding-top: 1.5rem;
        border-top: 1px solid rgba(255,255,255,0.08);
        text-align: left;
        font-family: 'Space Grotesk', sans-serif;
        font-size: 0.65rem;
        letter-spacing: 0.2em;
        text-transform: uppercase;
        color: rgba(255,255,255,0.25);
    }
</style>
""", unsafe_allow_html=True)

# ── Load validator prompt ─────────────────────────────────────────────────────
@st.cache_resource
def load_prompt() -> str:
    prompt_path = Path(__file__).parent / "sweep-brief-validator-prompt.md"
    return prompt_path.read_text(encoding="utf-8")

# ── Google Sheets logging ──────────────────────────────────────────────────────
SHEET_ID = "1-m7J24Qzz3QoC7Sm6mP_OOKiAuAOUkzZJX403OxpHUE"

def extract_score(text: str) -> str:
    """Pull the first percentage that looks like a total score from the report."""
    match = re.search(r'\b(\d{1,3})%', text)
    return f"{match.group(1)}%" if match else "—"

def log_to_sheet(filename: str, size_mb: float, type_used: str, score: str, duration: float):
    """Append one row to the Sweep Validator Log sheet. Fails silently."""
    try:
        creds = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(SHEET_ID)
        ws = sh.sheet1
        ws.append_row([
            datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            filename,
            round(size_mb, 1),
            type_used,
            score,
            round(duration),
        ])
    except Exception:
        pass  # Never block the user if logging fails

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown('<div class="sweep-wordmark">Sweep Agency</div>', unsafe_allow_html=True)

st.markdown("""
<div class="sweep-headline">Brief<br>Validator</div>
""", unsafe_allow_html=True)

st.markdown(
    '<div class="sweep-subline">'
    'Upload a presentation PDF. Claude reads every slide and scores it '
    'across 12 dimensions of Sweep\'s creative and strategic standards.'
    '</div>',
    unsafe_allow_html=True,
)

st.divider()

# ── Upload ────────────────────────────────────────────────────────────────────
st.markdown('<div class="sweep-label">Presentation</div>', unsafe_allow_html=True)
uploaded_file = st.file_uploader(
    label="presentation",
    type=["pdf"],
    label_visibility="collapsed",
    help="PDF up to ~50 MB",
)

st.markdown("<div style='margin-top:1.8rem'></div>", unsafe_allow_html=True)

# ── Type override ─────────────────────────────────────────────────────────────
TYPE_OPTIONS = {
    "Auto-detect (recommended)":       None,
    "A — Campaign Pitch":              "A",
    "B — Brand Strategy":              "B",
    "C — Creative Strategy + Concept": "C",
    "D — Brand Identity":              "D",
    "E — Communication Platform":      "E",
    "F — Employer Brand":              "F",
}
type_label = st.selectbox(
    "Type override",
    options=list(TYPE_OPTIONS.keys()),
    help="Override the automatic type classification if needed.",
)
selected_type = TYPE_OPTIONS[type_label]

st.markdown("<div style='margin-top:2.2rem'></div>", unsafe_allow_html=True)

# ── Run ───────────────────────────────────────────────────────────────────────
if uploaded_file:
    size_mb = uploaded_file.size / 1_048_576
    st.caption(f"📄 {uploaded_file.name} · {size_mb:.1f} MB")

    run = st.button("Run Validator →")

    if run:
        override_note = (
            f"\n\n**USER TYPE OVERRIDE:** Skip Stage 1 classification. "
            f"Treat this deck as **Type {selected_type}** and proceed directly "
            f"to Stage 2 scoring using Type {selected_type} weights."
            if selected_type else ""
        )

        user_message = (
            "Please validate this presentation using the Sweep Brief Validator. "
            "Run Stage 1 (classify) then Stage 2 (score) exactly as specified in your instructions."
            + override_note
        )

        pdf_bytes  = uploaded_file.read()
        pdf_base64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")
        start_time = time.time()

        try:
            client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
        except KeyError:
            st.error("ANTHROPIC_API_KEY not found. Add it in Streamlit Cloud → App settings → Secrets.")
            st.stop()

        validator_prompt = load_prompt()

        st.divider()
        st.markdown('<div class="result-label">Validation Report</div>', unsafe_allow_html=True)

        result_placeholder = st.empty()
        full_response = ""

        try:
            with st.spinner("Reading and scoring the deck…"):
                with client.messages.stream(
                    model="claude-opus-4-6",
                    max_tokens=4096,
                    system=validator_prompt,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "document",
                                    "source": {
                                        "type":       "base64",
                                        "media_type": "application/pdf",
                                        "data":       pdf_base64,
                                    },
                                },
                                {"type": "text", "text": user_message},
                            ],
                        }
                    ],
                ) as stream:
                    for chunk in stream.text_stream:
                        full_response += chunk
                        result_placeholder.markdown(full_response)

        except anthropic.APIError as e:
            st.error(f"API error: {e}")
            st.stop()

        # ── Log to Google Sheet ────────────────────────────────────────────
        duration  = time.time() - start_time
        score     = extract_score(full_response)
        type_used = type_label if selected_type else "Auto-detect"
        log_to_sheet(uploaded_file.name, size_mb, type_used, score, duration)

        st.divider()
        fname = uploaded_file.name.replace(".pdf", "").replace(" ", "_")
        st.download_button(
            label="Download Report →",
            data=full_response,
            file_name=f"sweep-validator-{fname}.md",
            mime="text/markdown",
        )

else:
    st.markdown(
        "<p style='color:rgba(255,255,255,0.3); font-size:0.9rem;'>"
        "Typical decks take 60–90 seconds to score.</p>",
        unsafe_allow_html=True,
    )

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown(
    '<div class="sweep-footer">Sweep Agency · Brief Validator v1.0 · Internal use only</div>',
    unsafe_allow_html=True,
)
