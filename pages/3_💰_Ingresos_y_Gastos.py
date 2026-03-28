import streamlit as st
import psycopg2
import pandas as pd
from datetime import date
import plotly.express as px
import requests

if 'user' not in st.session_state or st.session_state.user is None:
    st.error("Debes iniciar sesión.")
    st.stop()
USER_ID = st.session_state.user[0]
st.markdown("""<style>.stDataFrame th, .stDataFrame td {text-align: center;}</style>""", unsafe_allow_html=True)

def conectar_db():
    return psycopg2.connect(
        host=st.secrets["connections"]["supabase"]["host"],
        database=st.secrets["connections"]["supabase"]["database"],
        user=st.secrets["connections"]["supabase"]["username"],
        password=st.secrets["connections"]["supabase"]["password"],
        port=st.secrets["connections"]["supabase"]["port"]
    )
def anadir_flujo(fecha, tipo, categoria, monto, descripcion, moneda, user_id):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO finanzas_personales (fecha, tipo, categoria, monto, descripcion, moneda, user_id) VALUES (%s, %s, %s, %s, %s, %s, %s)", (fecha, tipo, categoria, monto, descripcion, moneda, user_id))
    conn.commit()
    conn.close()
def ver_flujos(user_id):
    conn = conectar_db()
    df = pd.read_sql_query("SELECT * FROM finanzas_personales WHERE user_id = %s ORDER BY fecha DESC", conn, params=(user_id,))
    conn.close()
    return df
def eliminar_flujo(flujo_id, user_id):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM finanzas_personales WHERE id = %s AND user_id = %s", (flujo_id, user_id))
    conn.commit()
    conn.close()
def ver_categorias(user_id, tipo):
    conn = conectar_db()
    df = pd.read_sql_query("SELECT * FROM categorias WHERE user_id = %s AND tipo = %s", conn, params=(user_id, tipo))
    conn.close()
    cats = ["Sueldo", "Inversiones", "Dividendo Recibido", "Otros"] if tipo == 'Ingreso' else ["Alquiler", "Tarjeta de Crédito", "Inversiones", "Comida", "Ocio", "Otros"]
    return cats + df['nombre'].tolist(), df
def anadir_categoria(user_id, tipo, nombre):
    conn = conectar_db()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO categorias (user_id, tipo, nombre) VALUES (%s, %s, %s)", (user_id, tipo, nombre))
        conn.commit()
        st.success("Añadida.")
    except: st.warning("Ya existe.")
    finally: conn.close()
def eliminar_categoria(id_cat, user_id):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM categorias WHERE id = %s AND user_id = %s", (id_cat, user_id))
    conn.commit()
    conn.close()

@st.cache_data(ttl=300)
def obtener_dolar():
    if 'precio_dolar_compartido' in st.session_state: return st.session_state['precio_dolar_compartido']
    try: 
        r = requests.get("https://dolarapi.com/v1/dolares/cripto", timeout=5)
        if r.status_code == 200: return float(r.json()['venta'])
    except: pass
    return 1150.0

def estilo(row):
    c = 'rgba(40, 167, 69, 0.4)' if row['Tipo'] == 'Ingreso' else 'rgba(220, 53, 69, 0.4)'
    return [f'background-color: {c}; color: #111;'] * len(row)

st.set_page_config(layout="wide", page_title="Ingresos")
st.title("Ingresos y Gastos 💸")
dolar = obtener_dolar()
st.sidebar.metric("Dólar Ref", f"${dolar:,.0f}")

with st.expander("Categorías"):
    with st.form("fc"):
        c1, c2 = st.columns([1, 2])
        tc = c1.selectbox("Tipo", ["Ingreso", "Gasto"])
        nc = c2.text_input("Nombre")
        if st.form_submit_button("Añadir") and nc: anadir_categoria(USER_ID, tc, nc)
    t1, t2 = st.tabs(["Ingresos", "Gastos"])
    with t1:
        _, df = ver_categorias(USER_ID, "Ingreso")
        for i,r in df.iterrows():
            c1, c2 = st.columns([3,1])
            c1.write(r['nombre'])
            if c2.button("X", key=f"ci{r['id']}"): eliminar_categoria(r['id'], USER_ID); st.rerun()
    with t2:
        _, df = ver_categorias(USER_ID, "Gasto")
        for i,r in df.iterrows():
            c1, c2 = st.columns([3,1])
            c1.write(r['nombre'])
            if c2.button("X", key=f"cg{r['id']}"): eliminar_categoria(r['id'], USER_ID); st.rerun()

st.divider()
with st.form("ff", clear_on_submit=True):
    st.subheader("Nuevo Movimiento")
    c1, c2, c3, c4, c5 = st.columns([1,1,1,1.5,2])
    fe = c1.date_input("Fecha", value=date.today())
    ti = c2.selectbox("Tipo", ["Ingreso", "Gasto"], key="tf")
    mo = c3.selectbox("Moneda", ["ARS", "USD"])
    lst, _ = ver_categorias(USER_ID, ti)
    ca = c4.selectbox("Categoría", lst)
    mt = c5.number_input("Monto", min_value=0.0, step=0.01, format="%.4f")
    de = st.text_input("Desc")
    if st.form_submit_button("Guardar") and mt > 0:
        anadir_flujo(fe, ti, ca, mt, de, mo, USER_ID); st.success("Listo"); st.rerun()

df = ver_flujos(USER_ID)
st.header("Resumen (USD)")
if not df.empty:
    if 'moneda' not in df.columns: df['moneda'] = 'ARS'
    df['monto_usd'] = df.apply(lambda x: x['monto'] if x['moneda']=='USD' else x['monto']/dolar, axis=1)
    df['fecha'] = pd.to_datetime(df['fecha'])
    hoy = pd.Timestamp.now()
    df_mes = df[(df['fecha'].dt.month == hoy.month) & (df['fecha'].dt.year == hoy.year)]
    
    ing_mes = df_mes[df_mes['tipo']=='Ingreso']['monto_usd'].sum()
    gas_mes = df_mes[df_mes['tipo']=='Gasto']['monto_usd'].sum()
    inv_mes = df_mes[(df_mes['tipo']=='Gasto')&(df_mes['categoria']=='Inversiones')]['monto_usd'].sum()
    vid_mes = gas_mes - inv_mes
    
    ing_hist = df[df['tipo']=='Ingreso']['monto_usd'].sum()
    gas_hist = df[df['tipo']=='Gasto']['monto_usd'].sum()
    inv_hist = df[(df['tipo']=='Gasto')&(df['categoria']=='Inversiones')]['monto_usd'].sum()
    ahorro = ing_hist - (gas_hist - inv_hist)
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Ingresos Mes", f"US$ {ing_mes:,.2f}")
    c2.metric("Vida Mes", f"US$ {vid_mes:,.2f}")
    c3.metric("Inv. Mes", f"US$ {inv_mes:,.2f}")
    c4.metric("Ahorro Hist.", f"US$ {ahorro:,.2f}")
    
    dfg = df[df['categoria']!='Inversiones'].copy()
    if not dfg.empty:
        men = dfg.groupby([dfg['fecha'].dt.to_period('M'), 'tipo'])['monto_usd'].sum().reset_index()
        men['fecha'] = men['fecha'].dt.to_timestamp()
        st.plotly_chart(px.bar(men, x='fecha', y='monto_usd', color='tipo', barmode='group'), use_container_width=True)

st.divider()
st.header("Historial")
if not df.empty:
    dfs = df.rename(columns={'id':'ID','fecha':'Fecha','tipo':'Tipo','categoria':'Categoría','monto':'Monto','moneda':'Moneda','descripcion':'Desc'})
    cols = st.columns([1,1,2,1,1.5,2,0.5])
    for c,h in zip(cols, ["Fecha","Tipo","Cat","Mon","Monto","Desc","Acc"]): c.markdown(f"**{h}**")
    st.divider()
    for i,r in dfs.iterrows():
        cols = st.columns([1,1,2,1,1.5,2,0.5])
        cols[0].write(r['Fecha'].strftime('%Y-%m-%d'))
        cols[1].write(r['Tipo'])
        cols[2].write(r['Categoría'])
        cols[3].write(r['Moneda'])
        cols[4].write(f"{r['Monto']:,.2f}")
        cols[5].write(r['Desc'])
        if cols[6].button("🗑️", key=f"del{r['ID']}"): eliminar_flujo(r['ID'], USER_ID); st.rerun()

st.divider()
st.header("Dividendos Cobrados")
if not df.empty:
    divs = df[(df['tipo']=='Ingreso')&(df['categoria']=='Dividendo Recibido')]
    if not divs.empty: st.dataframe(divs[['fecha','monto_usd','descripcion']], use_container_width=True)
    else: st.info("0 dividendos.")