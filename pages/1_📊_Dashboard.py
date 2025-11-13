import streamlit as st
import sqlite3
from datetime import date
import pandas as pd
import yfinance as yf
import plotly.express as px

# --- VERIFICADOR DE SESIÓN ---
if 'user' not in st.session_state or st.session_state.user is None:
    st.error("Debes iniciar sesión para acceder a esta página.")
    st.stop()
USER_ID = st.session_state.user[0]

# --- CSS PARA CENTRADO ---
st.markdown("""<style>.stDataFrame th, .stDataFrame td {text-align: center;}</style>""", unsafe_allow_html=True)

# --- FUNCIONES DE BASE DE DATOS ---
def conectar_db():
    return sqlite3.connect('portfolio.db')

# *** AUTO-MIGRACIÓN ***
def verificar_y_migrar_db():
    """Revisa si falta la columna 'moneda' y la agrega automáticamente."""
    conexion = conectar_db()
    cursor = conexion.cursor()
    try:
        cursor.execute("SELECT moneda FROM operaciones LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE operaciones ADD COLUMN moneda TEXT DEFAULT 'USD'")
        conexion.commit()
        st.toast("✅ Base de datos actualizada: Se añadió soporte para Monedas.", icon="🎉")
    finally:
        conexion.close()

def anadir_operacion(fecha, ticker, tipo, cantidad, precio, moneda, user_id):
    conexion = conectar_db()
    cursor = conexion.cursor()
    cursor.execute("INSERT INTO operaciones (fecha, ticker, tipo, cantidad, precio, moneda, user_id) VALUES (?, ?, ?, ?, ?, ?, ?)", (fecha, ticker, tipo, cantidad, precio, moneda, user_id))
    conexion.commit()
    conexion.close()

def eliminar_operacion(operacion_id, user_id):
    conexion = conectar_db()
    cursor = conexion.cursor()
    cursor.execute("DELETE FROM operaciones WHERE id = ? AND user_id = ?", (operacion_id, user_id))
    conexion.commit()
    conexion.close()

def ver_operaciones(user_id):
    conexion = conectar_db()
    df = pd.read_sql_query("SELECT * FROM operaciones WHERE user_id = ? ORDER BY fecha ASC", conexion, params=(user_id,))
    conexion.close()
    return df

def obtener_aportaciones_retiros(user_id):
    try:
        conexion = conectar_db()
        df = pd.read_sql_query("SELECT tipo, monto FROM finanzas_personales WHERE categoria = 'Inversiones' AND user_id = ?", conexion, params=(user_id,))
        conexion.close()
        total_aportado = df[df['tipo'] == 'Gasto']['monto'].sum()
        total_retirado = df[df['tipo'] == 'Ingreso']['monto'].sum()
        return total_aportado, total_retirado
    except:
        return 0, 0

# --- FUNCIONES DE DATOS Y CÁLCULO ---
@st.cache_data(ttl=600)
def obtener_datos_mercado(tickers):
    if not tickers: return {}, 1
    
    # 1. Precios de acciones
    data = yf.Tickers(tickers).history(period='1d')
    if not data.empty:
        precios = data['Close'].iloc[-1].to_dict()
    else:
        precios = {}

    # 2. Precio del Dólar (Usamos USDT-ARS como referencia)
    try:
        dolar_ticker = yf.Ticker("USDT-ARS")
        hist = dolar_ticker.history(period='1d')
        if not hist.empty:
            precio_dolar = hist['Close'].iloc[-1]
        else:
            precio_dolar = 1150.0
    except:
        precio_dolar = 1150.0 
        
    return precios, precio_dolar

def calcular_posiciones(df_ops, precio_dolar):
    if df_ops.empty: return pd.DataFrame(), 0, pd.DataFrame()
    df = df_ops.copy()
    
    if 'moneda' not in df.columns: df['moneda'] = 'USD'
    df['moneda'] = df['moneda'].fillna('USD')

    df['cantidad_neta'] = df.apply(lambda row: row['cantidad'] if row['tipo'] == 'Compra' else -row['cantidad'], axis=1)
    
    # Cálculos en moneda original
    df['coste_op'] = df['cantidad'] * df['precio']
    df['ingreso_op'] = df['cantidad'] * df['precio']
    
    posiciones = df.groupby(['ticker', 'moneda']).agg(
        cantidad_total=('cantidad_neta', 'sum'),
        coste_acumulado_compras=('coste_op', lambda x: x[df.loc[x.index, 'tipo'] == 'Compra'].sum()),
        cantidad_acumulada_compras=('cantidad', lambda x: x[df.loc[x.index, 'tipo'] == 'Compra'].sum()),
        total_ventas=('ingreso_op', lambda x: x[df.loc[x.index, 'tipo'] == 'Venta'].sum()),
        cantidad_vendida=('cantidad', lambda x: x[df.loc[x.index, 'tipo'] == 'Venta'].sum())
    ).reset_index()

    posiciones['ppp_original'] = posiciones.apply(lambda x: x['coste_acumulado_compras'] / x['cantidad_acumulada_compras'] if x['cantidad_acumulada_compras'] > 0 else 0, axis=1)
    posiciones['coste_vendido'] = posiciones['ppp_original'] * posiciones['cantidad_vendida']
    posiciones['beneficio_realizado_original'] = posiciones['total_ventas'] - posiciones['coste_vendido']

    posiciones_abiertas = posiciones[posiciones['cantidad_total'] > 0.000001].copy()
    
    ganancia_realizada_usd = 0
    for index, row in posiciones.iterrows():
        val = row['beneficio_realizado_original']
        if row['moneda'] == 'ARS':
            ganancia_realizada_usd += (val / precio_dolar)
        else:
            ganancia_realizada_usd += val
    
    beneficios_realizados_df = posiciones[['ticker', 'beneficio_realizado_original', 'moneda']]

    if not posiciones_abiertas.empty:
        tickers_list = posiciones_abiertas['ticker'].unique().tolist()
        precios_actuales, _ = obtener_datos_mercado(tickers_list)
        
        posiciones_abiertas['precio_actual'] = posiciones_abiertas['ticker'].map(precios_actuales).fillna(0)
        
        def calcular_valor_usd(row):
            if row['precio_actual'] == 0: return 0
            valor_local = row['cantidad_total'] * row['precio_actual']
            if row['moneda'] == 'ARS':
                return valor_local / precio_dolar
            return valor_local

        posiciones_abiertas['valor_mercado_usd'] = posiciones_abiertas.apply(calcular_valor_usd, axis=1)
        
        def calcular_coste_usd(row):
            coste_local = row['cantidad_total'] * row['ppp_original']
            if row['moneda'] == 'ARS':
                return coste_local / precio_dolar 
            return coste_local
            
        posiciones_abiertas['coste_total_usd'] = posiciones_abiertas.apply(calcular_coste_usd, axis=1)
        posiciones_abiertas['ganancia_no_realizada_usd'] = posiciones_abiertas['valor_mercado_usd'] - posiciones_abiertas['coste_total_usd']
        
        posiciones_abiertas['rentabilidad_%'] = posiciones_abiertas.apply(
            lambda x: (x['ganancia_no_realizada_usd'] / x['coste_total_usd'] * 100) if x['coste_total_usd'] > 0 else 0, axis=1
        )

    return posiciones_abiertas, ganancia_realizada_usd, beneficios_realizados_df

@st.cache_data(ttl=600)
def calcular_evolucion_patrimonio(df_ops):
    # Desactivado temporalmente por complejidad multimoneda
    return None

def estilo_ganancia(val):
    if pd.isna(val) or val == 0: return 'color: inherit; background-color: transparent;'
    if val > 0: return 'background-color: rgba(40, 167, 69, 0.4); color: #111;'
    else: return 'background-color: rgba(220, 53, 69, 0.4); color: #111;'

# --- INTERFAZ ---
st.set_page_config(layout="wide", page_title="Dashboard")
st.title(f"Dashboard de {st.session_state.user[1]} 📊")

# 1. Auto-migración
verificar_y_migrar_db()

# 2. Carga de datos
operaciones_df = ver_operaciones(USER_ID)
tickers_unicos = operaciones_df['ticker'].unique().tolist() if not operaciones_df.empty else []
_, precio_dolar_hoy = obtener_datos_mercado(tickers_unicos)

st.sidebar.markdown("---")
st.sidebar.metric("Dólar Ref (USDT)", f"${precio_dolar_hoy:,.0f}")

posiciones_df, ganancia_realizada_total, _ = calcular_posiciones(operaciones_df, precio_dolar_hoy)
total_aportado, total_retirado = obtener_aportaciones_retiros(USER_ID)

st.header("Resumen General (Base USD)")
if not operaciones_df.empty:
    valor_total_portafolio = posiciones_df['valor_mercado_usd'].sum() if 'valor_mercado_usd' in posiciones_df.columns else 0
    ganancia_no_realizada_total = posiciones_df['ganancia_no_realizada_usd'].sum() if 'ganancia_no_realizada_usd' in posiciones_df.columns else 0
    beneficio_total = ganancia_no_realizada_total + ganancia_realizada_total
    capital_neto_aportado = total_aportado - total_retirado
    rentabilidad = (beneficio_total / capital_neto_aportado) * 100 if capital_neto_aportado > 0 else 0
    
    row1_cols = st.columns(4)
    row1_cols[0].metric("Patrimonio Total", f"US$ {valor_total_portafolio:,.2f}")
    row1_cols[1].metric("Beneficio Total", f"US$ {beneficio_total:,.2f}")
    row1_cols[2].metric("Capital Neto (Est.)", f"US$ {capital_neto_aportado:,.2f}")
    row1_cols[3].metric("Rentabilidad Total", f"{rentabilidad:.2f}%", delta_color="off")
    
    row2_cols = st.columns(4)
    row2_cols[0].metric("Beneficio No Realizado", f"US$ {ganancia_no_realizada_total:,.2f}")
    row2_cols[1].metric("Beneficio Realizado", f"US$ {ganancia_realizada_total:,.2f}")
    row2_cols[2].metric("Total Aportado", f"US$ {total_aportado:,.2f}")
    row2_cols[3].metric("Total Retirado", f"-US$ {total_retirado:,.2f}")
else:
    st.info("Añade operaciones para ver tu dashboard.")

st.divider()

# Gráficos
st.header("Análisis Visual")
col_graf1, col_graf2 = st.columns(2)
with col_graf1:
    if not posiciones_df.empty:
        fig_diversificacion = px.pie(posiciones_df, values='valor_mercado_usd', names='ticker', title='Diversificación (en USD)', hole=.3)
        st.plotly_chart(fig_diversificacion, use_container_width=True)
    else:
        st.info("Sin datos.")
with col_graf2:
    st.info("El gráfico de evolución histórica está deshabilitado temporalmente.")

st.divider()

# Formulario
with st.form("operacion_form", clear_on_submit=True):
    st.header("Añadir Nueva Operación")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        fecha_op = st.date_input("Fecha", value=date.today())
        ticker_op = st.text_input("Ticker (ej. GGAL.BA)")
    with c2:
        tipo_op = st.selectbox("Tipo", ["Compra", "Venta"])
        moneda_op = st.selectbox("Moneda", ["USD", "ARS"])
    with c3:
        cantidad_op = st.number_input("Cantidad", min_value=0.0, step=0.0001, format="%.4f")
    with c4:
        precio_op = st.number_input("Precio Unitario", min_value=0.0, step=0.0001, format="%.4f")
        
    submitted = st.form_submit_button("Añadir Operación")
    if submitted:
        if not ticker_op or cantidad_op <= 0 or precio_op <= 0:
            st.warning("Datos incompletos.")
        else:
            ticker_final = ticker_op.upper()
            # *** LISTA COMPLETA DE CRIPTOS ***
            criptos_comunes = [
                "BTC", "ETH", "SOL", "USDT", "BNB", "XRP", "ADA", "DOGE", "SHIB", "DOT", "DAI", "MATIC", "AVAX", "TRX", "LTC", "LINK", "ATOM", "UNI"
            ]
            if ticker_final in criptos_comunes:
                ticker_final = f"{ticker_final}-USD"
            
            anadir_operacion(fecha_op, ticker_final, tipo_op, cantidad_op, precio_op, moneda_op, USER_ID)
            st.success(f"Operación añadida.")
            st.rerun()

# Tablas
st.header("Posiciones Actuales")
if not posiciones_df.empty:
    df_show = posiciones_df[[
        'ticker', 'moneda', 'cantidad_total', 'ppp_original', 'precio_actual', 
        'valor_mercado_usd', 'ganancia_no_realizada_usd', 'rentabilidad_%'
    ]].rename(columns={
        'ticker': 'Ticker', 'moneda': 'Moneda', 'cantidad_total': 'Cantidad',
        'ppp_original': 'Precio Prom (Orig)', 'precio_actual': 'Precio Hoy',
        'valor_mercado_usd': 'Valor (USD)', 'ganancia_no_realizada_usd': 'Ganancia (USD)',
        'rentabilidad_%': 'Rentabilidad %'
    })
    
    st.dataframe(df_show.style.applymap(estilo_ganancia, subset=['Ganancia (USD)']).format({
        'Precio Prom (Orig)': '${:,.2f}', 'Precio Hoy': '${:,.2f}', 
        'Valor (USD)': 'US$ {:,.2f}', 'Ganancia (USD)': 'US$ {:,.2f}', 'Rentabilidad %': '{:,.2f}%'
    }, na_rep="-").set_table_styles([dict(selector="th", props=[("text-align", "center")]), dict(selector="td", props=[("text-align", "center")])]), use_container_width=True)

st.header("Historial de Operaciones")
if not operaciones_df.empty:
    if 'moneda' not in operaciones_df.columns: operaciones_df['moneda'] = 'USD'
    df_hist = operaciones_df.sort_values(by="fecha", ascending=False).rename(columns={'id':'ID', 'fecha':'Fecha', 'ticker':'Ticker', 'tipo':'Tipo', 'moneda':'Moneda', 'cantidad':'Cant', 'precio':'Precio'})
    
    cols = st.columns([0.5, 1, 1, 0.8, 0.8, 1, 1, 0.5])
    headers = ["ID", "Fecha", "Ticker", "Tipo", "Moneda", "Cantidad", "Precio", "Acción"]
    for c, h in zip(cols, headers): c.markdown(f"**{h}**")
    st.divider()
    for index, row in df_hist.iterrows():
        cols = st.columns([0.5, 1, 1, 0.8, 0.8, 1, 1, 0.5])
        cols[0].write(row['ID'])
        cols[1].write(row['Fecha'])
        cols[2].write(row['Ticker'])
        cols[3].write(row['Tipo'])
        cols[4].write(row['Moneda'])
        cols[5].write(f"{row['Cant']:.4f}")
        cols[6].write(f"${row['Precio']:,.2f}")
        if cols[7].button("🗑️", key=f"del_{row['ID']}"):
            eliminar_operacion(row['ID'], USER_ID)
            st.rerun()