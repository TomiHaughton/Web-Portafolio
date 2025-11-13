import streamlit as st
import sqlite3
from datetime import date
import pandas as pd
import yfinance as yf
import plotly.express as px
import requests

# --- VERIFICADOR DE SESIÓN ---
if 'user' not in st.session_state or st.session_state.user is None:
    st.error("Debes iniciar sesión para acceder a esta página.")
    st.stop()
USER_ID = st.session_state.user[0]

# --- CSS ---
st.markdown("""<style>.stDataFrame th, .stDataFrame td {text-align: center;}</style>""", unsafe_allow_html=True)

# --- FUNCIONES DE BASE DE DATOS ---
def conectar_db():
    return sqlite3.connect('portfolio.db')

def verificar_y_migrar_db():
    conexion = conectar_db()
    cursor = conexion.cursor()
    try:
        cursor.execute("SELECT moneda FROM operaciones LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE operaciones ADD COLUMN moneda TEXT DEFAULT 'USD'")
        conexion.commit()
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

# --- FUNCIONES DE DATOS ---
@st.cache_data(ttl=300)
def obtener_dolar_argentina():
    precio = None
    fuente = "API"
    try:
        response = requests.get("https://dolarapi.com/v1/dolares/cripto", timeout=5)
        if response.status_code == 200:
            data = response.json()
            precio = float(data['venta'])
            fuente = "DolarApi"
    except: pass
    
    if precio is None:
        try:
            ticker = yf.Ticker("ARS=X")
            hist = ticker.history(period="1d")
            if not hist.empty:
                precio = hist['Close'].iloc[-1]
                if precio < 100: precio = None 
                else: fuente = "Yahoo"
        except: pass
            
    if precio is None:
        precio = 1150.0
        fuente = "Estimado"
    return precio, fuente

@st.cache_data(ttl=600)
def obtener_datos_mercado(tickers):
    if not tickers: return {}, 1
    try:
        data = yf.Tickers(tickers).history(period='1d')
        precios = data['Close'].iloc[-1].to_dict() if not data.empty else {}
    except:
        precios = {}
    return precios

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

# *** FUNCIÓN REACTIVADA Y MEJORADA ***
@st.cache_data(ttl=600)
def calcular_evolucion_patrimonio(df_ops, precio_dolar):
    if df_ops.empty: return None
    
    df_ops['fecha'] = pd.to_datetime(df_ops['fecha'])
    tickers = df_ops['ticker'].unique().tolist()
    start_date = df_ops['fecha'].min()
    
    # Descargamos precios históricos
    try:
        precios_historicos = yf.download(tickers, start=start_date, progress=False)['Close']
        # Limpieza de duplicados en índice
        if isinstance(precios_historicos.index, pd.DatetimeIndex):
            precios_historicos = precios_historicos.loc[~precios_historicos.index.duplicated(keep='first')]
    except:
        return None

    rango_fechas = pd.date_range(start=start_date, end=date.today())
    patrimonio_diario = pd.DataFrame(index=rango_fechas)

    for ticker in tickers:
        ops_ticker = df_ops[df_ops['ticker'] == ticker].copy()
        ops_ticker['cantidad_neta'] = ops_ticker['cantidad'].where(ops_ticker['tipo'] == 'Compra', -ops_ticker['cantidad'])
        ops_diarias = ops_ticker.groupby('fecha')['cantidad_neta'].sum()
        tenencias_diarias = ops_diarias.cumsum().reindex(patrimonio_diario.index, method='ffill').fillna(0)
        
        # Obtenemos el precio histórico del ticker
        if isinstance(precios_historicos, pd.DataFrame) and ticker in precios_historicos.columns:
            precio_serie = precios_historicos[ticker]
        elif isinstance(precios_historicos, pd.Series) and precios_historicos.name == ticker:
            precio_serie = precios_historicos
        else:
            precio_serie = 0
            
        # Calculamos valor diario
        valor_diario = tenencias_diarias * precio_serie.reindex(patrimonio_diario.index, method='ffill')
        
        # *** CONVERSIÓN INTELIGENTE ***
        # Si el ticker es argentino (termina en .BA), dividimos por el dólar actual
        # para normalizar la curva y que no se dispare en pesos.
        if ticker.endswith('.BA'):
            valor_diario = valor_diario / precio_dolar
            
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

verificar_y_migrar_db()

precio_dolar_hoy, fuente_dolar = obtener_dolar_argentina()
operaciones_df = ver_operaciones(USER_ID)

st.sidebar.markdown("---")
st.sidebar.metric("Cotización Dólar", f"${precio_dolar_hoy:,.0f} ARS")
st.sidebar.caption(f"Fuente: {fuente_dolar}")

posiciones_df, ganancia_realizada_total, _ = calcular_posiciones(operaciones_df, precio_dolar_hoy)
total_aportado, total_retirado = obtener_aportaciones_retiros(USER_ID)

st.header("Resumen General (Base USD)")
if not operaciones_df.empty:
    valor_total_portafolio = posiciones_df['valor_mercado_usd'].sum() if 'valor_mercado_usd' in posiciones_df.columns else 0
    ganancia_no_realizada_total = posiciones_df['ganancia_no_realizada_usd'].sum() if 'ganancia_no_realizada_usd' in posiciones_df.columns else 0
    beneficio_total = ganancia_no_realizada_total + ganancia_realizada_total
    capital_neto_aportado = total_aportado - total_retirado
    rentabilidad = (beneficio_total / capital_neto_aportado) * 100 if capital_neto_aportado > 0 else 0
    
    st.subheader("Resultados del Portafolio")
    r1 = st.columns(4)
    r1[0].metric("Patrimonio Total", f"US$ {valor_total_portafolio:,.2f}")
    r1[1].metric("Beneficio Total", f"US$ {beneficio_total:,.2f}")
    r1[2].metric("Capital Neto", f"US$ {capital_neto_aportado:,.2f}")
    r1[3].metric("Rentabilidad", f"{rentabilidad:.2f}%", delta_color="off")

    st.subheader("Componentes")
    r2 = st.columns(4)
    r2[0].metric("Beneficio No Realizado", f"US$ {ganancia_no_realizada_total:,.2f}")
    r2[1].metric("Beneficio Realizado", f"US$ {ganancia_realizada_total:,.2f}")
    r2[2].metric("Total Aportado", f"US$ {total_aportado:,.2f}")
    r2[3].metric("Total Retirado", f"-US$ {total_retirado:,.2f}")
else:
    st.info("Añade operaciones para ver tu dashboard.")

st.divider()

st.header("Análisis Visual")
c_graf1, c_graf2 = st.columns(2)
with c_graf1:
    if not posiciones_df.empty:
        fig_div = px.pie(posiciones_df, values='valor_mercado_usd', names='ticker', title='Diversificación (USD)', hole=.3)
        st.plotly_chart(fig_div, use_container_width=True)
    else:
        st.info("Sin datos.")
with c_graf2:
    # *** GRÁFICO REACTIVADO ***
    evolucion_df = calcular_evolucion_patrimonio(operaciones_df, precio_dolar_hoy)
    if evolucion_df is not None and not evolucion_df.empty:
        fig_ev = px.area(evolucion_df, x='Fecha', y='Total USD', title='Evolución Histórica (Estimada en USD)')
        st.plotly_chart(fig_ev, use_container_width=True)
    else:
        st.info("Se necesitan más datos históricos para generar la evolución.")

st.divider()

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
            criptos_comunes = ["BTC", "ETH", "SOL", "USDT", "BNB", "XRP", "ADA", "DOGE", "SHIB", "DOT", "DAI", "MATIC", "AVAX", "TRX", "LTC", "LINK", "ATOM", "UNI"]
            if ticker_final in criptos_comunes: ticker_final = f"{ticker_final}-USD"
            
            anadir_operacion(fecha_op, ticker_final, tipo_op, cantidad_op, precio_op, moneda_op, USER_ID)
            st.success(f"Operación añadida.")
            st.rerun()

st.header("Posiciones Actuales")
if not posiciones_df.empty:
    df_show = posiciones_df[['ticker', 'moneda', 'cantidad_total', 'ppp_original', 'precio_actual', 'valor_mercado_usd', 'ganancia_no_realizada_usd', 'rentabilidad_%']].rename(columns={'ticker': 'Ticker', 'moneda': 'Moneda', 'cantidad_total': 'Cant', 'ppp_original': 'Precio Prom (Orig)', 'precio_actual': 'Precio Hoy', 'valor_mercado_usd': 'Valor (USD)', 'ganancia_no_realizada_usd': 'Ganancia (USD)', 'rentabilidad_%': 'Rentabilidad %'})
    st.dataframe(df_show.style.applymap(estilo_ganancia, subset=['Ganancia (USD)']).format({'Precio Prom (Orig)': '${:,.2f}', 'Precio Hoy': '${:,.2f}', 'Valor (USD)': 'US$ {:,.2f}', 'Ganancia (USD)': 'US$ {:,.2f}', 'Rentabilidad %': '{:,.2f}%'}, na_rep="-").set_table_styles([dict(selector="th", props=[("text-align", "center")]), dict(selector="td", props=[("text-align", "center")])]), use_container_width=True)

st.header("Historial de Operaciones")
if not operaciones_df.empty:
    if 'moneda' not in operaciones_df.columns: operaciones_df['moneda'] = 'USD'
    df_hist = operaciones_df.sort_values(by="fecha", ascending=False).rename(columns={'id':'ID', 'fecha':'Fecha', 'ticker':'Ticker', 'tipo':'Tipo', 'moneda':'Moneda', 'cantidad':'Cant', 'precio':'Precio'})
    cols = st.columns([0.5, 1, 1, 0.8, 0.8, 1, 1, 0.5])
    headers = ["ID", "Fecha", "Ticker", "Tipo", "Moneda", "Cant", "Precio", "Acción"]
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
        cols[6].write(f"${row['Precio']:,.4f}")
        if cols[7].button("🗑️", key=f"del_{row['ID']}"):
            eliminar_operacion(row['ID'], USER_ID)
            st.rerun()