import streamlit as st
import sqlite3
import pandas as pd
import yfinance as yf

# --- VERIFICADOR DE SESIÓN ---
if 'user' not in st.session_state or st.session_state.user is None:
    st.error("Debes iniciar sesión para acceder a esta página.")
    st.stop()

USER_ID = st.session_state.user[0]

# --- FUNCIONES (ACTUALIZADAS) ---
def conectar_db():
    return sqlite3.connect('portfolio.db')

def ver_watchlist(user_id):
    conexion = conectar_db()
    df = pd.read_sql_query("SELECT * FROM watchlist WHERE user_id = ?", conexion, params=(user_id,))
    conexion.close()
    return df

# *** CAMBIO: Función ahora verifica si el ticker ya existe para el usuario ANTES de insertarlo ***
def anadir_a_watchlist(ticker, precio_objetivo, notas, user_id):
    conexion = conectar_db()
    cursor = conexion.cursor()
    
    # Paso 1: Verificar si el ticker ya existe para este usuario
    cursor.execute("SELECT * FROM watchlist WHERE ticker = ? AND user_id = ?", (ticker, user_id))
    existe = cursor.fetchone()
    
    if existe:
        st.warning(f"El ticker {ticker} ya está en tu watchlist.")
        conexion.close()
        return False # Indica que la operación falló
    else:
        # Paso 2: Si no existe, lo insertamos
        cursor.execute("INSERT INTO watchlist (ticker, precio_objetivo, notas, user_id) VALUES (?, ?, ?, ?)", (ticker, precio_objetivo, notas, user_id))
        conexion.commit()
        conexion.close()
        return True # Indica que la operación fue exitosa

def eliminar_de_watchlist(ticker_id, user_id):
    conexion = conectar_db()
    cursor = conexion.cursor()
    cursor.execute("DELETE FROM watchlist WHERE id = ? AND user_id = ?", (ticker_id, user_id))
    conexion.commit()
    conexion.close()

@st.cache_data(ttl=600)
def obtener_info_watchlist(tickers):
    # ... (esta función no cambia) ...
    info_dict = {}
    for ticker_str in tickers:
        try:
            ticker_obj = yf.Ticker(ticker_str)
            info = ticker_obj.info
            hist = ticker_obj.history(period="1mo")
            if len(hist) > 7:
                precio_hace_7d = hist['Close'][-8]
                precio_actual = hist['Close'][-1]
                rendimiento_7d = ((precio_actual - precio_hace_7d) / precio_hace_7d) * 100
            else:
                rendimiento_7d = None
            info_dict[ticker_str] = {'precio_actual': info.get('currentPrice', info.get('regularMarketPrice', 0)), 'ratio_pe': info.get('trailingPE', None), 'rendimiento_7d': rendimiento_7d, 'min_52_semanas': info.get('fiftyTwoWeekLow', None), 'max_52_semanas': info.get('fiftyTwoWeekHigh', None)}
        except Exception:
            info_dict[ticker_str] = {'precio_actual': 0, 'ratio_pe': None, 'rendimiento_7d': None, 'min_52_semanas': None, 'max_52_semanas': None}
    return info_dict

# --- INTERFAZ DE LA PÁGINA ---
st.set_page_config(layout="wide", page_title="Watchlist")
st.title("Watchlist de Activos 🎯")

with st.form("watchlist_form", clear_on_submit=True):
    st.subheader("Añadir Activo a la Watchlist")
    wl_col1, wl_col2, wl_col3 = st.columns(3)
    with wl_col1:
        wl_ticker = st.text_input("Ticker")
    with wl_col2:
        wl_precio_objetivo = st.number_input("Precio Objetivo", min_value=0.0, step=0.01, format="%.2f")
    with wl_col3:
        wl_notas = st.text_input("Notas")
    
    wl_submitted = st.form_submit_button("Añadir a Watchlist")
    if wl_submitted:
        if wl_ticker:
            # *** CAMBIO: Verificamos si la operación fue exitosa antes de mostrar el mensaje y recargar ***
            fue_exitoso = anadir_a_watchlist(wl_ticker.upper(), wl_precio_objetivo, wl_notas, USER_ID)
            if fue_exitoso:
                st.success(f"{wl_ticker.upper()} añadido a la watchlist.")
                st.rerun()
        else:
            st.warning("El ticker es obligatorio.")

# ... (El resto del código para mostrar la tabla no cambia) ...
watchlist_df = ver_watchlist(USER_ID)
if not watchlist_df.empty:
    tickers_watchlist = watchlist_df['ticker'].tolist()
    info_completa = obtener_info_watchlist(tickers_watchlist)
    watchlist_df['precio_actual'] = watchlist_df['ticker'].apply(lambda t: info_completa.get(t, {}).get('precio_actual', 0))
    watchlist_df['ratio_pe'] = watchlist_df['ticker'].apply(lambda t: info_completa.get(t, {}).get('ratio_pe', None))
    watchlist_df['rendimiento_7d'] = watchlist_df['ticker'].apply(lambda t: info_completa.get(t, {}).get('rendimiento_7d', None))
    watchlist_df['min_52_semanas'] = watchlist_df['ticker'].apply(lambda t: info_completa.get(t, {}).get('min_52_semanas', None))
    watchlist_df['max_52_semanas'] = watchlist_df['ticker'].apply(lambda t: info_completa.get(t, {}).get('max_52_semanas', None))
    st.subheader("Activos en Seguimiento")
    col1, col2, col3, col4, col5 = st.columns([1.5, 2, 1.5, 1.5, 1])
    col1.markdown("**Ticker**")
    col2.markdown("**Precio Actual vs. Rango 52 Semanas**")
    col3.markdown("**Ratio P/E (x)**")
    col4.markdown("**Rendimiento (7d)**")
    col5.markdown("**Acción**")
    st.divider()
    for index, row in watchlist_df.iterrows():
        col1, col2, col3, col4, col5 = st.columns([1.5, 2, 1.5, 1.5, 1])
        col1.write(row['ticker'])
        precio = row['precio_actual']
        min_52 = row['min_52_semanas']
        max_52 = row['max_52_semanas']
        col2.write(f"${precio:,.2f}")
        if min_52 is not None and max_52 is not None and max_52 > min_52:
            progreso = int(((precio - min_52) / (max_52 - min_52)) * 100)
            col2.progress(progreso)
        col3.write(f"{row['ratio_pe']:.2f}x" if row['ratio_pe'] is not None else "N/A")
        rendimiento = row['rendimiento_7d']
        if rendimiento is not None:
            color = "green" if rendimiento > 0 else "red"
            col4.markdown(f"<span style='color:{color};'>{rendimiento:.2f}%</span>", unsafe_allow_html=True)
        else:
            col4.write("N/A")
        if col5.button("Eliminar", key=f"del_{row['id']}"):
            eliminar_de_watchlist(row['id'], USER_ID)
            st.rerun()
else:
    st.info("Tu watchlist está vacía.")