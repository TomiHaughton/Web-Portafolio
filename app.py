import streamlit as st
import psycopg2
import hashlib

st.set_page_config(page_title="Portfolio App Login", layout="centered")

# --- CONEXIÓN A LA NUBE (SUPABASE) ---
def conectar_db():
    """Conecta a la base de datos usando los secretos (locales o de la nube)."""
    return psycopg2.connect(
        host=st.secrets["connections"]["supabase"]["host"],
        database=st.secrets["connections"]["supabase"]["database"],
        user=st.secrets["connections"]["supabase"]["username"],
        password=st.secrets["connections"]["supabase"]["password"],
        port=st.secrets["connections"]["supabase"]["port"]
    )

def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def verify_password(password, hashed_password):
    return hash_password(password) == hashed_password

def anadir_usuario(username, password):
    conn = conectar_db()
    cursor = conn.cursor()
    try:
        # CAMBIO IMPORTANTE: Usamos %s en lugar de ? para PostgreSQL
        cursor.execute("INSERT INTO usuarios (username, password) VALUES (%s, %s)", (username, hash_password(password)))
        conn.commit()
        return True
    except Exception: 
        return False
    finally:
        conn.close()

def obtener_usuario(username):
    conn = conectar_db()
    cursor = conn.cursor()
    # CAMBIO IMPORTANTE: Usamos %s en lugar de ?
    cursor.execute("SELECT * FROM usuarios WHERE username = %s", (username,))
    user_data = cursor.fetchone()
    conn.close()
    return user_data

# --- LÓGICA DE LA SESIÓN ---
if 'user' not in st.session_state:
    st.session_state.user = None

# --- LÓGICA PARA OCULTAR PÁGINAS ---
def ocultar_pagina(nombre_pagina):
    st.markdown(f"""<style>[data-testid="stSidebarNav"] li a[href*="/{nombre_pagina}"] {{display: none;}}</style>""", unsafe_allow_html=True)

if st.session_state.user:
    # En PostgreSQL, los booleanos son True/False reales, no 0/1.
    # is_admin es el índice 3 en la tupla (id, username, password, is_admin)
    es_admin = st.session_state.user[3]
    
    # Si es False (no admin), ocultamos.
    if not es_admin:
        ocultar_pagina("Admin")
else:
    ocultar_pagina("Dashboard")
    ocultar_pagina("Watchlist")
    ocultar_pagina("Ingresos_y_Gastos")
    ocultar_pagina("Análisis_Gráfico")
    ocultar_pagina("Dividendos")
    ocultar_pagina("Admin")

# --- INTERFAZ ---
if st.session_state.user:
    st.title(f"¡Bienvenido, {st.session_state.user[1]}! 👋")
    st.sidebar.info(f"Sesión iniciada como: **{st.session_state.user[1]}**")
    
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.user = None
        st.rerun()
    
    st.markdown("👈 **Selecciona una página en la barra lateral** para empezar.")
    st.success("✅ Conectado a la Nube (Supabase)")

else:
    st.title("Bienvenido a tu App de Portafolio")
    col1, col2 = st.columns(2)

    with col1:
        with st.form("login_form"):
            st.subheader("Iniciar Sesión")
            login_username = st.text_input("Nombre de Usuario", key="login_user")
            login_password = st.text_input("Contraseña", type="password", key="login_pass")
            
            if st.form_submit_button("Iniciar Sesión"):
                try:
                    user_data = obtener_usuario(login_username)
                    # Verificamos si encontramos usuario y si la contraseña coincide
                    if user_data and verify_password(login_password, user_data[2]):
                        st.session_state.user = user_data
                        st.rerun()
                    else:
                        st.error("Usuario o contraseña incorrectos.")
                except Exception as e:
                    st.error(f"Error de conexión con la nube: {e}")

    with col2:
        with st.form("register_form"):
            st.subheader("Registrar Nuevo Usuario")
            reg_username = st.text_input("Elige un Nombre de Usuario", key="reg_user")
            reg_password = st.text_input("Elige una Contraseña", type="password", key="reg_pass")
            
            if st.form_submit_button("Registrarse"):
                if anadir_usuario(reg_username, reg_password):
                    st.success("¡Registrado en la nube! Ahora inicia sesión.")
                else:
                    st.error("Ese usuario ya existe.")