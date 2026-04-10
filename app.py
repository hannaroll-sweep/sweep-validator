import streamlit as st
import anthropic
import base64
from pathlib import Path

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Brief Validator — Sweep",
    page_icon="https://wearesweep.com/favicon.ico",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── Brand styles (wearesweep.com) ─────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap');

    /* Global */
    html, body, [class*="css"] {
        font-family: Georgia, serif;
        background-color: #ffffff;
        color: #222222;
    }
    #MainMenu {visibility: hidden;}
    footer     {visibility: hidden;}
    header     {visibility: hidden;}

    /* Constrain width for a clean centered layout */
    .block-container {
        max-width: 780px;
        padding-top: 3rem;
        padding-bottom: 3rem;
    }

    /* Wordmark / logo area */
    .sweep-wordmark {
        font-family: 'Roboto', sans-serif;
        font-size: 0.8rem;
        font-weight: 700;
        letter-spacing: 0.18em;
        text-transform: uppercase;
        color: #330000;
        margin-bottom: 3rem;
    }

    /* Hero headline */
    .sweep-headline {
        font-family: 'Roboto', sans-serif;
        font-size: 2.4rem;
        font-weight: 700;
        color: #330000;
        line-height: 1.15;
        margin-bottom: 0.5rem;
    }

    /* Subline */
    .sweep-subline {
        font-family: Georgia, serif;
        font-size: 1rem;
        color: #555555;
        margin-bottom: 2.5rem;
        line-height: 1.6;
    }

    /* Section label */
    .sweep-label {
        font-family: 'Roboto', sans-serif;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.15em;
        text-transform: uppercase;
        color: #330000;
        margin-bottom: 0.4rem;
    }

    /* File uploader */
    [data-testid="stFileUploader"] {
        border: 1.5px solid #e0e0e0;
        border-radius: 8px;
        padding: 0.5rem;
    }

    /* Run button — white bg, burgundy text, pill shape (Sweep style) */
    div[data-testid="stButton"] > button {
        background-color: #ffffff !important;
        color: #330000 !important;
        border: 2px solid #330000 !important;
        border-radius: 250px !important;
        font-family: 'Roboto', sans-serif !important;
        font-weight: 700 !important;
        font-size: 0.85rem !important;
        letter-spacing: 0.08em !important;
        text-transform: uppercase !important;
        padding: 0.55rem 2.2rem !important;
        transition: all 0.2s ease !important;
    }
    div[data-testid="stButton"] > button:hover {
        background-color: #330000 !important;
        color: #cc99ff !important;
    }

    /* Download button — blue accent */
    div[data-testid="stDownloadButton"] > button {
        background-color: #0080FF !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 250px !important;
        font-family: 'Roboto', sans-serif !important;
        font-weight: 700 !important;
        font-size: 0.85rem !important;
        letter-spacing: 0.08em !important;
        text-transform: uppercase !important;
        padding: 0.55rem 2.2rem !important;
    }
    div[data-testid="stDownloadButton"] > button:hover {
        background-color: #0066cc !important;
    }

    /* Result area */
    .result-box {
        border-left: 3px solid #330000;
        padding-left: 1.5rem;
        margin-top: 2rem;
    }

    /* Divider */
    hr { border-color: #f0f0f0; margin: 2.5rem 0; }

    /* Selectbox */
    [data-testid="stSelectbox"] label {
        font-family: 'Roboto', sans-serif;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.15em;
        text-transform: uppercase;
        color: #330000;
    }

    /* Info box */
    [data-testid="stAlert"] {
        border-radius: 6px;
        border: 1px solid #e0e0e0;
        background-color: #fafafa;
        color: #222;
    }
</style>
""", unsafe_allow_html=True)

# ── Load validator prompt ─────────────────────────────────────────────────────
@st.cache_resource
def load_prompt() -> str:
    prompt_path = Path(__file__).parent / "sweep-brief-validator-prompt.md"
    return prompt_path.read_text(encoding="utf-8")

# ── Wordmark ──────────────────────────────────────────────────────────────────
st.markdown('<div class="sweep-wordmark">Sweep Agency</div>', unsafe_allow_html=True)

# ── Headline ──────────────────────────────────────────────────────────────────
st.markdown('<div class="sweep-headline">Brief Validator</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sweep-subline">Upload a presentation PDF. '
    'Claude reads every slide and scores it across 12 dimensions '
    'of Sweep\'s creative and strategic standards.</div>',
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

st.markdown("<div style='margin-top:1.5rem'></div>", unsafe_allow_html=True)

# ── Type override ─────────────────────────────────────────────────────────────
TYPE_OPTIONS = {
    "Auto-detect (recommended)":      None,
    "A — Campaign Pitch":             "A",
    "B — Brand Strategy":             "B",
    "C — Creative Strategy + Concept": "C",
    "D — Brand Identity":             "D",
    "E — Communication Platform":     "E",
    "F — Employer Brand":             "F",
}
type_label = st.selectbox(
    "Type override",
    options=list(TYPE_OPTIONS.keys()),
    help="Override the automatic type classification if needed.",
)
selected_type = TYPE_OPTIONS[type_label]

st.markdown("<div style='margin-top:2rem'></div>", unsafe_allow_html=True)

# ── Run ───────────────────────────────────────────────────────────────────────
if uploaded_file:
    size_mb = uploaded_file.size / 1_048_576
    st.caption(f"📄 {uploaded_file.name} · {size_mb:.1f} MB")

    run = st.button("Run Validator →")

    if run:
        if selected_type:
            override_note = (
                f"\n\n**USER TYPE OVERRIDE:** Skip Stage 1 classification. "
                f"Treat this deck as **Type {selected_type}** and proceed directly "
                f"to Stage 2 scoring using Type {selected_type} weights."
            )
        else:
            override_note = ""

        user_message = (
            "Please validate this presentation using the Sweep Brief Validator. "
            "Run Stage 1 (classify) then Stage 2 (score) exactly as specified in your instructions."
            + override_note
        )

        pdf_bytes  = uploaded_file.read()
        pdf_base64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")

        try:
            client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
        except KeyError:
            st.error("ANTHROPIC_API_KEY not found in secrets. Add it in Streamlit Cloud → App settings → Secrets.")
            st.stop()

        validator_prompt = load_prompt()

        st.divider()
        st.markdown('<div class="sweep-label">Validation Report</div>', unsafe_allow_html=True)
        st.markdown("<div style='margin-top:1rem'></div>", unsafe_allow_html=True)

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
        "<p style='color:#aaaaaa; font-size:0.9rem;'>"
        "Typical decks take 60–90 seconds to score.</p>",
        unsafe_allow_html=True,
    )

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown(
    "<div style='margin-top:4rem; padding-top:1.5rem; border-top:1px solid #f0f0f0;"
    "text-align:center; font-size:0.75rem; color:#bbbbbb; letter-spacing:0.1em;"
    "text-transform:uppercase; font-family:Roboto,sans-serif;'>"
    "Sweep Agency · Brief Validator v1.0 · Internal use only"
    "</div>",
    unsafe_allow_html=True,
)
