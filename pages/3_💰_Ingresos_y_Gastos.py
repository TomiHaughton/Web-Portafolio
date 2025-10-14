import streamlit as st
import sqlite3
import pandas as pd
from datetime import date
import plotly.express as px

# --- VERIFICADOR DE SESIÓN ---
if 'user' not in st.session_state or st.session_state.user is None:
    st.error("Debes iniciar sesión para acceder a esta página.")
    st.stop()

USER_ID = st.session_state.user[0]

# --- INYECCIÓN DE CSS (sin cambios) ---
st.markdown("""
<style>
.stDataFrame th { text-align: center; }
.stDataFrame td { text-align: center; }
</style>
""", unsafe_allow_html=True)

# --- FUNCIONES (ACTUALIZADAS PARA USAR user_id) ---
def conectar_db():
    return sqlite3.connect('portfolio.db')

def anadir_flujo(fecha, tipo, categoria, monto, descripcion, user_id):
    conexion = conectar_db()
    cursor = conexion.cursor()
    cursor.execute("INSERT INTO finanzas_personales (fecha, tipo, categoria, monto, descripcion, user_id) VALUES (?, ?, ?, ?, ?, ?)", (fecha, tipo, categoria, monto, descripcion, user_id))
    conexion.commit()
    conexion.close()

def ver_flujos(user_id):
    conexion = conectar_db()
    df = pd.read_sql_query("SELECT * FROM finanzas_personales WHERE user_id = ? ORDER BY fecha DESC", conexion, params=(user_id,))
    conexion.close()
    return df

def estilo_flujo(row):
    color = 'rgba(40, 167, 69, 0.4)' if row['Tipo'] == 'Ingreso' else 'rgba(220, 53, 69, 0.4)'
    return [f'background-color: {color}; color: #111;'] * len(row)

# --- INTERFAZ DE LA PÁGINA ---
st.set_page_config(layout="wide", page_title="Ingresos y Gastos")
st.title("Registro de Ingresos y Gastos 💸")

with st.form("flujo_form", clear_on_submit=True):
    st.subheader("Añadir Nuevo Movimiento")
    cols = st.columns(5)
    fecha = cols[0].date_input("Fecha", value=date.today())
    tipo = cols[1].selectbox("Tipo", ["Ingreso", "Gasto"], key="tipo_flujo")
    categorias_ingreso = ["Sueldo", "Inversiones", "Otros"]
    categorias_gasto = ["Alquiler", "Tarjeta de Crédito", "Inversiones", "Comida", "Ocio", "Otros"]
    if 'tipo_flujo' in st.session_state and st.session_state.tipo_flujo == "Ingreso":
        categoria = cols[2].selectbox("Categoría", categorias_ingreso, key="cat_ingreso")
    else:
        categoria = cols[2].selectbox("Categoría", categorias_gasto, key="cat_gasto")
    monto = cols[3].number_input("Monto", min_value=0.0, step=0.01, format="%.2f")
    descripcion = cols[4].text_input("Descripción")
    submitted = st.form_submit_button("Guardar Movimiento")
    if submitted:
        if not categoria or monto <= 0:
            st.warning("Por favor, completa la categoría y el monto.")
        else:
            # ACTUALIZADO: Pasamos el USER_ID
            anadir_flujo(fecha, st.session_state.tipo_flujo, categoria, monto, descripcion, USER_ID)
            st.success("Movimiento guardado con éxito.")
            st.rerun()

# ACTUALIZADO: Pasamos el USER_ID
flujos_df = ver_flujos(USER_ID)

st.header("Resumen Financiero")
if not flujos_df.empty:
    total_ingresos = flujos_df[flujos_df['tipo'] == 'Ingreso']['monto'].sum()
    total_gastos = flujos_df[flujos_df['tipo'] == 'Gasto']['monto'].sum()
    ahorro_neto = total_ingresos - total_gastos
    cols_summary = st.columns(3)
    cols_summary[0].metric("Total Ingresos", f"${total_ingresos:,.2f}")
    cols_summary[1].metric("Total Gastos", f"${total_gastos:,.2f}")
    cols_summary[2].metric("Ahorro Neto", f"${ahorro_neto:,.2f}", delta=f"{ahorro_neto:,.2f}")
    st.divider()
    st.header("Flujo de Caja Mensual")
    flujos_df['fecha'] = pd.to_datetime(flujos_df['fecha'])
    flujo_mensual = flujos_df.groupby([flujos_df['fecha'].dt.to_period('M'), 'tipo'])['monto'].sum().unstack(fill_value=0).reset_index()
    flujo_mensual['fecha'] = flujo_mensual['fecha'].dt.to_timestamp()
    fig_flujo_mensual = px.bar(flujo_mensual, x='fecha', y=['Ingreso', 'Gasto'], barmode='group', title='Ingresos vs. Gastos por Mes', labels={'fecha': 'Mes'})
    st.plotly_chart(fig_flujo_mensual, use_container_width=True)
else:
    st.info("Aún no hay movimientos registrados para mostrar un resumen.")

st.divider()
st.header("Historial de Movimientos")
if not flujos_df.empty:
    df_historial_finanzas = flujos_df.rename(columns={'id': 'ID', 'fecha': 'Fecha', 'tipo': 'Tipo', 'categoria': 'Categoría', 'monto': 'Monto', 'descripcion': 'Descripción'})
    st.dataframe(
        df_historial_finanzas.style.apply(estilo_flujo, axis=1),
        use_container_width=True
    )
else:
    st.info("No hay movimientos para mostrar.")