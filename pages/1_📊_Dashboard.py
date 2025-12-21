import streamlit as st
import psycopg2
from datetime import date
import pandas as pd
import yfinance as yf
import plotly.express as px
import requests

# --- VERIFICADOR DE SESIÓN ---
if 'user' not in st.session_state or st.session_state.user is None:
    st.error("Debes iniciar sesión.")
    st.stop()
USER_ID = st.session_state.user[0]

st.markdown("""<style>.stDataFrame th, .stDataFrame td {text-align: center;}</style>""", unsafe_allow_html=True)

# --- CONEXIÓN A SUPABASE ---
def conectar_db():
    return psycopg2.connect(
        host=st.secrets["connections"]["supabase"]["host"],
        database=st.secrets["connections"]["supabase"]["database"],
        user=st.secrets["connections"]["supabase"]["username"],
        password=st.secrets["connections"]["supabase"]["password"],
        port=st.secrets["connections"]["supabase"]["port"]
    )

# --- FUNCIONES ---
def verificar_y_migrar_db():
    pass # En Supabase la estructura ya está creada

def anadir_operacion(fecha, ticker, tipo, cantidad, precio, moneda, user_id):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO operaciones (fecha, ticker, tipo, cantidad, precio, moneda, user_id) VALUES (%s, %s, %s, %s, %s, %s, %s)", (fecha, ticker, tipo, cantidad, precio, moneda, user_id))
    conn.commit()
    conn.close()

def eliminar_operacion(operacion_id, user_id):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM operaciones WHERE id = %s AND user_id = %s", (operacion_id, user_id))
    conn.commit()
    conn.close()

def ver_operaciones(user_id):
    conn = conectar_db()
    df = pd.read_sql_query("SELECT * FROM operaciones WHERE user_id = %s ORDER BY fecha ASC", conn, params=(user_id,))
    conn.close()
    return df

def obtener_aportaciones_retiros(user_id, precio_dolar):
    try:
        conn = conectar_db()
        df = pd.read_sql_query("SELECT tipo, monto, moneda FROM finanzas_personales WHERE categoria = 'Inversiones' AND user_id = %s", conn, params=(user_id,))
        conn.close()
        if df.empty: return 0, 0
        if 'moneda' not in df.columns: df['moneda'] = 'ARS'
        df['moneda'] = df['moneda'].fillna('ARS')
        df['monto_usd'] = df.apply(lambda x: x['monto'] if x['moneda'] == 'USD' else x['monto'] / precio_dolar, axis=1)
        total_aportado = df[df['tipo'] == 'Gasto']['monto_usd'].sum()
        total_retirado = df[df['tipo'] == 'Ingreso']['monto_usd'].sum()
        return total_aportado, total_retirado
    except: return 0, 0

@st.cache_data(ttl=300)
def obtener_dolar_argentina():
    precio, fuente = 1150.0, "Estimado"
    try:
        response = requests.get("https://dolarapi.com/v1/dolares/cripto", timeout=5)
        if response.status_code == 200:
            data = response.json()
            precio, fuente = float(data['venta']), "DolarApi"
    except: pass
    st.session_state['precio_dolar_compartido'] = precio
    return precio, fuente

@st.cache_data(ttl=600)
def obtener_datos_mercado(tickers):
    if not tickers: return {}
    try:
        data = yf.Tickers(tickers).history(period='5d')
        precios = data['Close'].iloc[-1].to_dict() if not data.empty else {}
    except: precios = {}
    return precios

@st.cache_data(ttl=60) 
def calcular_efectivo_actual(user_id):
    saldo_usd, saldo_ars = 0.0, 0.0
    try:
        conn = conectar_db()
        df_fin = pd.read_sql_query("SELECT tipo, categoria, monto, moneda FROM finanzas_personales WHERE user_id = %s", conn, params=(user_id,))
        df_ops = pd.read_sql_query("SELECT tipo, cantidad, precio, moneda FROM operaciones WHERE user_id = %s", conn, params=(user_id,))
        conn.close()
        if 'moneda' not in df_fin.columns: df_fin['moneda'] = 'ARS'
        if 'moneda' not in df_ops.columns: df_ops['moneda'] = 'USD'
        df_fin['moneda'] = df_fin['moneda'].fillna('ARS')
        df_ops['moneda'] = df_ops['moneda'].fillna('USD')

        for _, row in df_fin.iterrows():
            monto, moneda = row['monto'], row['moneda']
            if row['tipo'] == 'Ingreso' and (row['categoria'] == 'Inversiones' or row['categoria'] == 'Dividendo Recibido'):
                if moneda == 'USD': saldo_usd += monto
                else: saldo_ars += monto
            elif row['tipo'] == 'Gasto' and row['categoria'] == 'Inversiones':
                if moneda == 'USD': saldo_usd += monto
                else: saldo_ars += monto
        
        for _, row in df_ops.iterrows():
            costo = row['cantidad'] * row['precio']
            moneda = row['moneda']
            if row['tipo'] == 'Compra':
                if moneda == 'USD': saldo_usd -= costo
                else: saldo_ars -= costo
            elif row['tipo'] == 'Venta':
                if moneda == 'USD': saldo_usd += costo
                else: saldo_ars += costo
        return saldo_usd, saldo_ars
    except: return 0.0, 0.0

def calcular_posiciones(df_ops, precio_dolar):
    if df_ops.empty: return pd.DataFrame(), 0, pd.DataFrame()
    df = df_ops.copy()
    if 'moneda' not in df.columns: df['moneda'] = 'USD'
    df['moneda'] = df['moneda'].fillna('USD')
    df['cantidad_neta'] = df.apply(lambda row: row['cantidad'] if row['tipo'] == 'Compra' else -row['cantidad'], axis=1)
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
        if row['moneda'] == 'ARS': ganancia_realizada_usd += (val / precio_dolar)
        else: ganancia_realizada_usd += val
    
    beneficios_realizados_df = posiciones[['ticker', 'beneficio_realizado_original', 'moneda']]
    
    if not posiciones_abiertas.empty:
        tickers_list = posiciones_abiertas['ticker'].unique().tolist()
        precios_actuales = obtener_datos_mercado(tickers_list)
        posiciones_abiertas['precio_actual'] = posiciones_abiertas['ticker'].map(precios_actuales).fillna(0)
        
        def calcular_valor_usd(row):
            if row['precio_actual'] == 0: return 0
            valor_local = row['cantidad_total'] * row['precio_actual']
            if row['moneda'] == 'ARS': return valor_local / precio_dolar
            return valor_local
        posiciones_abiertas['valor_mercado_usd'] = posiciones_abiertas.apply(calcular_valor_usd, axis=1)
        
        def calcular_coste_usd(row):
            coste_local = row['cantidad_total'] * row['ppp_original']
            if row['moneda'] == 'ARS': return coste_local / precio_dolar 
            return coste_local
        posiciones_abiertas['coste_total_usd'] = posiciones_abiertas.apply(calcular_coste_usd, axis=1)
        posiciones_abiertas['ganancia_no_realizada_usd'] = posiciones_abiertas['valor_mercado_usd'] - posiciones_abiertas['coste_total_usd']
        posiciones_abiertas['rentabilidad_%'] = posiciones_abiertas.apply(lambda x: (x['ganancia_no_realizada_usd'] / x['coste_total_usd'] * 100) if x['coste_total_usd'] > 0 else 0, axis=1)
    return posiciones_abiertas, ganancia_realizada_usd, beneficios_realizados_df

# *** GRÁFICO DE EVOLUCIÓN REACTIVADO ***
@st.cache_data(ttl=600)
def calcular_evolucion_patrimonio(df_ops, precio_dolar):
    if df_ops.empty: return None
    df_ops['fecha'] = pd.to_datetime(df_ops['fecha'])
    tickers = df_ops['ticker'].unique().tolist()
    start_date = df_ops['fecha'].min()
    try:
        precios_historicos = yf.download(tickers, start=start_date, progress=False)['Close']
        if isinstance(precios_historicos.index, pd.DatetimeIndex):
            precios_historicos = precios_historicos.loc[~precios_historicos.index.duplicated(keep='first')]
    except: return None
    rango_fechas = pd.date_range(start=start_date, end=date.today())
    patrimonio_diario = pd.DataFrame(index=rango_fechas)
    for ticker in tickers:
        ops_ticker = df_ops[df_ops['ticker'] == ticker].copy()
        ops_ticker['cantidad_neta'] = ops_ticker['cantidad'].where(ops_ticker['tipo'] == 'Compra', -ops_ticker['cantidad'])
        ops_diarias = ops_ticker.groupby('fecha')['cantidad_neta'].sum()
        tenencias_diarias = ops_diarias.cumsum().reindex(patrimonio_diario.index, method='ffill').fillna(0)
        
        if isinstance(precios_historicos, pd.DataFrame) and ticker in precios_historicos.columns:
            precio_serie = precios_historicos[ticker]
        elif isinstance(precios_historicos, pd.Series) and precios_historicos.name == ticker:
            precio_serie = precios_historicos
        else: precio_serie = 0
        
        valor_diario = tenencias_diarias * precio_serie.reindex(patrimonio_diario.index, method='ffill')
        # Convertimos activos .BA a dólares
        if ticker.endswith('.BA'): valor_diario = valor_diario / precio_dolar
        patrimonio_diario[ticker] = valor_diario
        
    patrimonio_diario['Total USD'] = patrimonio_diario.sum(axis=1)
    return patrimonio_diario[['Total USD']].reset_index().rename(columns={'index': 'Fecha'})

def estilo_ganancia(val):
    if pd.isna(val) or val == 0: return 'color: inherit; background-color: transparent;'
    if val > 0: return 'background-color: rgba(40, 167, 69, 0.4); color: #111;'
    else: return 'background-color: rgba(220, 53, 69, 0.4); color: #111;'

# --- INTERFAZ ---
st.set_page_config(layout="wide", page_title="Dashboard")
st.title(f"Dashboard de {st.session_state.user[1]} 📊")
precio_dolar_hoy, fuente_dolar = obtener_dolar_argentina()
operaciones_df = ver_operaciones(USER_ID)

st.sidebar.markdown("---")
st.sidebar.metric("Cotización Dólar", f"${precio_dolar_hoy:,.0f} ARS")
st.sidebar.caption(f"Fuente: {fuente_dolar}")

posiciones_df, ganancia_realizada_total, _ = calcular_posiciones(operaciones_df, precio_dolar_hoy)
total_aportado, total_retirado = obtener_aportaciones_retiros(USER_ID, precio_dolar_hoy)
saldo_efectivo_usd, saldo_efectivo_ars = calcular_efectivo_actual(USER_ID)

st.header("Resumen General (Base USD)")
if not operaciones_df.empty or total_aportado > 0 or saldo_efectivo_usd != 0:
    valor_acciones_usd = posiciones_df['valor_mercado_usd'].sum() if 'valor_mercado_usd' in posiciones_df.columns else 0
    valor_efectivo_ars_en_usd = saldo_efectivo_ars / precio_dolar_hoy
    patrimonio_total_usd = valor_acciones_usd + saldo_efectivo_usd + valor_efectivo_ars_en_usd
    ganancia_no_realizada_total = posiciones_df['ganancia_no_realizada_usd'].sum() if 'ganancia_no_realizada_usd' in posiciones_df.columns else 0
    beneficio_total = ganancia_no_realizada_total + ganancia_realizada_total
    capital_neto_aportado = total_aportado - total_retirado
    rentabilidad = (beneficio_total / capital_neto_aportado) * 100 if capital_neto_aportado > 0 else 0
    
    st.subheader("Resultados del Portafolio")
    r1 = st.columns(4)
    r1[0].metric("Patrimonio Total", f"US$ {patrimonio_total_usd:,.2f}")
    r1[1].metric("Beneficio Total", f"US$ {beneficio_total:,.2f}")
    r1[2].metric("Capital Neto", f"US$ {capital_neto_aportado:,.2f}")
    r1[3].metric("Rentabilidad", f"{rentabilidad:.2f}%", delta_color="off")
    st.subheader("Componentes")
    r2 = st.columns(4)
    r2[0].metric("Valor en Acciones", f"US$ {valor_acciones_usd:,.2f}")
    r2[1].metric("Efectivo en USD", f"US$ {saldo_efectivo_usd:,.2f}")
    r2[2].metric("Efectivo en ARS", f"AR$ {saldo_efectivo_ars:,.2f}", f"(aprox. US$ {valor_efectivo_ars_en_usd:,.2f})")
    r2[3].metric("Beneficio Realizado", f"US$ {ganancia_realizada_total:,.2f}")
else:
    st.info("Añade operaciones o aportes para ver tu dashboard.")

st.divider()
st.header("Análisis Visual")
c1, c2 = st.columns(2)
with c1:
    if not posiciones_df.empty:
        fig = px.pie(posiciones_df, values='valor_mercado_usd', names='ticker', title='Diversificación (USD)', hole=.3)
        st.plotly_chart(fig, use_container_width=True)
    else: st.info("Sin datos.")
with c2:
    evolucion_df = calcular_evolucion_patrimonio(operaciones_df, precio_dolar_hoy)
    if evolucion_df is not None and not evolucion_df.empty:
        fig = px.area(evolucion_df, x='Fecha', y='Total USD', title='Evolución Histórica (Estimada en USD)')
        st.plotly_chart(fig, use_container_width=True)
    else: st.info("Se necesitan más datos históricos para generar la evolución.")

st.divider()
with st.form("operacion_form", clear_on_submit=True):
    st.header("Añadir Nueva Operación")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        fecha_op = st.date_input("Fecha", value=date.today())
        ticker_op = st.text_input("Ticker")
    with c2:
        tipo_op = st.selectbox("Tipo", ["Compra", "Venta"])
        moneda_op = st.selectbox("Moneda", ["USD", "ARS"])
    with c3:
        cantidad_op = st.number_input("Cantidad", min_value=0.0, step=0.0001, format="%.4f")
    with c4:
        precio_op = st.number_input("Precio Unitario", min_value=0.0, step=0.0001, format="%.4f")
    if st.form_submit_button("Añadir Operación"):
        if not ticker_op or cantidad_op <= 0: st.warning("Datos inc.")
        else:
            ticker_final = ticker_op.upper()
            criptos = ["BTC", "ETH", "SOL", "USDT", "BNB", "XRP", "ADA", "DOGE", "SHIB", "DOT", "DAI", "MATIC", "AVAX", "TRX", "LTC", "LINK", "ATOM", "UNI"]
            if ticker_final in criptos: ticker_final = f"{ticker_final}-USD"
            anadir_operacion(fecha_op, ticker_final, tipo_op, cantidad_op, precio_op, moneda_op, USER_ID)
            st.success("Añadido.")
            st.rerun()

st.header("Posiciones Actuales")
if not posiciones_df.empty:
    df_show = posiciones_df[['ticker', 'moneda', 'cantidad_total', 'ppp_original', 'precio_actual', 'valor_mercado_usd', 'ganancia_no_realizada_usd', 'rentabilidad_%']].rename(columns={'ticker': 'Ticker', 'moneda': 'Moneda', 'cantidad_total': 'Cant', 'ppp_original': 'Precio Prom', 'precio_actual': 'Precio Hoy', 'valor_mercado_usd': 'Valor (USD)', 'ganancia_no_realizada_usd': 'Ganancia (USD)', 'rentabilidad_%': 'Rentabilidad %'})
    st.dataframe(df_show.style.applymap(estilo_ganancia, subset=['Ganancia (USD)']).format({'Precio Prom': '${:,.2f}', 'Precio Hoy': '${:,.2f}', 'Valor (USD)': 'US$ {:,.2f}', 'Ganancia (USD)': 'US$ {:,.2f}', 'Rentabilidad %': '{:,.2f}%'}, na_rep="-"), use_container_width=True)

st.header("Historial de Operaciones")
if not operaciones_df.empty:
    if 'moneda' not in operaciones_df.columns: operaciones_df['moneda'] = 'USD'
    df_hist = operaciones_df.sort_values(by="fecha", ascending=False).rename(columns={'id':'ID', 'fecha':'Fecha', 'ticker':'Ticker', 'tipo':'Tipo', 'moneda':'Moneda', 'cantidad':'Cant', 'precio':'Precio'})
    cols = st.columns([0.5, 1, 1, 0.8, 0.8, 1, 1, 0.5])
    for c, h in zip(cols, ["ID", "Fecha", "Ticker", "Tipo", "Moneda", "Cant", "Precio", "Acción"]): c.markdown(f"**{h}**")
    st.divider()
    for idx, row in df_hist.iterrows():
        cols = st.columns([0.5, 1, 1, 0.8, 0.8, 1, 1, 0.5])
        cols[0].write(row['ID'])
        cols[1].write(row['Fecha'])
        cols[2].write(row['Ticker'])
        cols[3].write(row['Tipo'])
        cols[4].write(row['Moneda'])
        cols[5].write(f"{row['Cant']:.4f}")
        cols[6].write(f"${row['Precio']:,.4f}")
        if cols[7].button("🗑️", key=f"del_{row['ID']}"):
            eliminar_operacion(row['ID'], USER_ID)
            st.rerun()