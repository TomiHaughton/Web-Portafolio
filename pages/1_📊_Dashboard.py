import streamlit as st
import sqlite3
from datetime import date
import pandas as pd
import yfinance as yf
import plotly.express as px

# --- VERIFICADOR Y CSS (sin cambios) ---
if 'user' not in st.session_state or st.session_state.user is None:
    st.error("Debes iniciar sesión para acceder a esta página.")
    st.stop()
USER_ID = st.session_state.user[0]
st.markdown("""<style>.stDataFrame th, .stDataFrame td {text-align: center;}</style>""", unsafe_allow_html=True)

# --- FUNCIONES ---
def conectar_db():
    return sqlite3.connect('portfolio.db')
# ... (funciones ver_operaciones, obtener_aportaciones_retiros, obtener_precios_actuales, calcular_posiciones, etc. sin cambios)
def anadir_operacion(fecha, ticker, tipo, cantidad, precio, user_id):
    conexion = conectar_db()
    cursor = conexion.cursor()
    cursor.execute("INSERT INTO operaciones (fecha, ticker, tipo, cantidad, precio, user_id) VALUES (?, ?, ?, ?, ?, ?)", (fecha, ticker, tipo, cantidad, precio, user_id))
    conexion.commit()
    conexion.close()
    
# *** NUEVA FUNCIÓN PARA ELIMINAR OPERACIONES ***
def eliminar_operacion(operacion_id, user_id):
    conexion = conectar_db()
    cursor = conexion.cursor()
    cursor.execute("DELETE FROM operaciones WHERE id = ? AND user_id = ?", (operacion_id, user_id))
    conexion.commit()
    conexion.close()
# ... (El resto de funciones siguen aquí)
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
@st.cache_data(ttl=600)
def obtener_precios_actuales(tickers):
    if not tickers: return {}
    data = yf.Tickers(tickers).history(period='1d')
    precios = data['Close'].iloc[-1].to_dict()
    return precios
def calcular_posiciones(df_ops):
    if df_ops.empty: return pd.DataFrame(), 0, pd.DataFrame()
    df = df_ops.copy()
    df['cantidad_neta'] = df.apply(lambda row: row['cantidad'] if row['tipo'] == 'Compra' else -row['cantidad'], axis=1)
    df['coste_total_compra'] = df.apply(lambda row: row['cantidad'] * row['precio'] if row['tipo'] == 'Compra' else 0, axis=1)
    df['cantidad_vendida'] = df.apply(lambda row: row['cantidad'] if row['tipo'] == 'Venta' else 0, axis=1)
    df['ingreso_total_venta'] = df.apply(lambda row: row['cantidad'] * row['precio'] if row['tipo'] == 'Venta' else 0, axis=1)
    posiciones = df.groupby('ticker').agg(cantidad_total=('cantidad_neta', 'sum'), coste_total=('coste_total_compra', 'sum'), cantidad_total_vendida=('cantidad_vendida', 'sum'), ingreso_total=('ingreso_total_venta', 'sum')).reset_index()
    compras_totales = df[df['tipo'] == 'Compra'].groupby('ticker')['cantidad'].sum()
    posiciones = posiciones.merge(compras_totales.rename('cantidad_comprada'), on='ticker', how='left')
    posiciones['cantidad_comprada'] = posiciones['cantidad_comprada'].fillna(0)
    posiciones['precio_promedio_compra'] = posiciones.apply(lambda row: row['coste_total'] / row['cantidad_comprada'] if row['cantidad_comprada'] > 0 else 0, axis=1)
    posiciones['coste_de_lo_vendido'] = posiciones['precio_promedio_compra'] * posiciones['cantidad_total_vendida']
    posiciones['beneficio_realizado'] = posiciones['ingreso_total'] - posiciones['coste_de_lo_vendido']
    ganancia_realizada_total = posiciones['beneficio_realizado'].sum()
    beneficios_realizados_por_ticker = posiciones[posiciones['beneficio_realizado'] != 0][['ticker', 'beneficio_realizado']]
    posiciones_abiertas = posiciones[posiciones['cantidad_total'] > 0].copy()
    if not posiciones_abiertas.empty:
        tickers_list = posiciones_abiertas['ticker'].unique().tolist()
        precios_actuales = obtener_precios_actuales(tickers_list)
        posiciones_abiertas['precio_actual'] = posiciones_abiertas['ticker'].map(precios_actuales).fillna(0)
        posiciones_abiertas['valor_mercado'] = posiciones_abiertas['cantidad_total'] * posiciones_abiertas['precio_actual']
        posiciones_abiertas['coste_total_actual'] = posiciones_abiertas['cantidad_total'] * posiciones_abiertas['precio_promedio_compra']
        posiciones_abiertas['ganancia_no_realizada'] = posiciones_abiertas['valor_mercado'] - posiciones_abiertas['coste_total_actual']
        posiciones_abiertas['rentabilidad_%'] = (posiciones_abiertas['ganancia_no_realizada'] / posiciones_abiertas['coste_total_actual']) * 100
    return posiciones_abiertas, ganancia_realizada_total, beneficios_realizados_por_ticker
@st.cache_data(ttl=600)
def calcular_evolucion_patrimonio(df_ops):
    if df_ops.empty: return None
    df_ops['fecha'] = pd.to_datetime(df_ops['fecha'])
    tickers = df_ops['ticker'].unique().tolist()
    start_date = df_ops['fecha'].min()
    precios_historicos = yf.download(tickers, start=start_date, progress=False)['Close']
    if isinstance(precios_historicos.index, pd.DatetimeIndex):
        precios_historicos = precios_historicos.loc[~precios_historicos.index.duplicated(keep='first')]
    rango_fechas = pd.date_range(start=start_date, end=date.today())
    patrimonio_diario = pd.DataFrame(index=rango_fechas)
    for ticker in tickers:
        ops_ticker = df_ops[df_ops['ticker'] == ticker].copy()
        ops_ticker['cantidad_neta'] = ops_ticker['cantidad'].where(ops_ticker['tipo'] == 'Compra', -ops_ticker['cantidad'])
        ops_diarias = ops_ticker.groupby('fecha')['cantidad_neta'].sum()
        tenencias_diarias = ops_diarias.cumsum().reindex(patrimonio_diario.index, method='ffill').fillna(0)
        if isinstance(precios_historicos, pd.DataFrame) and ticker in precios_historicos.columns:
            patrimonio_diario[ticker] = tenencias_diarias * precios_historicos[ticker].reindex(patrimonio_diario.index, method='ffill')
        elif isinstance(precios_historicos, pd.Series) and precios_historicos.name == ticker:
             patrimonio_diario[ticker] = tenencias_diarias * precios_historicos.reindex(patrimonio_diario.index, method='ffill')
        else:
            patrimonio_diario[ticker] = 0
    patrimonio_diario['Total'] = patrimonio_diario.sum(axis=1)
    return patrimonio_diario[['Total']].reset_index().rename(columns={'index': 'Fecha'})
def estilo_ganancia(val):
    if pd.isna(val) or val == 0: return 'color: inherit; background-color: transparent;'
    if val > 0: return 'background-color: rgba(40, 167, 69, 0.4); color: #111;'
    else: return 'background-color: rgba(220, 53, 69, 0.4); color: #111;'

# --- INTERFAZ ---
st.set_page_config(layout="wide", page_title="Dashboard")
st.title(f"Dashboard de {st.session_state.user[1]} 📊")
operaciones_df = ver_operaciones(USER_ID)
posiciones_df, ganancia_realizada_total, _ = calcular_posiciones(operaciones_df)
total_aportado, total_retirado = obtener_aportaciones_retiros(USER_ID)
# ... (código del Resumen General y Análisis Visual sin cambios) ...
st.header("Resumen General")
if not operaciones_df.empty:
    valor_total_portafolio = posiciones_df['valor_mercado'].sum() if 'valor_mercado' in posiciones_df.columns else 0
    ganancia_no_realizada_total = posiciones_df['ganancia_no_realizada'].sum() if 'ganancia_no_realizada' in posiciones_df.columns else 0
    beneficio_total = ganancia_no_realizada_total + ganancia_realizada_total
    capital_neto_aportado = total_aportado - total_retirado
    rentabilidad = (beneficio_total / capital_neto_aportado) * 100 if capital_neto_aportado > 0 else 0
    st.subheader("Resultados del Portafolio")
    row1_cols = st.columns(4)
    row1_cols[0].metric("Patrimonio Total", f"${valor_total_portafolio:,.2f}")
    row1_cols[1].metric("Beneficio Total", f"${beneficio_total:,.2f}")
    row1_cols[2].metric("Capital Neto Invertido", f"${capital_neto_aportado:,.2f}")
    row1_cols[3].metric("Rentabilidad Total", f"{rentabilidad:.2f}%", delta_color="off")
    st.subheader("Componentes")
    row2_cols = st.columns(4)
    row2_cols[0].metric("Beneficio No Realizado", f"${ganancia_no_realizada_total:,.2f}")
    row2_cols[1].metric("Beneficio Realizado", f"${ganancia_realizada_total:,.2f}")
    row2_cols[2].metric("Total Aportado", f"${total_aportado:,.2f}")
    row2_cols[3].metric("Total Retirado", f"-${total_retirado:,.2f}")
else:
    st.info("Añade operaciones para ver tu dashboard.")

st.divider()
st.header("Análisis Visual")
col_graf1, col_graf2 = st.columns(2)
with col_graf1:
    if not posiciones_df.empty:
        fig_diversificacion = px.pie(posiciones_df, values='valor_mercado', names='ticker', title='Diversificación del Portafolio por Activo', hole=.3)
        st.plotly_chart(fig_diversificacion, use_container_width=True)
    else:
        st.info("No hay posiciones para mostrar el gráfico de diversificación.")
with col_graf2:
    evolucion_df = calcular_evolucion_patrimonio(operaciones_df)
    if evolucion_df is not None:
        fig_evolucion = px.area(evolucion_df, x='Fecha', y='Total', title='Evolución del Patrimonio a lo Largo del Tiempo')
        st.plotly_chart(fig_evolucion, use_container_width=True)
    else:
        st.info("Añade operaciones para ver la evolución de tu patrimonio.")

st.divider()

with st.form("operacion_form", clear_on_submit=True):
    st.header("Añadir Nueva Operación")
    col1, col2, col3 = st.columns(3)
    with col1:
        fecha_op = st.date_input("Fecha", value=date.today())
        ticker_op = st.text_input("Ticker (ej. AAPL, BTC)")
    with col2:
        tipo_op = st.selectbox("Tipo de Operación", ["Compra", "Venta"])
        cantidad_op = st.number_input("Cantidad", min_value=0.0, step=0.01, format="%.2f")
    with col3:
        precio_op = st.number_input("Precio por unidad", min_value=0.0, step=0.01, format="%.2f")
    submitted = st.form_submit_button("Añadir Operación")
    if submitted:
        if not ticker_op or cantidad_op <= 0 or precio_op <= 0:
            st.warning("Por favor, completa todos los campos correctamente.")
        else:
            ticker_final = ticker_op.upper()
            criptos_comunes = ["BTC", "ETH", "SOL", "USDT", "BNB", "XRP", "ADA", "DOGE", "SHIB"]
            if ticker_final in criptos_comunes:
                ticker_final = f"{ticker_final}-USD"
            anadir_operacion(fecha_op, ticker_final, tipo_op, cantidad_op, precio_op, USER_ID)
            st.success(f"¡Operación de {tipo_op} para {ticker_final} añadida con éxito!")
            st.rerun()

# ... (código de la tabla Posiciones Actuales sin cambios) ...
st.header("Posiciones Actuales")
if posiciones_df.empty:
    st.info("No tienes posiciones abiertas.")
else:
    df_display = posiciones_df[['ticker', 'cantidad_total', 'precio_promedio_compra', 'precio_actual', 'valor_mercado', 'ganancia_no_realizada', 'rentabilidad_%']].rename(columns={'ticker': 'Ticker', 'cantidad_total': 'Cantidad', 'precio_promedio_compra': 'Precio Compra Prom.', 'precio_actual': 'Precio Actual', 'valor_mercado': 'Valor de Mercado', 'ganancia_no_realizada': 'Ganancia/Pérdida', 'rentabilidad_%': 'Rentabilidad %'})
    st.dataframe(df_display.style.applymap(estilo_ganancia, subset=['Ganancia/Pérdida']).format({'Precio Compra Prom.': '${:,.2f}', 'Precio Actual': '${:,.2f}', 'Valor de Mercado': '${:,.2f}', 'Ganancia/Pérdida': '${:,.2f}', 'Rentabilidad %': '{:,.2f}%'}, na_rep="-").set_table_styles([dict(selector="th", props=[("text-align", "center")]), dict(selector="td", props=[("text-align", "center")])]), use_container_width=True)

# *** CAMBIO: Modificamos la tabla de Historial para añadir botones de eliminar ***
st.header("Historial de Operaciones")
if operaciones_df.empty:
    st.info("Aún no has añadido ninguna operación.")
else:
    df_historial = operaciones_df.sort_values(by="fecha", ascending=False).rename(columns={'id': 'ID', 'fecha': 'Fecha', 'ticker': 'Ticker', 'tipo': 'Tipo', 'cantidad': 'Cantidad', 'precio': 'Precio'})
    
    # Creamos las columnas para la tabla manual
    column_widths = [0.5, 1, 1, 0.8, 1, 1, 0.5]
    cols = st.columns(column_widths)
    headers = ["ID", "Fecha", "Ticker", "Tipo", "Cantidad", "Precio", "Acción"]
    for col, header in zip(cols, headers):
        col.markdown(f"**{header}**")

    st.divider()

    # Iteramos sobre los datos para mostrar cada fila con su botón
    for index, row in df_historial.iterrows():
        cols = st.columns(column_widths)
        cols[0].write(row['ID'])
        cols[1].write(row['Fecha'])
        cols[2].write(row['Ticker'])
        cols[3].write(row['Tipo'])
        cols[4].write(row['Cantidad'])
        cols[5].write(f"${row['Precio']:,.2f}")
        # El botón de eliminar necesita una 'key' única
        if cols[6].button("🗑️", key=f"del_op_{row['ID']}"):
            eliminar_operacion(row['ID'], USER_ID)
            st.rerun()