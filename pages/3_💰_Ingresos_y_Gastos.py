import streamlit as st
import sqlite3
import pandas as pd
from datetime import date
import plotly.express as px
import requests
import yfinance as yf

# --- VERIFICADOR DE SESIÓN ---
if 'user' not in st.session_state or st.session_state.user is None:
    st.error("Debes iniciar sesión para acceder a esta página.")
    st.stop()
USER_ID = st.session_state.user[0]
st.markdown("""<style>.stDataFrame th, .stDataFrame td {text-align: center;}</style>""", unsafe_allow_html=True)

# --- FUNCIONES ---
def conectar_db():
    return sqlite3.connect('portfolio.db')
def anadir_flujo(fecha, tipo, categoria, monto, descripcion, moneda, user_id):
    conexion = conectar_db()
    cursor = conexion.cursor()
    cursor.execute("INSERT INTO finanzas_personales (fecha, tipo, categoria, monto, descripcion, moneda, user_id) VALUES (?, ?, ?, ?, ?, ?, ?)", (fecha, tipo, categoria, monto, descripcion, moneda, user_id))
    conexion.commit()
    conexion.close()
def ver_flujos(user_id):
    conexion = conectar_db()
    df = pd.read_sql_query("SELECT * FROM finanzas_personales WHERE user_id = ? ORDER BY fecha DESC", conexion, params=(user_id,))
    conexion.close()
    return df
def eliminar_flujo(flujo_id, user_id):
    conexion = conectar_db()
    cursor = conexion.cursor()
    cursor.execute("DELETE FROM finanzas_personales WHERE id = ? AND user_id = ?", (flujo_id, user_id))
    conexion.commit()
    conexion.close()
def ver_categorias(user_id, tipo):
    conexion = conectar_db()
    df = pd.read_sql_query("SELECT * FROM categorias WHERE user_id = ? AND tipo = ?", conexion, params=(user_id, tipo))
    conexion.close()
    categorias_defecto = []
    if tipo == 'Ingreso':
        categorias_defecto = ["Sueldo", "Inversiones", "Dividendo Recibido", "Otros"]
    else:
        categorias_defecto = ["Alquiler", "Tarjeta de Crédito", "Inversiones", "Comida", "Ocio", "Otros"]
    nombres_categorias = categorias_defecto + df['nombre'].tolist()
    return nombres_categorias, df
def anadir_categoria(user_id, tipo, nombre):
    conexion = conectar_db()
    cursor = conexion.cursor()
    try:
        cursor.execute("INSERT INTO categorias (user_id, tipo, nombre) VALUES (?, ?, ?)", (user_id, tipo, nombre))
        conexion.commit()
        st.success(f"Categoría '{nombre}' añadida.")
    except sqlite3.IntegrityError:
        st.warning(f"La categoría '{nombre}' ya existe.")
    finally:
        conexion.close()
def eliminar_categoria(categoria_id, user_id):
    conexion = conectar_db()
    cursor = conexion.cursor()
    cursor.execute("DELETE FROM categorias WHERE id = ? AND user_id = ?", (categoria_id, user_id))
    conexion.commit()
    conexion.close()
@st.cache_data(ttl=300)
def obtener_dolar_blue_compartido():
    if 'precio_dolar_compartido' in st.session_state:
        return st.session_state['precio_dolar_compartido']
    else:
        try:
            resp = requests.get("https://dolarapi.com/v1/dolares/cripto", timeout=5)
            if resp.status_code == 200: return float(resp.json()['venta'])
        except: pass
        return 1150.0
def estilo_flujo(row):
    color = 'rgba(40, 167, 69, 0.4)' if row['Tipo'] == 'Ingreso' else 'rgba(220, 53, 69, 0.4)'
    return [f'background-color: {color}; color: #111;'] * len(row)

# --- INTERFAZ ---
st.set_page_config(layout="wide", page_title="Ingresos y Gastos")
st.title("Registro de Ingresos y Gastos 💸")

dolar_hoy = obtener_dolar_blue_compartido()
st.sidebar.markdown("---")
st.sidebar.metric("Cotización Dólar (Ref)", f"${dolar_hoy:,.0f} ARS")

with st.expander("Gestionar Mis Categorías"):
    st.subheader("Añadir Nueva Categoría")
    with st.form("categoria_form"):
        c1, c2 = st.columns([1, 2])
        tipo_cat = c1.selectbox("Tipo de Categoría", ["Ingreso", "Gasto"], key="cat_tipo")
        nombre_cat = c2.text_input("Nombre", key="cat_nombre")
        if st.form_submit_button("Añadir"):
            if nombre_cat: anadir_categoria(USER_ID, tipo_cat, nombre_cat)
            else: st.warning("Nombre vacío.")
    cat_tabs = st.tabs(["Ingresos", "Gastos"])
    with cat_tabs[0]:
        _, df_i = ver_categorias(USER_ID, "Ingreso")
        if not df_i.empty:
            for i, r in df_i.iterrows():
                cx, cy = st.columns([3, 1])
                cx.write(r['nombre'])
                if cy.button("Borrar", key=f"di_{r['id']}"):
                    eliminar_categoria(r['id'], USER_ID)
                    st.rerun()
    with cat_tabs[1]:
        _, df_g = ver_categorias(USER_ID, "Gasto")
        if not df_g.empty:
            for i, r in df_g.iterrows():
                cx, cy = st.columns([3, 1])
                cx.write(r['nombre'])
                if cy.button("Borrar", key=f"dg_{r['id']}"):
                    eliminar_categoria(r['id'], USER_ID)
                    st.rerun()

st.divider()

with st.form("flujo_form", clear_on_submit=True):
    st.subheader("Añadir Nuevo Movimiento")
    c1, c2, c3, c4, c5 = st.columns([1, 1, 1, 1.5, 2])
    fecha = c1.date_input("Fecha", value=date.today())
    tipo = c2.selectbox("Tipo", ["Ingreso", "Gasto"], key="tipo_flujo")
    moneda = c3.selectbox("Moneda", ["ARS", "USD"])
    cats_ing = ["Sueldo", "Inversiones", "Dividendo Recibido", "Otros"]
    cats_gas = ["Alquiler", "Tarjeta de Crédito", "Inversiones", "Comida", "Ocio", "Otros"]
    if 'tipo_flujo' in st.session_state and st.session_state.tipo_flujo == "Ingreso":
        lista, _ = ver_categorias(USER_ID, "Ingreso")
        categoria = c4.selectbox("Categoría", lista, key="cat_ingreso")
    else:
        lista, _ = ver_categorias(USER_ID, "Gasto")
        categoria = c4.selectbox("Categoría", lista, key="cat_gasto")
    monto = c5.number_input("Monto", min_value=0.0, step=0.01, format="%.2f")
    descripcion = st.text_input("Descripción")
    if st.form_submit_button("Guardar Movimiento"):
        if not categoria or monto <= 0: st.warning("Datos inc.")
        else:
            anadir_flujo(fecha, st.session_state.tipo_flujo, categoria, monto, descripcion, moneda, USER_ID)
            st.success("Guardado.")
            st.rerun()

flujos_df = ver_flujos(USER_ID)
st.header("Resumen Financiero (Visualización en USD)")

if not flujos_df.empty:
    if 'moneda' not in flujos_df.columns: flujos_df['moneda'] = 'ARS'
    flujos_df['monto_usd'] = flujos_df.apply(lambda x: x['monto'] if x['moneda'] == 'USD' else x['monto'] / dolar_hoy, axis=1)
    flujos_df['fecha'] = pd.to_datetime(flujos_df['fecha'])
    
    # --- Filtro Mes Actual ---
    hoy = pd.Timestamp.now()
    mask_mes_actual = (flujos_df['fecha'].dt.month == hoy.month) & (flujos_df['fecha'].dt.year == hoy.year)
    df_mes = flujos_df[mask_mes_actual]
    
    # 1. Métricas del Mes
    ingresos_mes = df_mes[df_mes['tipo'] == 'Ingreso']['monto_usd'].sum()
    
    gastos_brutos_mes = df_mes[df_mes['tipo'] == 'Gasto']['monto_usd'].sum()
    inversion_mes = df_mes[(df_mes['tipo'] == 'Gasto') & (df_mes['categoria'] == 'Inversiones')]['monto_usd'].sum()
    gastos_vida_mes = gastos_brutos_mes - inversion_mes
    
    # CORRECCIÓN: Definimos la variable correctamente
    enviado_inversion_mes = inversion_mes
    
    # 2. Métricas Históricas
    ingresos_hist = flujos_df[flujos_df['tipo'] == 'Ingreso']['monto_usd'].sum()
    gastos_brutos_hist = flujos_df[flujos_df['tipo'] == 'Gasto']['monto_usd'].sum()
    inversion_hist = flujos_df[(flujos_df['tipo'] == 'Gasto') & (flujos_df['categoria'] == 'Inversiones')]['monto_usd'].sum()
    
    gastos_vida_hist = gastos_brutos_hist - inversion_hist
    ahorro_neto_acumulado = ingresos_hist - gastos_vida_hist

    nombre_mes = hoy.strftime("%B")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"Ingresos ({nombre_mes})", f"US$ {ingresos_mes:,.2f}")
    c2.metric(f"Gastos Vida ({nombre_mes})", f"US$ {gastos_vida_mes:,.2f}")
    c3.metric(f"Inversión ({nombre_mes})", f"US$ {enviado_inversion_mes:,.2f}")
    c4.metric("Ahorro Total Acum.", f"US$ {ahorro_neto_acumulado:,.2f}")
    
    st.caption(f"*Valores convertidos a Dólar (${dolar_hoy:,.0f}). Las 3 primeras métricas se reinician cada mes.")

    st.divider()
    st.header("Flujo de Caja Mensual (Ingresos vs. Gastos Vida)")
    
    # Filtramos para el gráfico
    df_grafico = flujos_df[flujos_df['categoria'] != 'Inversiones'].copy()
    
    mensual = df_grafico.groupby([df_grafico['fecha'].dt.to_period('M'), 'tipo'])['monto_usd'].sum().unstack(fill_value=0).reset_index()
    mensual['fecha'] = mensual['fecha'].dt.to_timestamp()
    if 'Ingreso' not in mensual.columns: mensual['Ingreso'] = 0
    if 'Gasto' not in mensual.columns: mensual['Gasto'] = 0
    
    fig = px.bar(mensual, x='fecha', y=['Ingreso', 'Gasto'], barmode='group', title='Ingresos vs. Gastos de Vida por Mes')
    fig.update_xaxes(rangeslider_visible=True)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Sin movimientos.")

st.divider()
st.header("Historial General")
if not flujos_df.empty:
    df_show = flujos_df.rename(columns={'id':'ID', 'fecha':'Fecha', 'tipo':'Tipo', 'categoria':'Categoría', 'monto':'Monto', 'moneda':'Moneda', 'descripcion':'Descripción'})
    cols = st.columns([1, 1, 2, 1, 1.5, 2, 0.5])
    for c, h in zip(cols, ["Fecha", "Tipo", "Categoría", "Moneda", "Monto", "Descripción", "Acción"]): c.markdown(f"**{h}**")
    st.divider()
    for idx, row in df_show.iterrows():
        cols = st.columns([1, 1, 2, 1, 1.5, 2, 0.5])
        cols[0].write(row['Fecha'].strftime('%Y-%m-%d'))
        cols[1].write(row['Tipo'])
        cols[2].write(row['Categoría'])
        cols[3].write(row['Moneda'])
        cols[4].write(f"{row['Monto']:,.2f}")
        cols[5].write(row['Descripción'])
        if cols[6].button("🗑️", key=f"del_f_{row['ID']}"):
            eliminar_flujo(row['ID'], USER_ID)
            st.rerun()

st.divider()
st.header("Historial de Dividendos Cobrados")
if not flujos_df.empty:
    divs = flujos_df[(flujos_df['tipo'] == 'Ingreso') & (flujos_df['categoria'] == 'Dividendo Recibido')]
    if not divs.empty:
        st.dataframe(divs[['fecha', 'monto_usd', 'descripcion']].rename(columns={'fecha':'Fecha', 'monto_usd':'Monto (USD Est.)'}), use_container_width=True)
    else: st.info("Sin dividendos cobrados.")
else: st.info("Sin datos.")