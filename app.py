import streamlit as st
import anthropic
import base64
from pathlib import Path

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Sweep Brief Validator",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Sweep brand styling ───────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Hide Streamlit default menu & footer */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* Header */
    .sweep-header {
        background-color: #3B0004;
        color: white;
        padding: 1.5rem 2rem;
        border-radius: 8px;
        margin-bottom: 1.5rem;
    }
    .sweep-header h1 { margin: 0; font-size: 1.8rem; font-weight: 700; }
    .sweep-header p  { margin: 0.3rem 0 0 0; opacity: 0.8; font-size: 0.95rem; }

    /* Primary button */
    div[data-testid="stButton"] > button {
        background-color: #3B0004 !important;
        color: white !important;
        border: none !important;
        font-weight: 600;
        padding: 0.6rem 2.5rem;
        border-radius: 6px;
        font-size: 1rem;
    }
    div[data-testid="stButton"] > button:hover {
        background-color: #5c0007 !important;
    }
</style>
""", unsafe_allow_html=True)

# ── Load validator prompt (cached so it only reads once per session) ──────────
@st.cache_resource
def load_prompt() -> str:
    prompt_path = Path(__file__).parent / "sweep-brief-validator-prompt.md"
    return prompt_path.read_text(encoding="utf-8")

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="sweep-header">
    <h1>🎯 Sweep Brief Validator</h1>
    <p>Internal tool for creative directors · Upload a presentation PDF to score it</p>
</div>
""", unsafe_allow_html=True)

# ── Upload + options ──────────────────────────────────────────────────────────
col_upload, col_type = st.columns([3, 2])

with col_upload:
    uploaded_file = st.file_uploader(
        "Upload presentation PDF",
        type=["pdf"],
        help="Supported: PDF up to ~50 MB",
    )

with col_type:
    TYPE_OPTIONS = {
        "Auto-detect (recommended)": None,
        "A — Campaign Pitch":             "A",
        "B — Brand Strategy":             "B",
        "C — Creative Strategy + Concept": "C",
        "D — Brand Identity":             "D",
        "E — Communication Platform":     "E",
        "F — Employer Brand":             "F",
    }
    type_label = st.selectbox(
        "Type override (optional)",
        options=list(TYPE_OPTIONS.keys()),
        help="Leave on Auto-detect to let the validator classify the deck itself.",
    )
    selected_type = TYPE_OPTIONS[type_label]

# ── File info + run button ────────────────────────────────────────────────────
if uploaded_file:
    size_mb = uploaded_file.size / 1_048_576
    st.info(f"📄 **{uploaded_file.name}** — {size_mb:.1f} MB")

    run = st.button("🎯 Run Validator")

    if run:
        # ── Build override instruction ─────────────────────────────────────
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

        # ── Encode PDF ─────────────────────────────────────────────────────
        pdf_bytes  = uploaded_file.read()
        pdf_base64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")

        # ── Call Claude ────────────────────────────────────────────────────
        try:
            client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
        except KeyError:
            st.error(
                "⚠️ **API key not configured.** "
                "Add `ANTHROPIC_API_KEY` to your app secrets in Streamlit Cloud."
            )
            st.stop()

        validator_prompt = load_prompt()

        st.divider()
        st.subheader("Validation Report")

        result_placeholder = st.empty()
        full_response      = ""

        try:
            with st.spinner("Claude is reading and scoring the deck…"):
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

        # ── Download button ────────────────────────────────────────────────
        st.divider()
        fname = uploaded_file.name.replace(".pdf", "").replace(" ", "_")
        st.download_button(
            label="📥 Download report as Markdown",
            data=full_response,
            file_name=f"sweep-validator-{fname}.md",
            mime="text/markdown",
        )

else:
    st.markdown(
        "_Upload a PDF above to get started. "
        "Typical decks score in 60–90 seconds depending on page count._"
    )

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown(
    "<br><hr><p style='text-align:center; color:#888; font-size:0.8rem;'>"
    "Sweep Agency · Brief Validator v1.0 · Internal use only</p>",
    unsafe_allow_html=True,
)
