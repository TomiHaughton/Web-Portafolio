import streamlit as st
import psycopg2
import pandas as pd
import yfinance as yf

if 'user' not in st.session_state or st.session_state.user is None:
    st.error("Debes iniciar sesión."); st.stop()
USER_ID = st.session_state.user[0]

def conectar_db():
    return psycopg2.connect(
        host=st.secrets["connections"]["supabase"]["host"],
        database=st.secrets["connections"]["supabase"]["database"],
        user=st.secrets["connections"]["supabase"]["username"],
        password=st.secrets["connections"]["supabase"]["password"],
        port=st.secrets["connections"]["supabase"]["port"]
    )
def ver_operaciones(user_id):
    conn = conectar_db()
    df = pd.read_sql_query("SELECT * FROM operaciones WHERE user_id = %s ORDER BY fecha ASC", conn, params=(user_id,))
    conn.close()
    return df
@st.cache_data(ttl=3600)
def info_divs(tickers):
    d = {}
    for t in tickers:
        try:
            obj = yf.Ticker(t)
            info = obj.info
            rate = info.get('dividendRate', 0)
            rate = rate if rate else 0
            cal = obj.calendar
            ex = pd.to_datetime(cal.get('Ex-Dividend Date')).strftime('%Y-%m-%d') if cal and cal.get('Ex-Dividend Date') else "N/A"
            pay = pd.to_datetime(cal.get('Dividend Date')).strftime('%Y-%m-%d') if cal and cal.get('Dividend Date') else "N/A"
            d[t] = {'rate': rate, 'ex': ex, 'pay': pay}
        except: d[t] = {'rate':0, 'ex':'Err', 'pay':'Err'}
    return d

st.set_page_config(layout="wide", page_title="Dividendos")
st.title("Proyección Dividendos 📅")
ops = ver_operaciones(USER_ID)
if not ops.empty:
    ops['cant_neta'] = ops.apply(lambda x: x['cantidad'] if x['tipo']=='Compra' else -x['cantidad'], axis=1)
    pos = ops.groupby('ticker')['cant_neta'].sum().reset_index()
    pos = pos[pos['cant_neta']>0]
    if not pos.empty:
        inf = info_divs(pos['ticker'].tolist())
        div_df = pd.DataFrame.from_dict(inf, orient='index')
        res = pos.set_index('ticker').join(div_df).reset_index()
        res = res[res['rate']>0]
        if not res.empty:
            res['est_anual'] = res['cant_neta'] * res['rate']
            st.dataframe(res[['ticker','cant_neta','rate','est_anual','ex','pay']].rename(columns={'ticker':'Ticker','cant_neta':'Acciones','rate':'Div/Acc','est_anual':'Total Est.','ex':'Ex-Div','pay':'Pago'}), use_container_width=True)
            st.metric("Total Anual Estimado", f"${res['est_anual'].sum():,.2f}")
        else: st.info("Tus acciones no pagan dividendos.")
    else: st.info("Sin acciones.")
else: st.info("Sin datos.")