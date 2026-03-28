import streamlit as st
import psycopg2
import pandas as pd

if 'user' not in st.session_state or st.session_state.user is None: st.error("Login requerido"); st.stop()
if not st.session_state.user[3]: st.error("Acceso denegado"); st.stop()

def conectar_db():
    return psycopg2.connect(
        host=st.secrets["connections"]["supabase"]["host"],
        database=st.secrets["connections"]["supabase"]["database"],
        user=st.secrets["connections"]["supabase"]["username"],
        password=st.secrets["connections"]["supabase"]["password"],
        port=st.secrets["connections"]["supabase"]["port"]
    )

st.title("Panel Admin ⚙️")
conn = conectar_db()
st.header("Usuarios")
st.dataframe(pd.read_sql("SELECT id, username, is_admin FROM usuarios ORDER BY id", conn), use_container_width=True)
st.header("Estadísticas")
ops = pd.read_sql("SELECT COUNT(*) FROM operaciones", conn).iloc[0,0]
usrs = pd.read_sql("SELECT COUNT(*) FROM usuarios", conn).iloc[0,0]
c1, c2 = st.columns(2)
c1.metric("Usuarios", usrs)
c2.metric("Operaciones Totales", ops)
conn.close()