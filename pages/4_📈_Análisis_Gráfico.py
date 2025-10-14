import streamlit as st
import sqlite3
import pandas as pd
import yfinance as yf
import plotly.express as px

# --- VERIFICADOR DE SESIÓN ---
if 'user' not in st.session_state or st.session_state.user is None:
    st.error("Debes iniciar sesión para acceder a esta página.")
    st.stop()

USER_ID = st.session_state.user[0]

# --- FUNCIONES (ACTUALIZADAS Y COMPLETAS) ---
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

def calcular_posiciones(df_ops):
    if df_ops.empty:
        return pd.DataFrame(), 0, pd.DataFrame()
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

# --- INTERFAZ DE LA PÁGINA ---
st.set_page_config(layout="wide", page_title="Análisis Gráfico")
st.title("Análisis Gráfico del Portafolio 📉")

# ACTUALIZADO: Pasamos el USER_ID
operaciones_df = ver_operaciones(USER_ID)
posiciones_df, _, beneficios_realizados_df = calcular_posiciones(operaciones_df)

if not operaciones_df.empty:
    col1, col2 = st.columns(2)
    with col1:
        st.header("Beneficios Actuales por Activo")
        if not posiciones_df.empty:
            fig_beneficios = px.bar(posiciones_df, x='ticker', y='ganancia_no_realizada', title='Ganancia / Pérdida No Realizada', labels={'ticker': 'Activo', 'ganancia_no_realizada': 'Monto ($)'}, color='ganancia_no_realizada', color_continuous_scale=px.colors.diverging.RdYlGn, color_continuous_midpoint=0)
            st.plotly_chart(fig_beneficios, use_container_width=True)
        else:
            st.info("No hay posiciones abiertas para mostrar.")
            
    with col2:
        st.header("Beneficios Históricos por Activo")
        if not beneficios_realizados_df.empty:
            fig_realizados = px.bar(
                beneficios_realizados_df,
                x='ticker',
                y='beneficio_realizado',
                title='Ganancia / Pérdida Realizada (Cerrada)',
                labels={'ticker': 'Activo', 'beneficio_realizado': 'Monto ($)'},
                color='beneficio_realizado',
                color_continuous_scale=px.colors.diverging.RdYlGn,
                color_continuous_midpoint=0
            )
            st.plotly_chart(fig_realizados, use_container_width=True)
        else:
            st.info("No hay beneficios realizados para mostrar.")

    st.divider()

    st.header("Coste vs. Valor de Mercado por Activo")
    if not posiciones_df.empty:
        df_melted = posiciones_df.melt(id_vars=['ticker'], value_vars=['coste_total_actual', 'valor_mercado'], var_name='Metrica', value_name='Valor')
        fig_coste_vs_valor = px.bar(df_melted, x='ticker', y='Valor', color='Metrica', barmode='group', title='Comparación de Coste vs. Valor de Mercado', labels={'ticker': 'Activo', 'Valor': 'Valor ($)'})
        st.plotly_chart(fig_coste_vs_valor, use_container_width=True)
    else:
        st.info("No hay posiciones abiertas para mostrar.")

else:
    st.info("No hay datos suficientes para generar los gráficos. Por favor, añade operaciones en el Dashboard.")