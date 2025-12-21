import streamlit as st
import psycopg2
import pandas as pd
import yfinance as yf
import plotly.express as px

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
@st.cache_data(ttl=600)
def obtener_precios(tickers):
    if not tickers: return {}
    try: return yf.Tickers(tickers).history(period='1d')['Close'].iloc[-1].to_dict()
    except: return {}
def calcular(df_ops):
    if df_ops.empty: return pd.DataFrame(), pd.DataFrame()
    df = df_ops.copy()
    if 'moneda' not in df.columns: df['moneda'] = 'USD'
    df['cantidad_neta'] = df.apply(lambda x: x['cantidad'] if x['tipo']=='Compra' else -x['cantidad'], axis=1)
    df['coste'] = df['cantidad'] * df['precio']
    df['ingreso'] = df['cantidad'] * df['precio']
    pos = df.groupby(['ticker', 'moneda']).agg(
        cant=('cantidad_neta', 'sum'),
        coste_compras=('coste', lambda x: x[df.loc[x.index,'tipo']=='Compra'].sum()),
        cant_compras=('cantidad', lambda x: x[df.loc[x.index,'tipo']=='Compra'].sum()),
        total_ventas=('ingreso', lambda x: x[df.loc[x.index,'tipo']=='Venta'].sum()),
        cant_ventas=('cantidad', lambda x: x[df.loc[x.index,'tipo']=='Venta'].sum())
    ).reset_index()
    pos['ppp'] = pos.apply(lambda x: x['coste_compras']/x['cant_compras'] if x['cant_compras']>0 else 0, axis=1)
    pos['realizado'] = pos['total_ventas'] - (pos['ppp']*pos['cant_ventas'])
    abiertas = pos[pos['cant']>0.000001].copy()
    if not abiertas.empty:
        precios = obtener_precios(abiertas['ticker'].unique().tolist())
        abiertas['precio'] = abiertas['ticker'].map(precios).fillna(0)
        abiertas['valor_usd'] = abiertas.apply(lambda x: (x['cant']*x['precio']) if x['moneda']=='USD' or x['precio']==0 else (x['cant']*x['precio'])/1150, axis=1) # Simplificado USD
        abiertas['coste_usd'] = abiertas.apply(lambda x: (x['cant']*x['ppp']) if x['moneda']=='USD' else (x['cant']*x['ppp'])/1150, axis=1)
        abiertas['ganancia_no_real'] = abiertas['valor_usd'] - abiertas['coste_usd']
    return abiertas, pos[['ticker', 'realizado']]

st.set_page_config(layout="wide", page_title="Análisis")
st.title("Análisis Gráfico 📉")
ops = ver_operaciones(USER_ID)
abiertas, realizadas = calcular(ops)

if not ops.empty:
    c1, c2 = st.columns(2)
    with c1:
        st.header("No Realizado")
        if not abiertas.empty: st.plotly_chart(px.bar(abiertas, x='ticker', y='ganancia_no_real', color='ganancia_no_real', color_continuous_scale=px.colors.diverging.RdYlGn, color_continuous_midpoint=0), use_container_width=True)
        else: st.info("Sin posiciones.")
    with c2:
        st.header("Realizado (Cerrado)")
        real = realizadas[realizadas['realizado']!=0]
        if not real.empty: st.plotly_chart(px.bar(real, x='ticker', y='realizado', color='realizado', color_continuous_scale=px.colors.diverging.RdYlGn, color_continuous_midpoint=0), use_container_width=True)
        else: st.info("Sin ventas.")
    st.divider()
    st.header("Coste vs Valor")
    if not abiertas.empty:
        melt = abiertas.melt(id_vars=['ticker'], value_vars=['coste_usd', 'valor_usd'], var_name='Métrica', value_name='Valor')
        st.plotly_chart(px.bar(melt, x='ticker', y='Valor', color='Métrica', barmode='group'), use_container_width=True)
else: st.info("Sin datos.")