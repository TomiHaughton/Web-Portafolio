import streamlit as st
import psycopg2
import pandas as pd
import yfinance as yf
from utils import apply_styles, section_header, badge

if 'user' not in st.session_state or st.session_state.user is None:
    st.error("Debes iniciar sesión.")
    st.stop()
USER_ID = st.session_state.user[0]

st.set_page_config(layout="wide", page_title="Watchlist · Portfolio")
apply_styles()

def conectar_db():
    return psycopg2.connect(
        host=st.secrets["connections"]["supabase"]["host"],
        database=st.secrets["connections"]["supabase"]["database"],
        user=st.secrets["connections"]["supabase"]["username"],
        password=st.secrets["connections"]["supabase"]["password"],
        port=st.secrets["connections"]["supabase"]["port"]
    )

def ver_watchlist(user_id):
    conn = conectar_db()
    df = pd.read_sql_query("SELECT * FROM watchlist WHERE user_id = %s", conn, params=(user_id,))
    conn.close()
    return df

def anadir_a_watchlist(ticker, precio_objetivo, notas, user_id):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM watchlist WHERE ticker = %s AND user_id = %s", (ticker, user_id))
    if cursor.fetchone():
        conn.close()
        st.warning("Ya existe en tu watchlist.")
        return False
    cursor.execute(
        "INSERT INTO watchlist (ticker, precio_objetivo, notas, user_id) VALUES (%s, %s, %s, %s)",
        (ticker, precio_objetivo, notas, user_id)
    )
    conn.commit(); conn.close()
    return True

def eliminar_de_watchlist(ticker_id, user_id):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM watchlist WHERE id = %s AND user_id = %s", (ticker_id, user_id))
    conn.commit(); conn.close()

@st.cache_data(ttl=600)
def obtener_info_watchlist(tickers):
    info = {}
    for t in tickers:
        try:
            obj  = yf.Ticker(t)
            dat  = obj.info
            hist = obj.history(period="1mo")
            rend = (
                (hist['Close'].iloc[-1] - hist['Close'].iloc[-8]) / hist['Close'].iloc[-8] * 100
                if len(hist) > 7 else None
            )
            info[t] = {
                'precio': dat.get('currentPrice', 0),
                'pe':     dat.get('trailingPE'),
                'rend':   rend,
                'min52':  dat.get('fiftyTwoWeekLow'),
                'max52':  dat.get('fiftyTwoWeekHigh'),
            }
        except:
            info[t] = {'precio': 0}
    return info

# ── HEADER ────────────────────────────────────────────────────────
st.markdown("<h1>Watchlist</h1>", unsafe_allow_html=True)
st.markdown(
    '<div style="color:#475569;font-size:0.85rem;font-family:JetBrains Mono,monospace;margin-top:-8px;margin-bottom:24px">'
    'Seguimiento de activos en radar</div>',
    unsafe_allow_html=True
)

# ── ADD FORM ──────────────────────────────────────────────────────
section_header("Agregar a Watchlist")
with st.form("wf", clear_on_submit=True):
    c1, c2, c3 = st.columns([1, 1, 2])
    tk = c1.text_input("Ticker", placeholder="AAPL")
    po = c2.number_input("Precio objetivo", min_value=0.0, format="%.2f")
    nt = c3.text_input("Notas", placeholder="Tesis de inversión...")
    submitted = st.form_submit_button("Agregar", use_container_width=True)
    if submitted and tk:
        CRIPTOS = {"BTC","ETH","SOL","USDT","BNB","XRP","ADA","DOGE","SHIB","DOT","DAI","MATIC","AVAX","TRX","LTC","LINK","ATOM","UNI"}
        tk_fin = tk.upper()
        if tk_fin in CRIPTOS: tk_fin = f"{tk_fin}-USD"
        if anadir_a_watchlist(tk_fin, po, nt, USER_ID):
            st.success(f"✓ {tk_fin} agregado a la watchlist.")
            st.rerun()

st.divider()

# ── WATCHLIST TABLE ───────────────────────────────────────────────
df = ver_watchlist(USER_ID)

if not df.empty:
    inf = obtener_info_watchlist(df['ticker'].tolist())
    section_header("Activos en seguimiento", f"{len(df)} tickers")

    # Header
    cols_h = st.columns([1.2, 1.8, 1.2, 2.5, 1, 1, 0.5])
    for col, lbl in zip(cols_h, ["Ticker", "Precio / Rango 52s", "Objetivo", "Notas", "P/E", "Rend 7d", ""]):
        col.markdown(
            f'<span style="font-size:0.65rem;text-transform:uppercase;letter-spacing:1px;'
            f'color:#334155;font-family:JetBrains Mono,monospace">{lbl}</span>',
            unsafe_allow_html=True
        )

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    for _, r in df.iterrows():
        d    = inf.get(r['ticker'], {})
        precio = d.get('precio', 0)
        cols = st.columns([1.2, 1.8, 1.2, 2.5, 1, 1, 0.5])

        # Ticker
        cols[0].markdown(
            f'<span style="color:#e2e8f0;font-family:JetBrains Mono,monospace;'
            f'font-size:0.9rem;font-weight:500">{r["ticker"]}</span>',
            unsafe_allow_html=True
        )

        # Precio + barra 52s
        cols[1].markdown(
            f'<span style="color:#cbd5e1;font-family:JetBrains Mono,monospace;font-size:0.85rem">'
            f'${precio:,.2f}</span>',
            unsafe_allow_html=True
        )
        if d.get('min52') and d.get('max52') and d['max52'] > d['min52']:
            pct = int(((precio - d['min52']) / (d['max52'] - d['min52'])) * 100)
            pct = max(0, min(100, pct))
            cols[1].markdown(
                f'<div style="background:#1a2540;border-radius:3px;height:4px;margin-top:4px">'
                f'<div style="background:#10b981;width:{pct}%;height:4px;border-radius:3px"></div>'
                f'</div>'
                f'<div style="display:flex;justify-content:space-between;margin-top:2px">'
                f'<span style="color:#334155;font-size:0.62rem;font-family:JetBrains Mono,monospace">${d["min52"]:,.0f}</span>'
                f'<span style="color:#334155;font-size:0.62rem;font-family:JetBrains Mono,monospace">${d["max52"]:,.0f}</span>'
                f'</div>',
                unsafe_allow_html=True
            )

        # Objetivo + distancia
        obj = r['precio_objetivo']
        if obj and obj > 0 and precio > 0:
            dist = ((obj - precio) / precio) * 100
            dist_color = "#10b981" if dist > 0 else "#ef4444"
            dist_sign  = "+" if dist > 0 else ""
            cols[2].markdown(
                f'<span style="color:#cbd5e1;font-family:JetBrains Mono,monospace;font-size:0.85rem">'
                f'${obj:,.2f}</span><br>'
                f'<span style="color:{dist_color};font-size:0.72rem;font-family:JetBrains Mono,monospace">'
                f'{dist_sign}{dist:.1f}% al obj.</span>',
                unsafe_allow_html=True
            )
        else:
            cols[2].markdown(
                f'<span style="color:#475569;font-family:JetBrains Mono,monospace;font-size:0.85rem">—</span>',
                unsafe_allow_html=True
            )

        # Notas
        cols[3].markdown(
            f'<span style="color:#64748b;font-size:0.82rem">{r["notas"] or "—"}</span>',
            unsafe_allow_html=True
        )

        # P/E
        pe = d.get('pe')
        cols[4].markdown(
            f'<span style="color:#94a3b8;font-family:JetBrains Mono,monospace;font-size:0.82rem">'
            f'{pe:.1f}x</span>' if pe else '<span style="color:#334155;font-size:0.82rem">N/A</span>',
            unsafe_allow_html=True
        )

        # Rend 7d
        ren = d.get('rend')
        if ren is not None:
            r_color = "#10b981" if ren >= 0 else "#ef4444"
            r_sign  = "+" if ren >= 0 else ""
            cols[5].markdown(
                f'<span style="color:{r_color};font-family:JetBrains Mono,monospace;font-size:0.85rem;font-weight:500">'
                f'{r_sign}{ren:.2f}%</span>',
                unsafe_allow_html=True
            )
        else:
            cols[5].markdown('<span style="color:#334155;font-size:0.82rem">N/A</span>', unsafe_allow_html=True)

        # Delete
        if cols[6].button("✕", key=f"d{r['id']}", help="Eliminar"):
            eliminar_de_watchlist(r['id'], USER_ID)
            st.rerun()

        st.markdown("<div style='height:2px;background:#0a0f1e;margin:4px 0'></div>", unsafe_allow_html=True)

else:
    st.markdown("""
        <div style="height:200px;display:flex;align-items:center;justify-content:center;
                    color:#334155;font-size:0.9rem;border:1px dashed #1a2540;border-radius:12px;
                    flex-direction:column;gap:8px">
            <span style="font-size:1.5rem">🎯</span>
            Tu watchlist está vacía — agregá tickers arriba
        </div>
    """, unsafe_allow_html=True)