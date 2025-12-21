import streamlit as st
import psycopg2
import pandas as pd
import yfinance as yf

if 'user' not in st.session_state or st.session_state.user is None:
    st.error("Debes iniciar sesión.")
    st.stop()
USER_ID = st.session_state.user[0]

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
    else:
        cursor.execute("INSERT INTO watchlist (ticker, precio_objetivo, notas, user_id) VALUES (%s, %s, %s, %s)", (ticker, precio_objetivo, notas, user_id))
        conn.commit()
        conn.close()
        return True

def eliminar_de_watchlist(ticker_id, user_id):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM watchlist WHERE id = %s AND user_id = %s", (ticker_id, user_id))
    conn.commit()
    conn.close()

@st.cache_data(ttl=600)
def obtener_info_watchlist(tickers):
    info = {}
    for t in tickers:
        try:
            obj = yf.Ticker(t)
            dat = obj.info
            hist = obj.history(period="1mo")
            rend = ((hist['Close'][-1] - hist['Close'][-8]) / hist['Close'][-8] * 100) if len(hist)>7 else None
            info[t] = {'precio': dat.get('currentPrice', 0), 'pe': dat.get('trailingPE'), 'rend': rend, 'min52': dat.get('fiftyTwoWeekLow'), 'max52': dat.get('fiftyTwoWeekHigh')}
        except: info[t] = {'precio':0}
    return info

st.set_page_config(layout="wide", page_title="Watchlist")
st.title("Watchlist 🎯")
with st.form("wf", clear_on_submit=True):
    c1, c2, c3 = st.columns(3)
    tk = c1.text_input("Ticker")
    po = c2.number_input("Objetivo", min_value=0.0)
    nt = c3.text_input("Notas")
    if st.form_submit_button("Añadir"):
        if tk:
            tk_fin = tk.upper()
            criptos = ["BTC", "ETH", "SOL", "USDT", "BNB", "XRP", "ADA", "DOGE", "SHIB", "DOT", "DAI", "MATIC", "AVAX", "TRX", "LTC", "LINK", "ATOM", "UNI"]
            if tk_fin in criptos: tk_fin = f"{tk_fin}-USD"
            if anadir_a_watchlist(tk_fin, po, nt, USER_ID):
                st.success("Añadido.")
                st.rerun()

df = ver_watchlist(USER_ID)
if not df.empty:
    inf = obtener_info_watchlist(df['ticker'].tolist())
    cols = st.columns([1.5, 2, 1.5, 2, 1.5, 1.5, 1])
    headers = ["Ticker", "Precio/Rango 52sem", "Objetivo", "Notas", "P/E", "Rend 7d", "Acción"]
    for c, h in zip(cols, headers): c.markdown(f"**{h}**")
    st.divider()
    for i, r in df.iterrows():
        d = inf.get(r['ticker'], {})
        cols = st.columns([1.5, 2, 1.5, 2, 1.5, 1.5, 1])
        cols[0].write(r['ticker'])
        cols[1].write(f"${d.get('precio',0):,.2f}")
        if d.get('min52') and d.get('max52') and d['max52']>d['min52']:
            cols[1].progress(int(((d['precio']-d['min52'])/(d['max52']-d['min52']))*100))
        cols[2].write(f"${r['precio_objetivo']:,.2f}")
        cols[3].write(r['notas'])
        cols[4].write(f"{d.get('pe',0):.2f}x" if d.get('pe') else "N/A")
        ren = d.get('rend')
        if ren: cols[5].markdown(f"<span style='color:{'green' if ren>0 else 'red'}'>{ren:.2f}%</span>", unsafe_allow_html=True)
        else: cols[5].write("N/A")
        if cols[6].button("X", key=f"d{r['id']}"):
            eliminar_de_watchlist(r['id'], USER_ID)
            st.rerun()
else: st.info("Vacía.")