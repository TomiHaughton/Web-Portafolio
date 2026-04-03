import streamlit as st
import psycopg2
import pandas as pd
from datetime import date
import plotly.express as px
import plotly.graph_objects as go
import requests
from utils import apply_styles, metric_card, section_header, apply_plotly_style

if 'user' not in st.session_state or st.session_state.user is None:
    st.error("Debes iniciar sesión.")
    st.stop()
USER_ID = st.session_state.user[0]

st.set_page_config(layout="wide", page_title="Ingresos y Gastos · Portfolio")
apply_styles()

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
    conn.cursor().execute(
        "INSERT INTO finanzas_personales (fecha, tipo, categoria, monto, descripcion, moneda, user_id) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s)",
        (fecha, tipo, categoria, monto, descripcion, moneda, user_id)
    )
    conn.commit(); conn.close()

def ver_flujos(user_id):
    conn = conectar_db()
    df = pd.read_sql_query(
        "SELECT * FROM finanzas_personales WHERE user_id=%s ORDER BY fecha DESC",
        conn, params=(user_id,)
    )
    conn.close()
    return df

def eliminar_flujo(flujo_id, user_id):
    conn = conectar_db()
    conn.cursor().execute(
        "DELETE FROM finanzas_personales WHERE id=%s AND user_id=%s", (flujo_id, user_id)
    )
    conn.commit(); conn.close()

def ver_categorias(user_id, tipo):
    conn = conectar_db()
    df = pd.read_sql_query(
        "SELECT * FROM categorias WHERE user_id=%s AND tipo=%s", conn, params=(user_id, tipo)
    )
    conn.close()
    defaults_ing = ["Sueldo","Inversiones","Dividendo Recibido","Otros"]
    defaults_gas = ["Alquiler","Tarjeta de Crédito","Inversiones","Comida","Ocio","Otros"]
    base = defaults_ing if tipo == 'Ingreso' else defaults_gas
    return base + df['nombre'].tolist(), df

def anadir_categoria(user_id, tipo, nombre):
    conn = conectar_db()
    try:
        conn.cursor().execute(
            "INSERT INTO categorias (user_id, tipo, nombre) VALUES (%s,%s,%s)", (user_id, tipo, nombre)
        )
        conn.commit()
        st.success("Categoría añadida.")
    except:
        st.warning("Ya existe.")
    finally:
        conn.close()

def eliminar_categoria(id_cat, user_id):
    conn = conectar_db()
    conn.cursor().execute(
        "DELETE FROM categorias WHERE id=%s AND user_id=%s", (id_cat, user_id)
    )
    conn.commit(); conn.close()

@st.cache_data(ttl=300)
def obtener_dolar():
    if 'precio_dolar_compartido' in st.session_state:
        return st.session_state['precio_dolar_compartido']
    try:
        r = requests.get("https://dolarapi.com/v1/dolares/cripto", timeout=5)
        if r.status_code == 200: return float(r.json()['venta'])
    except: pass
    return 1150.0

# ── HEADER ────────────────────────────────────────────────────────
dolar = obtener_dolar()
st.markdown("<h1>Ingresos y Gastos</h1>", unsafe_allow_html=True)
st.markdown(
    f'<div style="color:#475569;font-size:0.85rem;font-family:JetBrains Mono,monospace;'
    f'margin-top:-8px;margin-bottom:24px">Dólar cripto referencia: '
    f'<span style="color:#f59e0b">${dolar:,.0f} ARS</span></div>',
    unsafe_allow_html=True
)

# ── CATEGORÍAS (EXPANDER) ─────────────────────────────────────────
with st.expander("⚙️  Gestionar categorías"):
    with st.form("fc", clear_on_submit=True):
        c1, c2 = st.columns([1, 2])
        tc = c1.selectbox("Tipo", ["Ingreso", "Gasto"])
        nc = c2.text_input("Nombre de categoría")
        if st.form_submit_button("Añadir") and nc:
            anadir_categoria(USER_ID, tc, nc)

    t1, t2 = st.tabs(["Ingresos", "Gastos"])
    with t1:
        _, df_cat = ver_categorias(USER_ID, "Ingreso")
        for _, r in df_cat.iterrows():
            c1, c2 = st.columns([3, 1])
            c1.markdown(f'<span style="color:#94a3b8;font-size:0.85rem">{r["nombre"]}</span>', unsafe_allow_html=True)
            if c2.button("✕", key=f"ci{r['id']}"): eliminar_categoria(r['id'], USER_ID); st.rerun()
    with t2:
        _, df_cat = ver_categorias(USER_ID, "Gasto")
        for _, r in df_cat.iterrows():
            c1, c2 = st.columns([3, 1])
            c1.markdown(f'<span style="color:#94a3b8;font-size:0.85rem">{r["nombre"]}</span>', unsafe_allow_html=True)
            if c2.button("✕", key=f"cg{r['id']}"): eliminar_categoria(r['id'], USER_ID); st.rerun()

st.divider()

# ── NEW MOVEMENT FORM ─────────────────────────────────────────────
section_header("Nuevo Movimiento")
with st.form("ff", clear_on_submit=True):
    c1, c2, c3, c4, c5 = st.columns([1, 1, 1, 1.5, 1.5])
    fe = c1.date_input("Fecha", value=date.today())
    ti = c2.selectbox("Tipo", ["Ingreso", "Gasto"], key="tf")
    mo = c3.selectbox("Moneda", ["ARS", "USD"])
    lst, _ = ver_categorias(USER_ID, ti)
    ca = c4.selectbox("Categoría", lst)
    mt = c5.number_input("Monto", min_value=0.0, step=0.01, format="%.2f")
    de = st.text_input("Descripción (opcional)")
    if st.form_submit_button("Guardar movimiento", use_container_width=True) and mt > 0:
        anadir_flujo(fe, ti, ca, mt, de, mo, USER_ID)
        st.success("✓ Movimiento guardado.")
        st.rerun()

st.divider()

# ── RESUMEN ───────────────────────────────────────────────────────
df = ver_flujos(USER_ID)

if not df.empty:
    if 'moneda' not in df.columns: df['moneda'] = 'ARS'
    df['monto_usd'] = df.apply(
        lambda x: x['monto'] if x['moneda'] == 'USD' else x['monto'] / dolar, axis=1
    )
    df['fecha'] = pd.to_datetime(df['fecha'])
    hoy = pd.Timestamp.now()
    df_mes = df[(df['fecha'].dt.month == hoy.month) & (df['fecha'].dt.year == hoy.year)]

    ing_mes = df_mes[df_mes['tipo'] == 'Ingreso']['monto_usd'].sum()
    gas_mes = df_mes[df_mes['tipo'] == 'Gasto']['monto_usd'].sum()
    inv_mes = df_mes[(df_mes['tipo'] == 'Gasto') & (df_mes['categoria'] == 'Inversiones')]['monto_usd'].sum()
    vid_mes = gas_mes - inv_mes

    ing_hist = df[df['tipo'] == 'Ingreso']['monto_usd'].sum()
    gas_hist = df[df['tipo'] == 'Gasto']['monto_usd'].sum()
    inv_hist = df[(df['tipo'] == 'Gasto') & (df['categoria'] == 'Inversiones')]['monto_usd'].sum()
    ahorro   = ing_hist - (gas_hist - inv_hist)

    section_header("Resumen del mes", hoy.strftime('%B %Y'))
    c1, c2, c3, c4 = st.columns(4)
    with c1: metric_card("Ingresos del mes",  f"US$ {ing_mes:,.2f}", color="green")
    with c2: metric_card("Gastos de vida",     f"US$ {vid_mes:,.2f}", color="red")
    with c3: metric_card("Invertido el mes",   f"US$ {inv_mes:,.2f}", color="blue")
    with c4: metric_card("Ahorro histórico",   f"US$ {ahorro:,.2f}",
                         subtitle="Ingresos − gastos de vida acumulados",
                         color="green" if ahorro >= 0 else "red")

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    # Gráfico mensual (sin inversiones para ver flujo real de vida)
    dfg = df[df['categoria'] != 'Inversiones'].copy()
    if not dfg.empty:
        men = dfg.groupby([dfg['fecha'].dt.to_period('M'), 'tipo'])['monto_usd'].sum().reset_index()
        men['fecha'] = men['fecha'].dt.to_timestamp()
        men['tipo_label'] = men['tipo'].map({'Ingreso': 'Ingresos', 'Gasto': 'Gastos'})

        fig = px.bar(
            men, x='fecha', y='monto_usd', color='tipo_label', barmode='group',
            color_discrete_map={'Ingresos': '#10b981', 'Gastos': '#ef4444'},
            labels={'monto_usd': 'USD', 'fecha': '', 'tipo_label': ''},
        )
        fig.update_traces(marker_line_width=0)
        fig = apply_plotly_style(fig, "Ingresos vs Gastos mensuales (sin inversiones)")
        st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── HISTORIAL ─────────────────────────────────────────────────────
section_header("Historial de movimientos")

if not df.empty:
    cols_h = st.columns([1, 0.8, 1.5, 0.7, 1.2, 2, 0.4])
    for col, lbl in zip(cols_h, ["Fecha","Tipo","Categoría","Moneda","Monto","Descripción",""]):
        col.markdown(
            f'<span style="font-size:0.65rem;text-transform:uppercase;letter-spacing:1px;'
            f'color:#334155;font-family:JetBrains Mono,monospace">{lbl}</span>',
            unsafe_allow_html=True
        )
    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    for _, r in df.iterrows():
        tipo_color = "#10b981" if r['tipo'] == 'Ingreso' else "#ef4444"
        cols = st.columns([1, 0.8, 1.5, 0.7, 1.2, 2, 0.4])
        cols[0].markdown(f'<span style="color:#64748b;font-family:JetBrains Mono,monospace;font-size:0.8rem">{pd.to_datetime(r["fecha"]).strftime("%Y-%m-%d")}</span>', unsafe_allow_html=True)
        cols[1].markdown(f'<span style="color:{tipo_color};font-family:JetBrains Mono,monospace;font-size:0.8rem">{r["tipo"]}</span>', unsafe_allow_html=True)
        cols[2].markdown(f'<span style="color:#94a3b8;font-size:0.82rem">{r["categoria"]}</span>', unsafe_allow_html=True)
        cols[3].markdown(f'<span style="color:#475569;font-family:JetBrains Mono,monospace;font-size:0.8rem">{r["moneda"]}</span>', unsafe_allow_html=True)
        cols[4].markdown(f'<span style="color:#cbd5e1;font-family:JetBrains Mono,monospace;font-size:0.85rem">{r["monto"]:,.2f}</span>', unsafe_allow_html=True)
        cols[5].markdown(f'<span style="color:#475569;font-size:0.8rem">{r.get("descripcion","") or "—"}</span>', unsafe_allow_html=True)
        if cols[6].button("✕", key=f"del{r['id']}"): eliminar_flujo(r['id'], USER_ID); st.rerun()
        st.markdown("<div style='height:2px;background:#0a0f1e;margin:2px 0'></div>", unsafe_allow_html=True)
else:
    st.info("Sin movimientos registrados.")