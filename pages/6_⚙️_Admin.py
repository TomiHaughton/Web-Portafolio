import streamlit as st
import sqlite3
import pandas as pd

# --- VERIFICADOR DE SESIÓN DE ADMINISTRADOR ---
# Este 'portero' es más estricto.
# 1. Verifica si el usuario ha iniciado sesión.
# 2. Verifica si el usuario tiene el flag 'is_admin' en True.
if 'user' not in st.session_state or st.session_state.user is None:
    st.error("Debes iniciar sesión para acceder.")
    st.stop()

# st.session_state.user es una tupla: (id, username, password, is_admin)
# El cuarto elemento (índice 3) es el flag de administrador.
is_admin = st.session_state.user[3]

if not is_admin:
    st.error("No tienes permisos de administrador para ver esta página.")
    st.stop()

# --- FUNCIONES DE BASE DE DATOS PARA EL ADMIN ---
def conectar_db():
    return sqlite3.connect('portfolio.db')

def ver_todos_los_usuarios():
    """Obtiene una lista de todos los usuarios."""
    conexion = conectar_db()
    df = pd.read_sql_query("SELECT id, username FROM usuarios ORDER BY id", conexion)
    conexion.close()
    return df

def contar_registros_totales():
    """Cuenta el total de registros en las tablas principales."""
    conexion = conectar_db()
    cursor = conexion.cursor()

    total_operaciones = cursor.execute("SELECT COUNT(*) FROM operaciones").fetchone()[0]
    total_watchlist = cursor.execute("SELECT COUNT(*) FROM watchlist").fetchone()[0]
    total_finanzas = cursor.execute("SELECT COUNT(*) FROM finanzas_personales").fetchone()[0]

    conexion.close()
    return total_operaciones, total_watchlist, total_finanzas

# --- INTERFAZ DE LA PÁGINA DE ADMIN ---
st.set_page_config(layout="wide", page_title="Panel de Admin")
st.title("Panel de Administración ⚙️")

st.header("Estadísticas Generales de la Aplicación")

usuarios_df = ver_todos_los_usuarios()
total_ops, total_wl, total_fin = contar_registros_totales()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total de Usuarios Registrados", len(usuarios_df))
col2.metric("Total de Operaciones", total_ops)
col3.metric("Activos en Watchlists", total_wl)
col4.metric("Registros Financieros", total_fin)

st.divider()

st.header("Lista de Usuarios Registrados")
st.dataframe(usuarios_df, use_container_width=True)