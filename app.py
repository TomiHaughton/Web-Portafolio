import streamlit as st
import sqlite3
import hashlib # Librería para hashear contraseñas

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Portfolio App Login", layout="centered")

# --- FUNCIONES DE BASE DE DATOS Y USUARIOS ---
def conectar_db():
    return sqlite3.connect('portfolio.db')

def hash_password(password):
    """Hashea la contraseña para guardarla de forma segura."""
    return hashlib.sha256(str.encode(password)).hexdigest()

def verify_password(password, hashed_password):
    """Verifica si la contraseña ingresada coincide con la hasheada."""
    return hash_password(password) == hashed_password

def anadir_usuario(username, password):
    """Añade un nuevo usuario a la base de datos."""
    conexion = conectar_db()
    cursor = conexion.cursor()
    try:
        cursor.execute("INSERT INTO usuarios (username, password) VALUES (?, ?)", (username, hash_password(password)))
        conexion.commit()
        return True
    except sqlite3.IntegrityError:
        return False # El usuario ya existe
    finally:
        conexion.close()

def obtener_usuario(username):
    """Obtiene los datos de un usuario por su nombre de usuario."""
    conexion = conectar_db()
    cursor = conexion.cursor()
    cursor.execute("SELECT * FROM usuarios WHERE username = ?", (username,))
    user_data = cursor.fetchone()
    conexion.close()
    return user_data

# --- LÓGICA DE LA SESIÓN ---
# Inicializamos el estado de la sesión si no existe
if 'user' not in st.session_state:
    st.session_state.user = None

# --- INTERFAZ ---

# Si el usuario ya inició sesión, mostramos la bienvenida y un botón para cerrar sesión
if st.session_state.user:
    st.title(f"¡Bienvenido, {st.session_state.user[1]}! 👋")
    st.sidebar.success("Sesión iniciada. Selecciona una página.")
    
    if st.button("Cerrar Sesión"):
        st.session_state.user = None
        st.rerun() # Recargamos la página para volver al login
else:
    # Si no hay sesión iniciada, mostramos los formularios de login y registro
    st.title("Bienvenido a tu App de Portafolio")
    
    col1, col2 = st.columns(2)

    # --- Formulario de Inicio de Sesión ---
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
                    st.rerun() # Recargamos la página para mostrar la bienvenida
                else:
                    st.error("Nombre de usuario o contraseña incorrectos.")

    # --- Formulario de Registro ---
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