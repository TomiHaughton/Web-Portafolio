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

# *** AUTO-MIGRACIÓN (Seguridad) ***
def verificar_y_migrar_finanzas():
    conexion = conectar_db()
    cursor = conexion.cursor()
    try:
        cursor.execute("SELECT moneda FROM finanzas_personales LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE finanzas_personales ADD COLUMN moneda TEXT DEFAULT 'ARS'")
        conexion.commit()
    finally:
        conexion.close()

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
def obtener_dolar_blue():
    # Usamos la misma lógica que en el dashboard para consistencia
    precio = 1150.0
    try:
        response = requests.get("https://dolarapi.com/v1/dolares/blue", timeout=5)
        if response.status_code == 200:
            data = response.json()
            precio = float(data['venta'])
    except:
        try:
            ticker = yf.Ticker("ARS=X")
            hist = ticker.history(period="1d")
            if not hist.empty: precio = hist['Close'].iloc[-1]
        except: pass
    return precio

def estilo_flujo(row):
    color = 'rgba(40, 167, 69, 0.4)' if row['Tipo'] == 'Ingreso' else 'rgba(220, 53, 69, 0.4)'
    return [f'background-color: {color}; color: #111;'] * len(row)

# --- INTERFAZ ---
st.set_page_config(layout="wide", page_title="Ingresos y Gastos")
st.title("Registro de Ingresos y Gastos 💸")

verificar_y_migrar_finanzas()
dolar_hoy = obtener_dolar_blue()

with st.expander("Gestionar Mis Categorías"):
    st.subheader("Añadir Nueva Categoría")
    with st.form("categoria_form"):
        cat_col1, cat_col2 = st.columns([1, 2])
        tipo_cat = cat_col1.selectbox("Tipo de Categoría", ["Ingreso", "Gasto"], key="cat_tipo")
        nombre_cat = cat_col2.text_input("Nombre de la Nueva Categoría", key="cat_nombre")
        if st.form_submit_button("Añadir Categoría"):
            if nombre_cat: anadir_categoria(USER_ID, tipo_cat, nombre_cat)
            else: st.warning("Nombre vacío.")
    st.subheader("Categorías Personalizadas")
    cat_tabs = st.tabs(["Ingresos", "Gastos"])
    with cat_tabs[0]:
        _, cat_df_ing = ver_categorias(USER_ID, "Ingreso")
        if not cat_df_ing.empty:
            for i, r in cat_df_ing.iterrows():
                c1, c2 = st.columns([3, 1])
                c1.write(r['nombre'])
                if c2.button("Eliminar", key=f"dci_{r['id']}"):
                    eliminar_categoria(r['id'], USER_ID)
                    st.rerun()
    with cat_tabs[1]:
        _, cat_df_gas = ver_categorias(USER_ID, "Gasto")
        if not cat_df_gas.empty:
            for i, r in cat_df_gas.iterrows():
                c1, c2 = st.columns([3, 1])
                c1.write(r['nombre'])
                if c2.button("Eliminar", key=f"dcg_{r['id']}"):
                    eliminar_categoria(r['id'], USER_ID)
                    st.rerun()

st.divider()

with st.form("flujo_form", clear_on_submit=True):
    st.subheader("Añadir Nuevo Movimiento")
    c1, c2, c3, c4, c5 = st.columns([1, 1, 1, 1.5, 2])
    fecha = c1.date_input("Fecha", value=date.today())
    tipo = c2.selectbox("Tipo", ["Ingreso", "Gasto"], key="tipo_flujo")
    
    # Moneda
    moneda = c3.selectbox("Moneda", ["ARS", "USD"])
    
    cats_ing = ["Sueldo", "Inversiones", "Dividendo Recibido", "Otros"]
    cats_gas = ["Alquiler", "Tarjeta de Crédito", "Inversiones", "Comida", "Ocio", "Otros"]
    
    if 'tipo_flujo' in st.session_state and st.session_state.tipo_flujo == "Ingreso":
        lista_cats, _ = ver_categorias(USER_ID, "Ingreso")
        categoria = c4.selectbox("Categoría", lista_cats, key="cat_ingreso")
    else:
        lista_cats, _ = ver_categorias(USER_ID, "Gasto")
        categoria = c4.selectbox("Categoría", lista_cats, key="cat_gasto")
        
    monto = c5.number_input("Monto", min_value=0.0, step=0.01, format="%.2f")
    descripcion = st.text_input("Descripción")
    
    if st.form_submit_button("Guardar Movimiento"):
        if not categoria or monto <= 0:
            st.warning("Datos incompletos.")
        else:
            anadir_flujo(fecha, st.session_state.tipo_flujo, categoria, monto, descripcion, moneda, USER_ID)
            st.success("Guardado.")
            st.rerun()

flujos_df = ver_flujos(USER_ID)
st.header("Resumen Financiero (Visualización en USD)")
if not flujos_df.empty:
    # Normalización a USD para visualización coherente
    if 'moneda' not in flujos_df.columns: flujos_df['moneda'] = 'ARS'
    
    flujos_df['monto_usd'] = flujos_df.apply(
        lambda x: x['monto'] if x['moneda'] == 'USD' else x['monto'] / dolar_hoy, axis=1
    )

    total_ingresos = flujos_df[flujos_df['tipo'] == 'Ingreso']['monto_usd'].sum()
    total_gastos = flujos_df[flujos_df['tipo'] == 'Gasto']['monto_usd'].sum()
    ahorro_neto = total_ingresos - total_gastos
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Ingresos", f"US$ {total_ingresos:,.2f}")
    c2.metric("Total Gastos", f"US$ {total_gastos:,.2f}")
    c3.metric("Ahorro Neto", f"US$ {ahorro_neto:,.2f}", delta=f"{ahorro_neto:,.2f}")
    
    st.caption(f"*Valores en Pesos convertidos a Dólar Blue aprox. (${dolar_hoy:,.0f}) para el resumen.")

    st.divider()
    st.header("Flujo de Caja Mensual (USD)")
    flujos_df['fecha'] = pd.to_datetime(flujos_df['fecha'])
    # Usamos monto_usd para el gráfico
    mensual = flujos_df.groupby([flujos_df['fecha'].dt.to_period('M'), 'tipo'])['monto_usd'].sum().unstack(fill_value=0).reset_index()
    mensual['fecha'] = mensual['fecha'].dt.to_timestamp()
    if 'Ingreso' not in mensual.columns: mensual['Ingreso'] = 0
    if 'Gasto' not in mensual.columns: mensual['Gasto'] = 0
    
    fig = px.bar(mensual, x='fecha', y=['Ingreso', 'Gasto'], barmode='group', title='Evolución Mensual en Dólares')
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Sin movimientos.")

st.divider()
st.header("Historial General")
if not flujos_df.empty:
    # Mostramos la tabla con la moneda original
    df_show = flujos_df.rename(columns={'id':'ID', 'fecha':'Fecha', 'tipo':'Tipo', 'categoria':'Categoría', 'monto':'Monto', 'moneda':'Moneda', 'descripcion':'Descripción'})
    
    # Creamos tabla manual para incluir el botón
    col_widths = [1, 1, 2, 1, 1.5, 2, 0.5]
    cols = st.columns(col_widths)
    headers = ["Fecha", "Tipo", "Categoría", "Moneda", "Monto", "Descripción", "Acción"]
    for c, h in zip(cols, headers): c.markdown(f"**{h}**")
    st.divider()
    
    for idx, row in df_show.iterrows():
        cols = st.columns(col_widths)
        cols[0].write(row['Fecha'].strftime('%Y-%m-%d'))
        cols[1].write(row['Tipo'])
        cols[2].write(row['Categoría'])
        cols[3].write(row['Moneda'])
        cols[4].write(f"{row['Monto']:,.2f}")
        cols[5].write(row['Descripción'])
        if cols[6].button("🗑️", key=f"del_f_{row['ID']}"):
            eliminar_flujo(row['ID'], USER_ID)
            st.rerun()