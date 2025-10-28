import streamlit as st
import sqlite3
import pandas as pd
import yfinance as yf
from datetime import date

# --- VERIFICADOR DE SESIÓN ---
if 'user' not in st.session_state or st.session_state.user is None:
    st.error("Debes iniciar sesión para acceder a esta página.")
    st.stop()
USER_ID = st.session_state.user[0]

# --- FUNCIONES ---
def conectar_db():
    return sqlite3.connect('portfolio.db')
def ver_operaciones(user_id):
    conexion = conectar_db()
    df = pd.read_sql_query("SELECT * FROM operaciones WHERE user_id = ? ORDER BY fecha ASC", conexion, params=(user_id,))
    conexion.close()
    return df
@st.cache_data(ttl=600)
def obtener_precios_actuales(tickers):
    if not tickers: return {}
    data = yf.Tickers(tickers).history(period='1d')
    precios = data['Close'].iloc[-1].to_dict()
    return precios
def calcular_cantidad_actual(df_ops):
    if df_ops.empty: return pd.DataFrame()
    df = df_ops.copy()
    df['cantidad_neta'] = df.apply(lambda row: row['cantidad'] if row['tipo'] == 'Compra' else -row['cantidad'], axis=1)
    posiciones = df.groupby('ticker').agg(cantidad_total=('cantidad_neta', 'sum')).reset_index()
    posiciones_abiertas = posiciones[posiciones['cantidad_total'] > 0].copy()
    return posiciones_abiertas[['ticker', 'cantidad_total']]

# --- FUNCIÓN DE DIVIDENDOS (ACTUALIZADA con Frecuencia Mejorada) ---
@st.cache_data(ttl=3600)
def obtener_info_dividendos(tickers):
    data = {}
    for ticker_str in tickers:
        div_rate = 0
        frecuencia = "N/A"
        ex_div_date = "N/A"
        pay_date = "N/A"
        try:
            ticker_obj = yf.Ticker(ticker_str)
            info = ticker_obj.info
            div_rate = info.get('dividendRate', 0)
            div_rate = div_rate if div_rate is not None else 0

            # Calculamos frecuencia de forma más segura, analizando intervalos
            try:
                divs = ticker_obj.dividends
                if not divs.empty and len(divs) > 1:
                    # Calculamos los días entre los últimos pagos
                    intervalos = divs.index.to_series().diff().dt.days.dropna()
                    if not intervalos.empty:
                        # Usamos la mediana para ser robustos a pagos irregulares
                        mediana_intervalo = intervalos.median()
                        if 25 <= mediana_intervalo <= 35: frecuencia = "Mensual"
                        elif 80 <= mediana_intervalo <= 100: frecuencia = "Trimestral"
                        elif 170 <= mediana_intervalo <= 190: frecuencia = "Semestral"
                        elif 350 <= mediana_intervalo <= 370: frecuencia = "Anual"
                        else: frecuencia = "Irregular"
                    else: # Solo un dividendo histórico
                        frecuencia = "Anual/Único?"
                elif not divs.empty and len(divs) == 1:
                     frecuencia = "Anual/Único?"
                elif div_rate > 0: # Paga pero no hay historial suficiente
                    frecuencia = "Paga (freq. ?)"
                else:
                    frecuencia = "No Paga"
            except Exception:
                frecuencia = "N/A" # Si falla el cálculo

            # Fechas del calendario
            try:
                calendar = ticker_obj.calendar
                ex_div_val = calendar.get('Ex-Dividend Date')
                pay_val = calendar.get('Dividend Date')
                ex_div_date = pd.to_datetime(ex_div_val).strftime('%Y-%m-%d') if pd.notna(ex_div_val) else "N/A"
                pay_date = pd.to_datetime(pay_val).strftime('%Y-%m-%d') if pd.notna(pay_val) else "N/A"
            except Exception:
                 ex_div_date = "N/A"
                 pay_date = "N/A"
        except Exception:
            div_rate = 0
            frecuencia = "Error Ticker"
            
        data[ticker_str] = {
            'dividendo_anual_accion': div_rate,
            'frecuencia_estimada': frecuencia,
            'prox_fecha_ex_div': ex_div_date,
            'prox_fecha_pago': pay_date
        }
    return data

# --- INTERFAZ (sin cambios) ---
st.set_page_config(layout="wide", page_title="Dividendos")
st.title("Proyección de Dividendos 📅")
# ... (El resto del código de la interfaz no cambia) ...
operaciones_df = ver_operaciones(USER_ID)
posiciones_actuales_df = calcular_cantidad_actual(operaciones_df)
if not posiciones_actuales_df.empty:
    tickers_list = posiciones_actuales_df['ticker'].unique().tolist()
    info_dividendos = obtener_info_dividendos(tickers_list)
    dividendos_df = pd.DataFrame.from_dict(info_dividendos, orient='index')
    resultado_df = posiciones_actuales_df.set_index('ticker').join(dividendos_df).reset_index()
    resultado_df_filtrado = resultado_df[resultado_df['dividendo_anual_accion'] > 0].copy()
    if not resultado_df_filtrado.empty:
        resultado_df_filtrado['ingreso_anual_estimado'] = resultado_df_filtrado['cantidad_total'] * resultado_df_filtrado['dividendo_anual_accion']
        df_display = resultado_df_filtrado[['ticker', 'cantidad_total', 'dividendo_anual_accion', 'frecuencia_estimada','ingreso_anual_estimado', 'prox_fecha_ex_div', 'prox_fecha_pago']].rename(columns={'ticker': 'Ticker', 'cantidad_total': 'Acciones Actuales', 'dividendo_anual_accion': 'Dividendo Anual / Acción','frecuencia_estimada': 'Frecuencia Estimada','ingreso_anual_estimado': 'Ingreso Anual Estimado', 'prox_fecha_ex_div': 'Próx. Fecha Ex-Div', 'prox_fecha_pago': 'Próx. Fecha Pago'})
        st.dataframe(df_display.style.format({'Dividendo Anual / Acción': '${:,.2f}','Ingreso Anual Estimado': '${:,.2f}'}), use_container_width=True)
        ingreso_total_anual = df_display['Ingreso Anual Estimado'].sum()
        st.metric("Ingreso Anual Total Estimado por Dividendos", f"${ingreso_total_anual:,.2f}")
    else:
        st.info("Ninguno de los activos en tu portafolio actual parece pagar dividendos según los datos disponibles.")
else:
    st.info("Aún no tienes posiciones abiertas para calcular la proyección de dividendos.")