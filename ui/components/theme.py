import streamlit as st

from config.design_tokens import COLORS


def apply_global_styles() -> None:
    """Tune native Streamlit controls to the shared visual language."""
    st.markdown(
        f"""
        <style>
        :root {{
            --golf-forest: {COLORS['forest']};
            --golf-forest-dark: {COLORS['forest_dark']};
            --golf-canvas: {COLORS['canvas']};
            --golf-surface: {COLORS['surface']};
            --golf-border: {COLORS['border']};
            --golf-muted: {COLORS['muted']};
            --golf-focus-ring: {COLORS['focus_ring']};
            --golf-accent: {COLORS['accent']};
        }}

        [data-testid="stAppViewContainer"] {{
            background: var(--golf-canvas);
        }}
        [data-testid="stHeader"] {{
            display: none;
        }}
        [data-testid="stDecoration"] {{
            display: none;
        }}
        [data-testid="stToolbar"] {{
            visibility: hidden;
        }}
        [data-testid="stMainBlockContainer"] {{
            padding-top: 0.75rem;
            padding-bottom: 3rem;
        }}
        [data-testid="stVerticalBlockBorderWrapper"] {{
            border-color: var(--golf-border);
            background: var(--golf-surface);
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(32, 53, 45, 0.06);
        }}
        [data-testid="stBaseButton-primary"] {{
            background: var(--golf-forest);
            border-color: var(--golf-forest);
            color: white;
        }}
        [data-testid="stBaseButton-primary"]:hover {{
            background: var(--golf-forest-dark);
            border-color: var(--golf-forest-dark);
        }}
        [data-testid="stBaseButton-secondary"] {{
            background: var(--golf-surface);
            border-color: var(--golf-border);
            color: var(--golf-forest-dark);
        }}
        [data-testid="stBaseButton-secondary"]:hover {{
            border-color: var(--golf-forest);
            color: var(--golf-forest-dark);
            background: var(--golf-focus-ring);
            box-shadow: 0 3px 10px rgba(36, 86, 74, 0.12);
        }}
        button[aria-label="Forrige hull"] svg,
        button[aria-label="Bekreft og gå til neste hull"] svg {{
            width: 1.45rem;
            height: 1.45rem;
        }}
        button[aria-label="Forrige hull"],
        button[aria-label="Bekreft og gå til neste hull"] {{
            min-height: 2.75rem;
        }}
        [data-baseweb="tab-list"] {{
            gap: 1.25rem;
        }}
        [data-baseweb="tab"] {{
            color: var(--golf-muted);
        }}
        [aria-selected="true"][data-baseweb="tab"] {{
            color: var(--golf-forest-dark);
        }}
        [data-testid="stMetricValue"] {{
            color: var(--golf-forest-dark);
        }}
        .golf-page-title {{
            margin: 0;
            color: var(--golf-forest-dark);
            font-size: clamp(0.77rem, 8cqi, 1.4rem);
            font-weight: 750;
            line-height: 1.1;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        [data-testid="stHorizontalBlock"]:has(.golf-page-title) {{
            flex-wrap: nowrap;
        }}
        [data-testid="stHorizontalBlock"]:has(.golf-page-title) > div {{
            flex: 0 0 auto;
        }}
        [data-testid="stHorizontalBlock"]:has(.golf-page-title) > div:has(.golf-page-title) {{
            flex: 1 1 auto;
            min-width: 0;
            container-type: inline-size;
        }}
        .golf-context {{
            margin: 0.25rem 0 0;
            color: var(--golf-muted);
            font-size: 0.9rem;
        }}
        .golf-hole-title {{
            margin: 0;
            color: var(--golf-forest-dark);
            font-size: 1.05rem;
            font-weight: 750;
            line-height: 1.2;
            text-align: center;
            white-space: nowrap;
        }}
        .golf-section-label {{
            margin: 0 0 0.5rem;
            color: var(--golf-forest-dark);
            font-size: 1rem;
            font-weight: 750;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
