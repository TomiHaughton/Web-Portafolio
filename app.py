import streamlit as st
import sqlite3
import hashlib

st.set_page_config(page_title="Portfolio App Login", layout="centered")

# --- FUNCIONES DE BASE DE DATOS Y USUARIOS (sin cambios) ---
# ... (código sin cambios) ...
def conectar_db():
    return sqlite3.connect('portfolio.db')
def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()
def verify_password(password, hashed_password):
    return hash_password(password) == hashed_password
def anadir_usuario(username, password):
    conexion = conectar_db()
    cursor = conexion.cursor()
    try:
        cursor.execute("INSERT INTO usuarios (username, password) VALUES (?, ?)", (username, hash_password(password)))
        conexion.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conexion.close()
def obtener_usuario(username):
    conexion = conectar_db()
    cursor = conexion.cursor()
    cursor.execute("SELECT * FROM usuarios WHERE username = ?", (username,))
    user_data = cursor.fetchone()
    conexion.close()
    return user_data

# --- LÓGICA DE LA SESIÓN ---
if 'user' not in st.session_state:
    st.session_state.user = None

# --- LÓGICA PARA OCULTAR PÁGINAS ---
def ocultar_pagina(nombre_pagina):
    st.markdown(f"""
        <style>
            [data-testid="stSidebarNav"] li a[href*="/{nombre_pagina}"] {{
                display: none;
            }}
        </style>
    """, unsafe_allow_html=True)

# Lógica principal de visibilidad
if st.session_state.user:
    es_admin = st.session_state.user[3]
    if es_admin == 0:
        ocultar_pagina("Admin")
else:
    # *** CAMBIO: Añadimos "Dividendos" a la lista ***
    ocultar_pagina("Dashboard")
    ocultar_pagina("Watchlist")
    ocultar_pagina("Ingresos_y_Gastos")
    ocultar_pagina("Análisis_Gráfico")
    ocultar_pagina("Admin")
    ocultar_pagina("Dividendos") # <-- AÑADIDO

# --- INTERFAZ (sin cambios) ---
# ... (El resto del código de login y bienvenida es el mismo) ...
if st.session_state.user:
    st.title(f"¡Bienvenido, {st.session_state.user[1]}! 👋")
    st.sidebar.info(f"Sesión iniciada como: **{st.session_state.user[1]}**")
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.user = None
        st.rerun()
    st.markdown("👈 **Selecciona una página en la barra lateral** para empezar.")
else:
    st.title("Bienvenido a tu App de Portafolio")
    col1, col2 = st.columns(2)
    with col1:
        with st.form("login_form"):
            st.subheader("Iniciar Sesión")
            login_username = st.text_input("Nombre de Usuario", key="login_user")
            login_password = st.text_input("Contraseña", type="password", key="login_pass")
            login_submitted = st.form_submit_button("Iniciar Sesión")
            if login_submitted:
                user_data = obtener_usuario(login_username)
                if user_data and verify_password(login_password, user_data[2]):
                    st.success("¡Inicio de sesión exitoso!")
                    st.session_state.user = user_data
                    st.rerun()
                else:
                    st.error("Nombre de usuario o contraseña incorrectos.")
    with col2:
        with st.form("register_form"):
            st.subheader("Registrar Nuevo Usuario")
            reg_username = st.text_input("Elige un Nombre de Usuario", key="reg_user")
            reg_password = st.text_input("Elige una Contraseña", type="password", key="reg_pass")
            reg_submitted = st.form_submit_button("Registrarse")
            if reg_submitted:
                if anadir_usuario(reg_username, reg_password):
                    st.success("¡Usuario registrado con éxito! Ahora puedes iniciar sesión.")
                else:
                    st.error("Ese nombre de usuario ya existe.")