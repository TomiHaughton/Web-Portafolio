import streamlit as st
import psycopg2
import pandas as pd
import yfinance as yf
from utils import apply_styles, section_header

if 'user' not in st.session_state or st.session_state.user is None:
    st.error("Debes iniciar sesión.")
    st.stop()
USER_ID = st.session_state.user[0]

st.set_page_config(layout="wide", page_title="Watchlist · Portfolio")
apply_styles()
st.markdown("""<style>
.material-symbols-rounded,[data-testid="stNumberInputStepDown"] span,
[data-testid="stNumberInputStepUp"] span{font-size:0!important}
</style>""", unsafe_allow_html=True)

# ── DB ────────────────────────────────────────────────────────────
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
    try:
        df = pd.read_sql_query(
            "SELECT * FROM watchlist WHERE user_id=%s ORDER BY carpeta NULLS LAST, ticker",
            conn, params=(user_id,)
        )
    except Exception:
        df = pd.read_sql_query(
            "SELECT * FROM watchlist WHERE user_id=%s ORDER BY ticker",
            conn, params=(user_id,)
        )
    conn.close()
    if 'carpeta' not in df.columns:
        df['carpeta'] = None
    return df

def anadir_a_watchlist(ticker, precio_objetivo, notas, carpeta, user_id):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM watchlist WHERE ticker=%s AND user_id=%s", (ticker, user_id))
    if cursor.fetchone():
        conn.close()
        st.warning("Ya existe en tu watchlist.")
        return False
    try:
        cursor.execute(
            "INSERT INTO watchlist (ticker, precio_objetivo, notas, carpeta, user_id) VALUES (%s,%s,%s,%s,%s)",
            (ticker, precio_objetivo, notas, carpeta or None, user_id)
        )
    except Exception:
        cursor.execute(
            "INSERT INTO watchlist (ticker, precio_objetivo, notas, user_id) VALUES (%s,%s,%s,%s)",
            (ticker, precio_objetivo, notas, user_id)
        )
    conn.commit(); conn.close()
    return True

def actualizar_watchlist(ticker_id, precio_objetivo, notas, carpeta, user_id):
    conn = conectar_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE watchlist SET precio_objetivo=%s, notas=%s, carpeta=%s WHERE id=%s AND user_id=%s",
            (precio_objetivo, notas, carpeta or None, ticker_id, user_id)
        )
    except Exception:
        cursor.execute(
            "UPDATE watchlist SET precio_objetivo=%s, notas=%s WHERE id=%s AND user_id=%s",
            (precio_objetivo, notas, ticker_id, user_id)
        )
    conn.commit(); conn.close()

def eliminar_de_watchlist(ticker_id, user_id):
    conn = conectar_db()
    conn.cursor().execute("DELETE FROM watchlist WHERE id=%s AND user_id=%s", (ticker_id, user_id))
    conn.commit(); conn.close()

def ver_carpetas(user_id):
    df = ver_watchlist(user_id)
    return sorted([c for c in df['carpeta'].dropna().unique() if c])

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

CRIPTOS = {"BTC","ETH","SOL","USDT","BNB","XRP","ADA","DOGE","SHIB","DOT","DAI","MATIC","AVAX","TRX","LTC","LINK","ATOM","UNI"}

if 'editando' not in st.session_state:
    st.session_state.editando = None

# ── HEADER ────────────────────────────────────────────────────────
st.markdown("<h1>Watchlist</h1>", unsafe_allow_html=True)
st.markdown(
    '<div style="color:#475569;font-size:0.85rem;font-family:JetBrains Mono,monospace;'
    'margin-top:-8px;margin-bottom:24px">Activos en radar · organizados por carpeta</div>',
    unsafe_allow_html=True
)

# ── ADD FORM ──────────────────────────────────────────────────────
section_header("Agregar ticker")
with st.form("wf", clear_on_submit=True):
    c1, c2 = st.columns(2)
    tk            = c1.text_input("Ticker", placeholder="AAPL")
    po            = c2.number_input("Precio objetivo", min_value=0.0, format="%.2f")
    carpeta_nueva = st.text_input("Carpeta", placeholder="A comprar, A vender…")
    nt            = st.text_input("Notas", placeholder="Tesis de inversión...")
    if st.form_submit_button("Agregar", use_container_width=True) and tk:
        tk_fin = tk.upper()
        if tk_fin in CRIPTOS: tk_fin = f"{tk_fin}-USD"
        if anadir_a_watchlist(tk_fin, po, nt, carpeta_nueva.strip() or None, USER_ID):
            st.success(f"✓ {tk_fin} agregado.")
            st.cache_data.clear()
            st.rerun()

st.divider()

# ── WATCHLIST ─────────────────────────────────────────────────────
df = ver_watchlist(USER_ID)

if df.empty:
    st.markdown("""
        <div style="height:180px;display:flex;align-items:center;justify-content:center;
                    color:#334155;font-size:0.9rem;border:1px dashed #1a2540;border-radius:12px;
                    flex-direction:column;gap:8px">
            Tu watchlist está vacía
        </div>
    """, unsafe_allow_html=True)
    st.stop()

inf = obtener_info_watchlist(df['ticker'].tolist())
carpetas_existentes = ver_carpetas(USER_ID)

df['carpeta_display'] = df['carpeta'].fillna('Sin carpeta')
orden = [c for c in sorted(df['carpeta_display'].unique()) if c != 'Sin carpeta']
if 'Sin carpeta' in df['carpeta_display'].values:
    orden.append('Sin carpeta')

for carpeta_nombre in orden:
    grupo_df = df[df['carpeta_display'] == carpeta_nombre]
    icono = "📁" if carpeta_nombre != "Sin carpeta" else "📋"

    st.markdown(f"""
        <div style="display:flex;align-items:center;gap:10px;margin:28px 0 12px;
                    padding-bottom:8px;border-bottom:1px solid #1a2540">
            <span>{icono}</span>
            <span style="color:#e2e8f0;font-size:0.95rem;font-weight:600">{carpeta_nombre}</span>
            <span style="color:#334155;font-size:0.75rem;font-family:JetBrains Mono,monospace">
                {len(grupo_df)} ticker{'s' if len(grupo_df) != 1 else ''}
            </span>
        </div>
    """, unsafe_allow_html=True)

    for _, r in grupo_df.iterrows():
        d      = inf.get(r['ticker'], {})
        precio = d.get('precio', 0)
        row_id = r['id']

        # ── MODO EDICIÓN ───────────────────────────────────────────
        if st.session_state.editando == row_id:
            st.markdown(
                '<div style="background:#0c1a30;border:1px solid #10b981;'
                'border-radius:10px;padding:16px;margin:6px 0">',
                unsafe_allow_html=True
            )
            ec1, ec2 = st.columns(2)
            nuevo_obj = ec1.number_input(
                "Precio objetivo", value=float(r['precio_objetivo'] or 0),
                min_value=0.0, format="%.2f", key=f"obj_{row_id}"
            )
            opciones_carp = ["Sin carpeta"] + carpetas_existentes
            if r['carpeta'] and r['carpeta'] not in opciones_carp:
                opciones_carp.append(r['carpeta'])
            idx      = opciones_carp.index(r['carpeta']) if r['carpeta'] in opciones_carp else 0
            carp_sel = ec2.selectbox("Carpeta", opciones_carp, index=idx, key=f"carp_{row_id}")
            carp_new = st.text_input("Nueva carpeta", placeholder="Nombre…", key=f"carpnew_{row_id}")
            nueva_nota = st.text_input("Notas", value=r['notas'] or "", key=f"nota_{row_id}")

            ba, bb = st.columns(2)
            if ba.button("Guardar", key=f"save_{row_id}", use_container_width=True):
                carpeta_final = carp_new.strip() if carp_new.strip() else (
                    None if carp_sel == "Sin carpeta" else carp_sel
                )
                actualizar_watchlist(row_id, nuevo_obj, nueva_nota, carpeta_final, USER_ID)
                st.session_state.editando = None
                st.cache_data.clear()
                st.rerun()
            if bb.button("Cancelar", key=f"cancel_{row_id}", use_container_width=True):
                st.session_state.editando = None
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        # ── MODO VISUALIZACIÓN — card responsive ──────────────────
        else:
            ren = d.get('rend')
            pe  = d.get('pe')
            obj = r['precio_objetivo']

            # Distancia al objetivo
            dist_html = "—"
            if obj and float(obj) > 0 and precio > 0:
                dist      = ((float(obj) - precio) / precio) * 100
                d_color   = "#10b981" if dist > 0 else "#ef4444"
                d_sign    = "+" if dist > 0 else ""
                obj_str   = f"${float(obj):,.2f}"
                dist_html = (
                    f'<div style="color:#cbd5e1;font-family:JetBrains Mono,monospace;font-size:1rem">{obj_str}</div>'
                    f'<div style="color:{d_color};font-size:0.72rem;font-family:JetBrains Mono,monospace">{d_sign}{dist:.1f}% al obj.</div>'
                )
            else:
                dist_html = '<div style="color:#334155;font-size:0.88rem">—</div>'

            # Rendimiento 7d
            if ren is not None:
                r_color   = "#10b981" if ren >= 0 else "#ef4444"
                r_sign    = "+" if ren >= 0 else ""
                rend_html = f'<span style="color:{r_color};font-family:JetBrains Mono,monospace;font-size:0.85rem;font-weight:500">{r_sign}{ren:.2f}%</span>'
            else:
                rend_html = '<span style="color:#334155;font-size:0.82rem">N/A</span>'

            # Barra 52 semanas
            bar_html = ""
            if d.get('min52') and d.get('max52') and d['max52'] > d['min52'] and precio > 0:
                pct      = max(0, min(100, int(((precio - d['min52']) / (d['max52'] - d['min52'])) * 100)))
                bar_html = (
                    f'<div style="background:#1a2540;border-radius:3px;height:3px;margin:5px 0 2px">'
                    f'<div style="background:#10b981;width:{pct}%;height:3px;border-radius:3px"></div></div>'
                    f'<div style="display:flex;justify-content:space-between">'
                    f'<span style="color:#334155;font-size:0.6rem;font-family:JetBrains Mono,monospace">${d["min52"]:,.0f}</span>'
                    f'<span style="color:#334155;font-size:0.6rem;font-family:JetBrains Mono,monospace">${d["max52"]:,.0f}</span></div>'
                )

            notas_html = ""
            if r['notas']:
                notas_html = (
                    f'<div style="color:#e2e8f0;font-size:0.88rem;margin-top:8px;'
                    f'padding-top:8px;border-top:1px solid #1a2540">{r["notas"]}</div>'
                )

            pe_str = f"{pe:.1f}x" if pe else "N/A"

            # Build card HTML as a plain string (no f-string nesting issues)
            card = (
                '<div style="background:#0b1220;border:1px solid #1a2540;border-radius:12px;padding:14px 16px;margin:5px 0">'
                '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">'
                '<span style="color:#f1f5f9;font-family:JetBrains Mono,monospace;font-size:1.15rem;font-weight:700">' + str(r['ticker']) + '</span>'
                + rend_html +
                '</div>'
                '<div style="display:flex;gap:16px;flex-wrap:wrap">'
                '<div style="min-width:80px">'
                '<div style="color:#475569;font-size:0.72rem;text-transform:uppercase;letter-spacing:1px;font-family:JetBrains Mono,monospace;margin-bottom:4px">Precio</div>'
                '<div style="color:#f1f5f9;font-family:JetBrains Mono,monospace;font-size:1.15rem;font-weight:500">$' + f'{precio:,.2f}' + '</div>'
                + bar_html +
                '</div>'
                '<div style="min-width:80px">'
                '<div style="color:#475569;font-size:0.72rem;text-transform:uppercase;letter-spacing:1px;font-family:JetBrains Mono,monospace;margin-bottom:4px">Objetivo</div>'
                + dist_html +
                '</div>'
                '<div style="min-width:60px">'
                '<div style="color:#475569;font-size:0.72rem;text-transform:uppercase;letter-spacing:1px;font-family:JetBrains Mono,monospace;margin-bottom:4px">P/E</div>'
                '<div style="color:#94a3b8;font-family:JetBrains Mono,monospace;font-size:1.1rem">' + pe_str + '</div>'
                '</div>'
                '<div style="min-width:60px">'
                '<div style="color:#475569;font-size:0.72rem;text-transform:uppercase;letter-spacing:1px;font-family:JetBrains Mono,monospace;margin-bottom:4px">7d</div>'
                + rend_html +
                '</div>'
                '</div>'
                + notas_html +
                '</div>'
            )
            st.markdown(card, unsafe_allow_html=True)

            ba, bb, _ = st.columns([1, 1, 4])
            if ba.button("Editar", key=f"edit_{row_id}", use_container_width=True):
                st.session_state.editando = row_id
                st.rerun()
            if bb.button("Eliminar", key=f"del_{row_id}", use_container_width=True):
                eliminar_de_watchlist(row_id, USER_ID)
                st.cache_data.clear()
                st.rerun()