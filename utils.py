import streamlit as st
import plotly.graph_objects as go
import psycopg2
import pandas as pd

# ─────────────────────────────────────────────
#  GLOBAL CSS — inject at the top of every page
# ─────────────────────────────────────────────
DARK_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

/* ── BASE ── */
html, body, .stApp {
    background-color: #070c18 !important;
    color: #e2e8f0 !important;
}
*, p, span, div, label { font-family: 'DM Sans', sans-serif !important; }

/* ── SIDEBAR ── */
[data-testid="stSidebar"] {
    background: #0b1220 !important;
    border-right: 1px solid #1a2540 !important;
}
[data-testid="stSidebar"] * { color: #94a3b8 !important; }
[data-testid="stSidebar"] [data-testid="stMetricValue"] {
    color: #10b981 !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 1.3rem !important;
}
[data-testid="stSidebar"] [data-testid="stMetricLabel"] {
    color: #475569 !important;
    font-size: 0.7rem !important;
    text-transform: uppercase;
    letter-spacing: 1px;
}

/* ── HEADINGS ── */
h1 {
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 800 !important;
    color: #f1f5f9 !important;
    font-size: 2rem !important;
    letter-spacing: -0.5px !important;
}
h2 {
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 600 !important;
    color: #e2e8f0 !important;
    font-size: 1.25rem !important;
    letter-spacing: -0.3px !important;
}
h3 {
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 500 !important;
    color: #cbd5e1 !important;
}

/* ── NATIVE METRICS (fallback) ── */
[data-testid="metric-container"] {
    background: #0f1729 !important;
    border: 1px solid #1e2e4a !important;
    border-radius: 12px !important;
    padding: 16px 20px !important;
}
[data-testid="metric-container"] label {
    color: #475569 !important;
    font-size: 0.68rem !important;
    text-transform: uppercase !important;
    letter-spacing: 1.2px !important;
    font-family: 'JetBrains Mono', monospace !important;
}
[data-testid="stMetricValue"] {
    color: #f1f5f9 !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-weight: 500 !important;
}
[data-testid="stMetricDelta"] { font-family: 'JetBrains Mono', monospace !important; }

/* ── DATAFRAME ── */
.stDataFrame {
    border: 1px solid #1a2540 !important;
    border-radius: 12px !important;
    overflow: hidden !important;
}
.stDataFrame thead tr th {
    background: #0c1223 !important;
    color: #475569 !important;
    font-size: 0.68rem !important;
    text-transform: uppercase !important;
    letter-spacing: 1px !important;
    font-family: 'JetBrains Mono', monospace !important;
    border-bottom: 1px solid #1a2540 !important;
}
.stDataFrame tbody tr td {
    background: #070c18 !important;
    color: #cbd5e1 !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.82rem !important;
    border-bottom: 1px solid #0f1729 !important;
}
.stDataFrame tbody tr:hover td { background: #0c1223 !important; }

/* ── BUTTONS ── */
.stButton > button {
    background: #0f1729 !important;
    color: #64748b !important;
    border: 1px solid #1e2e4a !important;
    border-radius: 8px !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.78rem !important;
    transition: all 0.18s ease !important;
}
.stButton > button:hover {
    background: #1e2e4a !important;
    color: #10b981 !important;
    border-color: #10b981 !important;
}

/* ── FORM ── */
[data-testid="stForm"] {
    background: #0b1220 !important;
    border: 1px solid #1a2540 !important;
    border-radius: 16px !important;
    padding: 24px !important;
}
.stTextInput > div > div > input,
.stNumberInput > div > div > input {
    background: #0f1729 !important;
    color: #e2e8f0 !important;
    border: 1px solid #1e2e4a !important;
    border-radius: 8px !important;
    font-family: 'JetBrains Mono', monospace !important;
}
.stTextInput > div > div > input:focus,
.stNumberInput > div > div > input:focus {
    border-color: #10b981 !important;
    box-shadow: 0 0 0 2px rgba(16,185,129,0.12) !important;
}
[data-baseweb="select"] > div {
    background: #0f1729 !important;
    border: 1px solid #1e2e4a !important;
    border-radius: 8px !important;
    color: #e2e8f0 !important;
}
[data-baseweb="menu"] { background: #0f1729 !important; border: 1px solid #1e2e4a !important; }
[data-baseweb="option"] { background: #0f1729 !important; color: #cbd5e1 !important; }
[data-baseweb="option"]:hover { background: #1e2e4a !important; }

/* ── SUBMIT BUTTON ── */
[data-testid="stFormSubmitButton"] > button {
    background: linear-gradient(135deg, #059669, #10b981) !important;
    color: #f0fdf4 !important;
    border: none !important;
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.9rem !important;
    letter-spacing: 0.3px !important;
    border-radius: 10px !important;
    padding: 10px 24px !important;
    transition: opacity 0.2s !important;
}
[data-testid="stFormSubmitButton"] > button:hover { opacity: 0.88 !important; }

/* ── DATE INPUT ── */
[data-baseweb="input"] input {
    background: #0f1729 !important;
    color: #e2e8f0 !important;
    border: 1px solid #1e2e4a !important;
    font-family: 'JetBrains Mono', monospace !important;
}

/* ── DIVIDER ── */
hr { border-color: #1a2540 !important; margin: 28px 0 !important; }

/* ── EXPANDER ── */
.streamlit-expanderHeader {
    background: #0b1220 !important;
    border: 1px solid #1a2540 !important;
    border-radius: 10px !important;
    color: #64748b !important;
    font-size: 0.85rem !important;
}
.streamlit-expanderContent {
    background: #0b1220 !important;
    border: 1px solid #1a2540 !important;
    border-top: none !important;
}

/* ── TABS ── */
[data-baseweb="tab-list"] { background: #0b1220 !important; border-radius: 8px !important; padding: 4px !important; }
[data-baseweb="tab"] { color: #475569 !important; font-size: 0.85rem !important; border-radius: 6px !important; }
[aria-selected="true"][data-baseweb="tab"] {
    background: #1e2e4a !important;
    color: #10b981 !important;
}

/* ── PROGRESS BAR ── */
.stProgress > div > div > div > div { background: linear-gradient(90deg, #059669, #10b981) !important; }

/* ── ALERTS ── */
.stSuccess { background: rgba(16,185,129,0.08) !important; border: 1px solid rgba(16,185,129,0.3) !important; border-radius: 10px !important; color: #6ee7b7 !important; }
.stInfo    { background: rgba(59,130,246,0.08) !important; border: 1px solid rgba(59,130,246,0.3) !important; border-radius: 10px !important; color: #93c5fd !important; }
.stWarning { background: rgba(245,158,11,0.08) !important; border: 1px solid rgba(245,158,11,0.3) !important; border-radius: 10px !important; color: #fcd34d !important; }
.stError   { background: rgba(239,68,68,0.08)  !important; border: 1px solid rgba(239,68,68,0.3)  !important; border-radius: 10px !important; color: #fca5a5 !important; }

/* ── SCROLLBAR ── */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: #070c18; }
::-webkit-scrollbar-thumb { background: #1e2e4a; border-radius: 2px; }
::-webkit-scrollbar-thumb:hover { background: #2a3f66; }

/* ── FADE IN ── */
@keyframes fadeUp {
    from { opacity: 0; transform: translateY(10px); }
    to   { opacity: 1; transform: translateY(0); }
}
section.main > div { animation: fadeUp 0.35s ease-out; }
</style>
"""

# ─────────────────────────────────────────────
#  PLOTLY CONFIG — pass layout_overrides to figs
# ─────────────────────────────────────────────
PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="#0a0f1e",
    font=dict(color="#64748b", family="JetBrains Mono"),
    colorway=["#10b981","#3b82f6","#f59e0b","#8b5cf6","#ef4444","#06b6d4","#ec4899","#84cc16"],
    xaxis=dict(gridcolor="#1a2540", zerolinecolor="#1a2540", tickfont=dict(color="#475569", size=11)),
    yaxis=dict(gridcolor="#1a2540", zerolinecolor="#1a2540", tickfont=dict(color="#475569", size=11)),
    legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="#94a3b8", size=12)),
    margin=dict(l=16, r=16, t=40, b=16),
)

PIE_COLORS = ["#10b981","#3b82f6","#f59e0b","#8b5cf6","#ef4444","#06b6d4","#ec4899","#84cc16","#a3e635","#fb923c"]

# ─────────────────────────────────────────────
#  HELPER FUNCTIONS
# ─────────────────────────────────────────────

def apply_styles():
    """Inject global CSS. Call once at the top of every page."""
    st.markdown(DARK_CSS, unsafe_allow_html=True)


def metric_card(label, value, subtitle=None, color="default"):
    """
    Render a styled metric card.
    color: "green" | "red" | "blue" | "amber" | "default"
    """
    palettes = {
        "green":   ("#10b981", "rgba(16,185,129,0.06)", "#052e16"),
        "red":     ("#ef4444", "rgba(239,68,68,0.06)",  "#2d0a0a"),
        "blue":    ("#3b82f6", "rgba(59,130,246,0.06)", "#0a1628"),
        "amber":   ("#f59e0b", "rgba(245,158,11,0.06)", "#1c1000"),
        "default": ("#334155", "rgba(51,65,85,0.4)",    "#0f1729"),
    }
    accent, bg, _ = palettes.get(color, palettes["default"])
    sub_html = (
        f'<div style="font-size:0.72rem;color:#475569;margin-top:6px;'
        f'font-family:JetBrains Mono,monospace">{subtitle}</div>'
    ) if subtitle else ""
    st.markdown(f"""
        <div style="
            background:{bg};
            border:1px solid #1a2540;
            border-left:3px solid {accent};
            border-radius:12px;
            padding:18px 20px;
            min-height:90px;
        ">
            <div style="
                font-size:0.65rem;
                text-transform:uppercase;
                letter-spacing:1.4px;
                color:#475569;
                font-family:'JetBrains Mono',monospace;
                margin-bottom:8px;
            ">{label}</div>
            <div style="
                font-size:1.45rem;
                font-weight:500;
                color:#f1f5f9;
                font-family:'JetBrains Mono',monospace;
                line-height:1.2;
            ">{value}</div>
            {sub_html}
        </div>
    """, unsafe_allow_html=True)


def section_header(title, subtitle=None):
    """Render a styled section header."""
    sub = (
        f'<div style="color:#475569;font-size:0.82rem;margin-top:3px;'
        f'font-family:DM Sans,sans-serif">{subtitle}</div>'
    ) if subtitle else ""
    st.markdown(f"""
        <div style="margin:36px 0 16px">
            <div style="
                font-size:1.05rem;
                font-weight:600;
                color:#e2e8f0;
                font-family:'DM Sans',sans-serif;
                letter-spacing:-0.2px;
                border-left:3px solid #10b981;
                padding-left:12px;
            ">{title}</div>
            {sub}
        </div>
    """, unsafe_allow_html=True)


def badge(text, color="green"):
    """Inline badge: gain / loss / neutral labels."""
    palettes = {
        "green": ("#10b981", "rgba(16,185,129,0.12)"),
        "red":   ("#ef4444", "rgba(239,68,68,0.12)"),
        "gray":  ("#64748b", "rgba(100,116,139,0.12)"),
    }
    fg, bg = palettes.get(color, palettes["gray"])
    return (
        f'<span style="background:{bg};color:{fg};border:1px solid {fg}33;'
        f'border-radius:5px;padding:2px 8px;font-size:0.72rem;'
        f'font-family:JetBrains Mono,monospace;font-weight:500">{text}</span>'
    )


def apply_plotly_style(fig, title=""):
    """Apply the dark theme to any plotly figure."""
    fig.update_layout(title=dict(text=title, font=dict(color="#94a3b8", size=13, family="DM Sans")), **PLOTLY_LAYOUT)
    return fig


# ─────────────────────────────────────────────
#  PORTFOLIO HELPERS
# ─────────────────────────────────────────────

def _conectar():
    return psycopg2.connect(
        host=st.secrets["connections"]["supabase"]["host"],
        database=st.secrets["connections"]["supabase"]["database"],
        user=st.secrets["connections"]["supabase"]["username"],
        password=st.secrets["connections"]["supabase"]["password"],
        port=st.secrets["connections"]["supabase"]["port"]
    )

def ver_portafolios(user_id):
    conn = _conectar()
    df = pd.read_sql_query(
        "SELECT * FROM portafolios WHERE user_id=%s ORDER BY id ASC",
        conn, params=(user_id,)
    )
    conn.close()
    return df

def crear_portafolio(user_id, nombre, descripcion=""):
    conn = _conectar()
    c = conn.cursor()
    c.execute(
        "INSERT INTO portafolios (user_id, nombre, descripcion) VALUES (%s,%s,%s) RETURNING id",
        (user_id, nombre, descripcion)
    )
    new_id = c.fetchone()[0]
    conn.commit(); conn.close()
    return new_id

def eliminar_portafolio(portfolio_id, user_id):
    conn = _conectar()
    c = conn.cursor()
    c.execute(
        "UPDATE operaciones SET portfolio_id=NULL WHERE portfolio_id=%s AND user_id=%s",
        (portfolio_id, user_id)
    )
    c.execute(
        "DELETE FROM portafolios WHERE id=%s AND user_id=%s",
        (portfolio_id, user_id)
    )
    conn.commit(); conn.close()

def renombrar_portafolio(portfolio_id, nuevo_nombre, nueva_desc, user_id):
    conn = _conectar()
    c = conn.cursor()
    c.execute(
        "UPDATE portafolios SET nombre=%s, descripcion=%s WHERE id=%s AND user_id=%s",
        (nuevo_nombre, nueva_desc, portfolio_id, user_id)
    )
    conn.commit(); conn.close()


def portfolio_selector_sidebar(user_id):
    """
    Renders the portfolio selector in the sidebar.
    Returns (portfolio_id_or_None, label).
    None means 'Todos' (consolidated view).
    """
    portfolios = ver_portafolios(user_id)

    if portfolios.empty:
        st.session_state['portfolio_id']    = None
        st.session_state['portfolio_label'] = "Sin portafolio"
        return None, "Sin portafolio"

    opciones = {"Todos (consolidado)": None}
    for _, p in portfolios.iterrows():
        opciones[p['nombre']] = p['id']

    labels = list(opciones.keys())
    current_label = st.session_state.get('portfolio_label', labels[0])
    if current_label not in labels:
        current_label = labels[0]

    st.sidebar.markdown("""
        <div style="font-size:0.62rem;text-transform:uppercase;letter-spacing:1.4px;
                    color:#334155;font-family:JetBrains Mono,monospace;margin-bottom:6px">
            Portafolio
        </div>
    """, unsafe_allow_html=True)

    seleccion = st.sidebar.radio(
        "portafolio_radio",
        labels,
        index=labels.index(current_label),
        label_visibility="collapsed"
    )
    st.session_state['portfolio_label'] = seleccion
    st.session_state['portfolio_id']    = opciones[seleccion]

    return opciones[seleccion], seleccion


# ─────────────────────────────────────────────
#  EFECTIVO HELPERS
# ─────────────────────────────────────────────

def get_efectivo(user_id, portfolio_id=None):
    """Devuelve (saldo_usd, saldo_ars) para el usuario/portafolio."""
    conn = _conectar()
    try:
        if portfolio_id is None:
            df = pd.read_sql_query(
                "SELECT saldo_usd, saldo_ars FROM efectivo WHERE user_id=%s AND portfolio_id IS NULL",
                conn, params=(user_id,)
            )
        else:
            df = pd.read_sql_query(
                "SELECT saldo_usd, saldo_ars FROM efectivo WHERE user_id=%s AND portfolio_id=%s",
                conn, params=(user_id, portfolio_id)
            )
        conn.close()
        if df.empty:
            return 0.0, 0.0
        return float(df.iloc[0]['saldo_usd']), float(df.iloc[0]['saldo_ars'])
    except:
        conn.close()
        return 0.0, 0.0


def set_efectivo(user_id, saldo_usd, saldo_ars, portfolio_id=None):
    """Upsert del efectivo — crea o sobreescribe."""
    conn = _conectar()
    c = conn.cursor()
    try:
        if portfolio_id is None:
            c.execute(
                "SELECT id FROM efectivo WHERE user_id=%s AND portfolio_id IS NULL",
                (user_id,)
            )
        else:
            c.execute(
                "SELECT id FROM efectivo WHERE user_id=%s AND portfolio_id=%s",
                (user_id, portfolio_id)
            )
        row = c.fetchone()
        if row:
            if portfolio_id is None:
                c.execute(
                    "UPDATE efectivo SET saldo_usd=%s, saldo_ars=%s WHERE user_id=%s AND portfolio_id IS NULL",
                    (saldo_usd, saldo_ars, user_id)
                )
            else:
                c.execute(
                    "UPDATE efectivo SET saldo_usd=%s, saldo_ars=%s WHERE user_id=%s AND portfolio_id=%s",
                    (saldo_usd, saldo_ars, user_id, portfolio_id)
                )
        else:
            c.execute(
                "INSERT INTO efectivo (user_id, portfolio_id, saldo_usd, saldo_ars) VALUES (%s,%s,%s,%s)",
                (user_id, portfolio_id, saldo_usd, saldo_ars)
            )
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()