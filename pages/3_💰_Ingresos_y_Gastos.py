import streamlit as st
import sqlite3
import pandas as pd
from datetime import date
import plotly.express as px

# --- VERIFICADOR DE SESIÓN y CSS (sin cambios) ---
if 'user' not in st.session_state or st.session_state.user is None:
    st.error("Debes iniciar sesión para acceder a esta página.")
    st.stop()
USER_ID = st.session_state.user[0]
st.markdown("""<style>.stDataFrame th, .stDataFrame td {text-align: center;}</style>""", unsafe_allow_html=True)

# --- FUNCIONES (sin cambios) ---
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

# --- INTERFAZ DE LA PÁGINA ---
st.set_page_config(layout="wide", page_title="Ingresos y Gastos")
st.title("Registro de Ingresos y Gastos 💸")

with st.expander("Gestionar Mis Categorías"):
    # ... (código de gestión de categorías sin cambios) ...
    st.subheader("Añadir Nueva Categoría")
    with st.form("categoria_form"):
        cat_col1, cat_col2 = st.columns([1, 2])
        tipo_cat = cat_col1.selectbox("Tipo de Categoría", ["Ingreso", "Gasto"], key="cat_tipo")
        nombre_cat = cat_col2.text_input("Nombre de la Nueva Categoría", key="cat_nombre")
        cat_submitted = st.form_submit_button("Añadir Categoría")
        if cat_submitted:
            if nombre_cat:
                anadir_categoria(USER_ID, tipo_cat, nombre_cat)
            else:
                st.warning("El nombre de la categoría no puede estar vacío.")
    st.subheader("Categorías Personalizadas")
    cat_tabs = st.tabs(["Ingresos", "Gastos"])
    with cat_tabs[0]:
        _, categorias_df_ingreso = ver_categorias(USER_ID, "Ingreso")
        if not categorias_df_ingreso.empty:
            for index, row in categorias_df_ingreso.iterrows():
                col1, col2 = st.columns([3, 1])
                col1.write(row['nombre'])
                if col2.button("Eliminar", key=f"del_cat_ing_{row['id']}"):
                    eliminar_categoria(row['id'], USER_ID)
                    st.rerun()
        else:
            st.info("No tienes categorías de ingreso personalizadas.")
    with cat_tabs[1]:
        _, categorias_df_gasto = ver_categorias(USER_ID, "Gasto")
        if not categorias_df_gasto.empty:
            for index, row in categorias_df_gasto.iterrows():
                col1, col2 = st.columns([3, 1])
                col1.write(row['nombre'])
                if col2.button("Eliminar", key=f"del_cat_gas_{row['id']}"):
                    eliminar_categoria(row['id'], USER_ID)
                    st.rerun()
        else:
            st.info("No tienes categorías de gasto personalizadas.")

with st.form("flujo_form", clear_on_submit=True):
    st.subheader("Añadir Nuevo Movimiento")
    cols = st.columns(5)
    fecha = cols[0].date_input("Fecha", value=date.today())
    tipo = cols[1].selectbox("Tipo", ["Ingreso", "Gasto"], key="tipo_flujo")
    if 'tipo_flujo' in st.session_state and st.session_state.tipo_flujo == "Ingreso":
        lista_categorias, _ = ver_categorias(USER_ID, "Ingreso")
        categoria = cols[2].selectbox("Categoría", lista_categorias, key="cat_ingreso")
    else:
        lista_categorias, _ = ver_categorias(USER_ID, "Gasto")
        categoria = cols[2].selectbox("Categoría", lista_categorias, key="cat_gasto")
    
    # *** CAMBIO: Aumentamos la precisión a 4 decimales ***
    monto = cols[3].number_input("Monto", min_value=0.0, step=0.0001, format="%.4f")
    descripcion = cols[4].text_input("Descripción", help="Para dividendos, puedes poner el ticker aquí.")
    submitted = st.form_submit_button("Guardar Movimiento")
    if submitted:
        if not categoria or monto <= 0:
            st.warning("Por favor, completa la categoría y el monto.")
        else:
            anadir_flujo(fecha, st.session_state.tipo_flujo, categoria, monto, descripcion, USER_ID)
            st.success("Movimiento guardado con éxito.")
            st.rerun()

flujos_df = ver_flujos(USER_ID)
st.header("Resumen Financiero")
if not flujos_df.empty:
    # ... (código del resumen y gráfico sin cambios) ...
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
    flujo_mensual_grouped = flujos_df.groupby([flujos_df['fecha'].dt.to_period('M'), 'tipo'])['monto'].sum()
    flujo_mensual = flujo_mensual_grouped.unstack(fill_value=0).reset_index()
    flujo_mensual['fecha'] = flujo_mensual['fecha'].dt.to_timestamp()
    if 'Ingreso' not in flujo_mensual.columns: flujo_mensual['Ingreso'] = 0
    if 'Gasto' not in flujo_mensual.columns: flujo_mensual['Gasto'] = 0
    fig_flujo_mensual = px.bar(flujo_mensual, x='fecha', y=['Ingreso', 'Gasto'], barmode='group', title='Ingresos vs. Gastos por Mes', labels={'fecha': 'Mes', 'value': 'Monto ($)', 'variable': 'Tipo'})
    st.plotly_chart(fig_flujo_mensual, use_container_width=True)
else:
    st.info("Aún no hay movimientos registrados para mostrar un resumen.")

st.divider()
st.header("Historial General de Movimientos")
if not flujos_df.empty:
    df_historial_finanzas = flujos_df.rename(columns={'id': 'ID', 'fecha': 'Fecha', 'tipo': 'Tipo', 'categoria': 'Categoría', 'monto': 'Monto', 'descripcion': 'Descripción'})
    column_widths = [1, 2, 2, 2, 2, 1]
    cols = st.columns(column_widths)
    headers = ["Fecha", "Tipo", "Categoría", "Monto", "Descripción", "Acción"]
    for col, header in zip(cols, headers):
        col.markdown(f"**{header}**")
    st.divider()
    for index, row in df_historial_finanzas.iterrows():
        cols = st.columns(column_widths)
        cols[0].write(row['Fecha'])
        cols[1].write(row['Tipo'])
        cols[2].write(row['Categoría'])
        cols[3].write(f"${row['Monto']:,.4f}") # Mostramos 4 decimales
        cols[4].write(row['Descripción'])
        if cols[5].button("🗑️", key=f"del_flujo_{row['ID']}"):
            eliminar_flujo(row['ID'], USER_ID)
            st.rerun()
else:
    st.info("No hay movimientos para mostrar.")

st.divider()
st.header("Historial de Dividendos Cobrados")
if not flujos_df.empty:
    dividendos_cobrados_df = flujos_df[(flujos_df['tipo'] == 'Ingreso') & (flujos_df['categoria'] == 'Dividendo Recibido')].copy()
    if not dividendos_cobrados_df.empty:
        df_hist_divs = dividendos_cobrados_df.rename(columns={'id': 'ID', 'fecha': 'Fecha', 'monto': 'Monto Cobrado', 'descripcion': 'Ticker/Descripción'})
        st.dataframe(df_hist_divs[['Fecha', 'Monto Cobrado', 'Ticker/Descripción']], use_container_width=True)
        total_dividendos_cobrados = dividendos_cobrados_df['monto'].sum()
        st.metric("Total de Dividendos Cobrados Registrados", f"${total_dividendos_cobrados:,.2f}")
    else:
        st.info("No has registrado ningún dividendo cobrado.")
else:
    st.info("No hay movimientos registrados.")