import streamlit as st
import psycopg2
from datetime import date
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
import requests
from utils import apply_styles, metric_card, section_header, apply_plotly_style, badge, PIE_COLORS, portfolio_selector_sidebar, ver_portafolios, crear_portafolio, eliminar_portafolio, renombrar_portafolio, get_efectivo, set_efectivo

# ── Auth ──────────────────────────────────────────────────────────
if 'user' not in st.session_state or st.session_state.user is None:
    st.error("Debes iniciar sesión.")
    st.stop()

USER_ID = st.session_state.user[0]

st.set_page_config(layout="wide", page_title="Dashboard · Portfolio")
apply_styles()

# ── DB ────────────────────────────────────────────────────────────
def conectar_db():
    return psycopg2.connect(
        host=st.secrets["connections"]["supabase"]["host"],
        database=st.secrets["connections"]["supabase"]["database"],
        user=st.secrets["connections"]["supabase"]["username"],
        password=st.secrets["connections"]["supabase"]["password"],
        port=st.secrets["connections"]["supabase"]["port"]
    )

# ── DATA FUNCTIONS ────────────────────────────────────────────────
def anadir_operacion(fecha, ticker, tipo, cantidad, precio, moneda, user_id, portfolio_id=None):
    conn = conectar_db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO operaciones (fecha, ticker, tipo, cantidad, precio, moneda, user_id, portfolio_id) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
        (fecha, ticker, tipo, cantidad, precio, moneda, user_id, portfolio_id)
    )
    conn.commit(); conn.close()

def eliminar_operacion(op_id, user_id):
    conn = conectar_db()
    c = conn.cursor()
    c.execute("DELETE FROM operaciones WHERE id=%s AND user_id=%s", (op_id, user_id))
    conn.commit(); conn.close()

def ver_operaciones(user_id, portfolio_id=None):
    conn = conectar_db()
    if portfolio_id is None:
        df = pd.read_sql_query(
            "SELECT * FROM operaciones WHERE user_id=%s ORDER BY fecha ASC",
            conn, params=(user_id,)
        )
    else:
        df = pd.read_sql_query(
            "SELECT * FROM operaciones WHERE user_id=%s AND portfolio_id=%s ORDER BY fecha ASC",
            conn, params=(user_id, portfolio_id)
        )
    conn.close()
    return df

def calcular_capital_neto(df_ops, precio_dolar):
    """Capital neto = costo total compras - ingresos ventas, en USD."""
    if df_ops.empty: return 0.0
    df = df_ops.copy()
    df['moneda'] = df['moneda'].fillna('USD')
    df['monto'] = df['cantidad'] * df['precio']
    df['monto_usd'] = df.apply(
        lambda r: r['monto'] / precio_dolar if r['moneda'] == 'ARS' else r['monto'], axis=1
    )
    compras = df[df['tipo']=='Compra']['monto_usd'].sum()
    ventas  = df[df['tipo']=='Venta']['monto_usd'].sum()
    return compras - ventas

@st.cache_data(ttl=300)
def obtener_dolar_argentina():
    precio, fuente = 1150.0, "Estimado"
    try:
        r = requests.get("https://dolarapi.com/v1/dolares/cripto", timeout=5)
        if r.status_code == 200:
            data = r.json()
            precio, fuente = float(data['venta']), "DolarApi"
    except:
        pass
    st.session_state['precio_dolar_compartido'] = precio
    return precio, fuente

@st.cache_data(ttl=600)
def obtener_datos_mercado(tickers):
    if not tickers: return {}
    precios = {}
    for ticker in tickers:
        try:
            hist = yf.Ticker(ticker).history(period="5d")
            precios[ticker] = hist['Close'].dropna().iloc[-1] if not hist.empty else 0.0
        except:
            precios[ticker] = 0.0
    return precios

# efectivo ahora se maneja con get_efectivo/set_efectivo desde utils

def calcular_posiciones(df_ops, precio_dolar):
    if df_ops.empty: return pd.DataFrame(), 0, pd.DataFrame()
    df = df_ops.copy()
    df['moneda'] = df['moneda'].fillna('USD')
    df['cantidad_neta'] = df.apply(lambda r: r['cantidad'] if r['tipo']=='Compra' else -r['cantidad'], axis=1)
    df['coste_op']   = df['cantidad'] * df['precio']
    df['ingreso_op'] = df['cantidad'] * df['precio']

    pos = df.groupby(['ticker','moneda']).agg(
        cantidad_total          =('cantidad_neta', 'sum'),
        coste_acumulado_compras =('coste_op',   lambda x: x[df.loc[x.index,'tipo']=='Compra'].sum()),
        cantidad_acumulada_compras=('cantidad', lambda x: x[df.loc[x.index,'tipo']=='Compra'].sum()),
        total_ventas            =('ingreso_op', lambda x: x[df.loc[x.index,'tipo']=='Venta'].sum()),
        cantidad_vendida        =('cantidad',   lambda x: x[df.loc[x.index,'tipo']=='Venta'].sum())
    ).reset_index()

    pos['ppp_original'] = pos.apply(
        lambda r: r['coste_acumulado_compras'] / r['cantidad_acumulada_compras']
        if r['cantidad_acumulada_compras'] > 0 else 0, axis=1
    )
    pos['ganancia_realizada'] = pos['total_ventas'] - (pos['ppp_original'] * pos['cantidad_vendida'])
    ganancia_realizada_usd = pos['ganancia_realizada'].sum()
    beneficios_df = pos[['ticker','ganancia_realizada']].copy()

    abiertas = pos[pos['cantidad_total'] > 0.000001].copy()
    if not abiertas.empty:
        precios = obtener_datos_mercado(abiertas['ticker'].unique().tolist())
        abiertas['precio_actual'] = abiertas['ticker'].map(precios).fillna(0)

        def val_usd(row):
            v = row['cantidad_total'] * row['precio_actual']
            return v / precio_dolar if row['moneda'] == 'ARS' and row['precio_actual'] != 0 else v

        def coste_usd(row):
            c = row['cantidad_total'] * row['ppp_original']
            return c / precio_dolar if row['moneda'] == 'ARS' else c

        abiertas['valor_mercado_usd']       = abiertas.apply(val_usd, axis=1)
        abiertas['coste_total_usd']         = abiertas.apply(coste_usd, axis=1)
        abiertas['ganancia_no_realizada_usd'] = abiertas['valor_mercado_usd'] - abiertas['coste_total_usd']
        abiertas['rentabilidad_%']          = abiertas.apply(
            lambda r: (r['ganancia_no_realizada_usd'] / r['coste_total_usd'] * 100)
            if r['coste_total_usd'] > 0 else 0, axis=1
        )
    return abiertas, ganancia_realizada_usd, beneficios_df

@st.cache_data(ttl=600)
def calcular_evolucion_patrimonio(df_ops, precio_dolar):
    if df_ops.empty: return None
    df_ops = df_ops.copy()
    df_ops['fecha'] = pd.to_datetime(df_ops['fecha'])

    # Separar tickers USD y ARS para descargar por separado
    tickers_usd = [t for t in df_ops['ticker'].unique() if not t.endswith('.BA')]
    tickers_ars = [t for t in df_ops['ticker'].unique() if t.endswith('.BA')]
    start_date  = df_ops['fecha'].min()
    rango       = pd.date_range(start=start_date, end=date.today())
    patrimonio  = pd.DataFrame(index=rango)

    def descargar_precios(tickers):
        if not tickers: return pd.DataFrame()
        try:
            raw = yf.download(tickers, start=start_date, progress=False, auto_adjust=True)
            # yf devuelve MultiIndex cuando son varios tickers
            if isinstance(raw.columns, pd.MultiIndex):
                close = raw['Close']
            else:
                close = raw[['Close']].rename(columns={'Close': tickers[0]}) if len(tickers) == 1 else raw
            # Eliminar duplicados de índice
            close = close[~close.index.duplicated(keep='first')]
            return close
        except:
            return pd.DataFrame()

    precios_usd = descargar_precios(tickers_usd)
    precios_ars = descargar_precios(tickers_ars)

    for ticker in df_ops['ticker'].unique():
        ops_t = df_ops[df_ops['ticker'] == ticker].copy()
        ops_t['cantidad_neta'] = ops_t['cantidad'].where(ops_t['tipo'] == 'Compra', -ops_t['cantidad'])
        ops_d    = ops_t.groupby('fecha')['cantidad_neta'].sum()
        tenencias = ops_d.cumsum().reindex(rango, method='ffill').fillna(0)

        # Obtener serie de precios del DataFrame correcto
        es_ars = ticker.endswith('.BA')
        df_precios = precios_ars if es_ars else precios_usd

        if not df_precios.empty and ticker in df_precios.columns:
            precio_s = df_precios[ticker].reindex(rango)
            # Clave del fix: ffill mantiene último precio conocido en fines de semana/feriados
            # Solo llenamos hacia adelante (nunca hacia atrás, para no inventar precios antes de que existiera)
            precio_s = precio_s.ffill()
            # Para días anteriores a la primera cotización, dejamos 0 (tenencias también son 0 ahí)
            precio_s = precio_s.fillna(0)
        else:
            precio_s = pd.Series(0, index=rango)

        valor = tenencias * precio_s
        if es_ars:
            valor = valor / precio_dolar  # conversión ARS → USD al tipo actual (aproximado)

        patrimonio[ticker] = valor

    # Suma solo donde tenemos datos reales (ignora NaN, no los convierte a 0)
    patrimonio['Total USD'] = patrimonio.sum(axis=1)

    # Filtrar días donde el total es 0 al inicio (antes de cualquier compra)
    primera_compra = df_ops['fecha'].min()
    resultado = patrimonio[['Total USD']].reset_index().rename(columns={'index': 'Fecha'})
    resultado = resultado[resultado['Fecha'] >= primera_compra]

    return resultado


# ── LOAD DATA ─────────────────────────────────────────────────────
precio_dolar_hoy, fuente_dolar = obtener_dolar_argentina()

# Portfolio selector runs first (sets session_state)
portfolio_id_sel, portfolio_label_sel = portfolio_selector_sidebar(USER_ID)

operaciones_df     = ver_operaciones(USER_ID, portfolio_id_sel)
posiciones_df, ganancia_realizada_total, _ = calcular_posiciones(operaciones_df, precio_dolar_hoy)
saldo_efectivo_usd, saldo_efectivo_ars = get_efectivo(USER_ID, portfolio_id_sel)

valor_acciones_usd = posiciones_df['valor_mercado_usd'].sum() if 'valor_mercado_usd' in posiciones_df.columns else 0
valor_ars_en_usd   = saldo_efectivo_ars / precio_dolar_hoy
patrimonio_total   = valor_acciones_usd + saldo_efectivo_usd + valor_ars_en_usd
ganancia_no_real   = posiciones_df['ganancia_no_realizada_usd'].sum() if 'ganancia_no_realizada_usd' in posiciones_df.columns else 0
beneficio_total    = ganancia_no_real + ganancia_realizada_total
capital_neto       = calcular_capital_neto(operaciones_df, precio_dolar_hoy)
rentabilidad       = (beneficio_total / capital_neto * 100) if capital_neto > 0 else 0

# ── SIDEBAR ───────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"""
        <div style="padding:8px 0 16px">
            <div style="font-size:0.62rem;text-transform:uppercase;letter-spacing:1.5px;
                        color:#334155;font-family:JetBrains Mono,monospace;margin-bottom:4px">
                Usuario
            </div>
            <div style="font-size:1.05rem;font-weight:600;color:#e2e8f0">
                {st.session_state.user[1]}
            </div>
        </div>
    """, unsafe_allow_html=True)
    st.metric("Dólar Cripto", f"${precio_dolar_hoy:,.0f} ARS")
    st.caption(f"Fuente: {fuente_dolar}")
    st.divider()

    # ── Gestión de portafolios ─────────────────────────────────────
    with st.expander("⚙️  Gestionar portafolios"):
        portfolios_df = ver_portafolios(USER_ID)

        # Crear nuevo
        with st.form("form_crear_portfolio", clear_on_submit=True):
            np_nombre = st.text_input("Nombre", placeholder="Ej: Largo plazo")
            np_desc   = st.text_input("Descripción (opcional)", placeholder="Jubilación, acciones growth…")
            if st.form_submit_button("Crear", use_container_width=True) and np_nombre:
                crear_portafolio(USER_ID, np_nombre, np_desc)
                st.success(f"✓ Portafolio '{np_nombre}' creado.")
                st.rerun()

        # Listar y editar existentes
        if not portfolios_df.empty:
            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            for _, pf in portfolios_df.iterrows():
                with st.expander(f"📁 {pf['nombre']}"):
                    with st.form(f"edit_pf_{pf['id']}", clear_on_submit=False):
                        e_nombre = st.text_input("Nombre", value=pf['nombre'], key=f"en_{pf['id']}")
                        e_desc   = st.text_input("Descripción", value=pf['descripcion'] or "", key=f"ed_{pf['id']}")
                        c_save, c_del = st.columns(2)
                        if c_save.form_submit_button("Guardar"):
                            renombrar_portafolio(pf['id'], e_nombre, e_desc, USER_ID)
                            st.rerun()
                        if c_del.form_submit_button("Eliminar", type="primary"):
                            eliminar_portafolio(pf['id'], USER_ID)
                            st.session_state['portfolio_label'] = "Todos (consolidado)"
                            st.rerun()

    st.divider()

    # ── Mini posiciones ────────────────────────────────────────────
    if not posiciones_df.empty and 'valor_mercado_usd' in posiciones_df.columns:
        st.markdown("""
            <div style="font-size:0.62rem;text-transform:uppercase;letter-spacing:1.5px;
                        color:#334155;font-family:JetBrains Mono,monospace;margin-bottom:8px">
                Posiciones activas
            </div>
        """, unsafe_allow_html=True)
        for _, row in posiciones_df.sort_values('valor_mercado_usd', ascending=False).iterrows():
            rent  = row.get('rentabilidad_%', 0)
            color = "#10b981" if rent >= 0 else "#ef4444"
            sign  = "+" if rent >= 0 else ""
            st.markdown(f"""
                <div style="display:flex;justify-content:space-between;align-items:center;
                            padding:5px 0;border-bottom:1px solid #1a2540">
                    <span style="color:#cbd5e1;font-size:0.82rem;font-family:JetBrains Mono,monospace">
                        {row['ticker']}
                    </span>
                    <span style="color:{color};font-size:0.75rem;font-family:JetBrains Mono,monospace">
                        {sign}{rent:.1f}%
                    </span>
                </div>
            """, unsafe_allow_html=True)

# ── HEADER ────────────────────────────────────────────────────────
col_title, col_date = st.columns([3, 1])
with col_title:
    st.markdown(f"""
        <div style="padding-bottom:4px">
            <h1 style="margin:0">Portfolio Dashboard</h1>
            <div style="color:#475569;font-size:0.85rem;font-family:'JetBrains Mono',monospace;margin-top:4px">
                {st.session_state.user[1]} · actualizado {date.today().strftime('%d %b %Y')}
            </div>
        </div>
    """, unsafe_allow_html=True)
with col_date:
    st.markdown("<div style='padding-top:18px'></div>", unsafe_allow_html=True)
    rent_color = "green" if rentabilidad >= 0 else "red"
    rent_sign  = "+" if rentabilidad >= 0 else ""
    st.markdown(
        f'<div style="text-align:right">{badge(f"{rent_sign}{rentabilidad:.2f}% total", rent_color)}</div>',
        unsafe_allow_html=True
    )

st.divider()

# ── METRICS ROW 1 ─────────────────────────────────────────────────
if not operaciones_df.empty or total_aportado > 0 or saldo_efectivo_usd != 0:
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        metric_card("Patrimonio Total", f"US$ {patrimonio_total:,.2f}", color="default")
    with c2:
        b_color = "green" if beneficio_total >= 0 else "red"
        b_sign  = "+" if beneficio_total >= 0 else ""
        metric_card("Beneficio Total", f"{b_sign}US$ {abs(beneficio_total):,.2f}", color=b_color)
    with c3:
        metric_card("Capital Neto Aportado", f"US$ {capital_neto:,.2f}", color="blue")
    with c4:
        r_color = "green" if rentabilidad >= 0 else "red"
        r_sign  = "+" if rentabilidad >= 0 else ""
        metric_card("Rentabilidad", f"{r_sign}{rentabilidad:.2f}%",
                    subtitle=f"Realizado: US$ {ganancia_realizada_total:,.2f}", color=r_color)

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    # ── METRICS ROW 2 ──────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        metric_card("Valor en Acciones", f"US$ {valor_acciones_usd:,.2f}", color="default")
    with c2:
        with st.container():
            st.markdown('''
                <div style="background:rgba(59,130,246,0.06);border:1px solid #1a2540;
                border-left:3px solid #3b82f6;border-radius:12px;padding:18px 20px;min-height:90px">
                <div style="font-size:0.65rem;text-transform:uppercase;letter-spacing:1.4px;
                color:#475569;font-family:JetBrains Mono,monospace;margin-bottom:6px">Efectivo USD</div>
                ''', unsafe_allow_html=True)
            nuevo_usd = st.number_input("usd_input", value=saldo_efectivo_usd,
                min_value=0.0, step=0.01, format="%.2f",
                label_visibility="collapsed", key="input_usd")
            if nuevo_usd != saldo_efectivo_usd:
                set_efectivo(USER_ID, nuevo_usd, saldo_efectivo_ars, portfolio_id_sel)
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
    with c3:
        with st.container():
            st.markdown('''
                <div style="background:rgba(245,158,11,0.06);border:1px solid #1a2540;
                border-left:3px solid #f59e0b;border-radius:12px;padding:18px 20px;min-height:90px">
                <div style="font-size:0.65rem;text-transform:uppercase;letter-spacing:1.4px;
                color:#475569;font-family:JetBrains Mono,monospace;margin-bottom:6px">Efectivo ARS</div>
                ''', unsafe_allow_html=True)
            nuevo_ars = st.number_input("ars_input", value=saldo_efectivo_ars,
                min_value=0.0, step=1.0, format="%.0f",
                label_visibility="collapsed", key="input_ars")
            if nuevo_ars != saldo_efectivo_ars:
                set_efectivo(USER_ID, saldo_efectivo_usd, nuevo_ars, portfolio_id_sel)
                st.rerun()
            st.markdown(f'<div style="font-size:0.72rem;color:#475569;margin-top:4px;font-family:JetBrains Mono,monospace">≈ US$ {nuevo_ars/precio_dolar_hoy:,.2f}</div></div>', unsafe_allow_html=True)
    with c4:
        nr_color = "green" if ganancia_no_real >= 0 else "red"
        nr_sign  = "+" if ganancia_no_real >= 0 else ""
        metric_card("No Realizado", f"{nr_sign}US$ {abs(ganancia_no_real):,.2f}", color=nr_color)

else:
    st.info("Añadí operaciones o aportes para ver tu dashboard.")

st.divider()

# ── CHARTS ────────────────────────────────────────────────────────
section_header("Análisis Visual", "Distribución y evolución del portafolio")

c1, c2 = st.columns(2)

with c1:
    if not posiciones_df.empty and 'valor_mercado_usd' in posiciones_df.columns:
        fig_pie = px.pie(
            posiciones_df,
            values='valor_mercado_usd',
            names='ticker',
            hole=0.55,
            color_discrete_sequence=PIE_COLORS,
        )
        fig_pie.update_traces(
            textfont=dict(family="JetBrains Mono", size=11, color="#cbd5e1"),
            marker=dict(line=dict(color="#070c18", width=2)),
            hovertemplate="<b>%{label}</b><br>US$ %{value:,.2f}<br>%{percent}<extra></extra>",
        )
        fig_pie.update_layout(
            **{k: v for k, v in dict(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#64748b", family="JetBrains Mono"),
                legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="#94a3b8", size=11)),
                margin=dict(l=16, r=16, t=40, b=16),
                title=dict(text="Diversificación por activo", font=dict(color="#64748b", size=12, family="DM Sans")),
                annotations=[dict(
                    text=f"<b>US$ {valor_acciones_usd:,.0f}</b>",
                    x=0.5, y=0.5, font_size=14,
                    font_color="#f1f5f9", font_family="JetBrains Mono",
                    showarrow=False
                )],
            ).items()},
        )
        st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.markdown("""
            <div style="height:300px;display:flex;align-items:center;justify-content:center;
                        color:#334155;font-size:0.85rem;border:1px dashed #1a2540;border-radius:12px">
                Sin posiciones abiertas
            </div>
        """, unsafe_allow_html=True)

with c2:
    evolucion_df = calcular_evolucion_patrimonio(operaciones_df, precio_dolar_hoy)
    if evolucion_df is not None and not evolucion_df.empty:
        fig_ev = go.Figure()
        fig_ev.add_trace(go.Scatter(
            x=evolucion_df['Fecha'],
            y=evolucion_df['Total USD'],
            fill='tozeroy',
            fillcolor='rgba(16,185,129,0.07)',
            line=dict(color='#10b981', width=2),
            hovertemplate="<b>%{x|%d %b %Y}</b><br>US$ %{y:,.2f}<extra></extra>",
            name='Patrimonio'
        ))
        fig_ev.update_layout(
            title=dict(text="Evolución histórica (USD)", font=dict(color="#64748b", size=12, family="DM Sans")),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="#0a0f1e",
            font=dict(color="#64748b", family="JetBrains Mono"),
            xaxis=dict(gridcolor="#1a2540", zerolinecolor="#1a2540", tickfont=dict(color="#475569", size=10)),
            yaxis=dict(gridcolor="#1a2540", zerolinecolor="#1a2540", tickfont=dict(color="#475569", size=10), tickprefix="$"),
            showlegend=False,
            margin=dict(l=16, r=16, t=40, b=16),
            hovermode="x unified",
        )
        st.plotly_chart(fig_ev, use_container_width=True)
    else:
        st.markdown("""
            <div style="height:300px;display:flex;align-items:center;justify-content:center;
                        color:#334155;font-size:0.85rem;border:1px dashed #1a2540;border-radius:12px">
                Se necesitan más datos históricos
            </div>
        """, unsafe_allow_html=True)

st.divider()

# ── ADD OPERATION FORM ────────────────────────────────────────────
section_header("Nueva Operación", "Registrá una compra o venta")

CRIPTOS = {"BTC","ETH","SOL","USDT","BNB","XRP","ADA","DOGE","SHIB","DOT","DAI","MATIC","AVAX","TRX","LTC","LINK","ATOM","UNI"}

with st.form("operacion_form", clear_on_submit=True):
    c1, c2, c3, c4, c5 = st.columns([1.2, 1, 1, 1.3, 1.3])
    with c1: fecha_op    = st.date_input("Fecha", value=date.today())
    with c2: ticker_op   = st.text_input("Ticker", placeholder="AAPL")
    with c3: tipo_op     = st.selectbox("Tipo", ["Compra", "Venta"])
    with c4: moneda_op   = st.selectbox("Moneda", ["USD", "ARS"])
    with c5: cantidad_op = st.number_input("Cantidad", min_value=0.0, step=0.0001, format="%.4f")

    pf_col, precio_col = st.columns([1, 2])
    with precio_col:
        precio_op = st.number_input("Precio Unitario", min_value=0.0, step=0.0001, format="%.4f")
    with pf_col:
        portfolios_form = ver_portafolios(USER_ID)
        if not portfolios_form.empty:
            pf_opts   = {"Sin asignar": None}
            for _, pf in portfolios_form.iterrows():
                pf_opts[pf['nombre']] = pf['id']
            pf_sel_label = st.selectbox("Portafolio", list(pf_opts.keys()))
            pf_sel_id    = pf_opts[pf_sel_label]
        else:
            st.info("Crea un portafolio primero en el menú lateral.")
            pf_sel_id = None

    submitted = st.form_submit_button("Confirmar Operación", use_container_width=True)
    if submitted:
        if not ticker_op or cantidad_op <= 0:
            st.warning("Completá ticker y cantidad.")
        else:
            tk = ticker_op.upper()
            if tk in CRIPTOS: tk = f"{tk}-USD"
            anadir_operacion(fecha_op, tk, tipo_op, cantidad_op, precio_op, moneda_op, USER_ID, pf_sel_id)
            st.success(f"✓ Operación registrada — {tipo_op} {cantidad_op:.4f} {tk} → {pf_sel_label}")
            st.rerun()

st.divider()

# ── OPEN POSITIONS TABLE ──────────────────────────────────────────
section_header("Posiciones Actuales", f"{len(posiciones_df)} activos en cartera")

if not posiciones_df.empty:
    df_show = posiciones_df[[
        'ticker','moneda','cantidad_total','ppp_original',
        'precio_actual','valor_mercado_usd','ganancia_no_realizada_usd','rentabilidad_%'
    ]].rename(columns={
        'ticker':'Ticker','moneda':'Moneda','cantidad_total':'Cantidad',
        'ppp_original':'PPP','precio_actual':'Precio Hoy',
        'valor_mercado_usd':'Valor (USD)','ganancia_no_realizada_usd':'Ganancia (USD)','rentabilidad_%':'Rent %'
    })

    def color_ganancia(val):
        if pd.isna(val) or val == 0: return 'color:#475569; background:transparent'
        if val > 0: return 'color:#10b981; background:rgba(16,185,129,0.06)'
        return 'color:#ef4444; background:rgba(239,68,68,0.06)'

    styled = (
        df_show.style
        .map(color_ganancia, subset=['Ganancia (USD)','Rent %'])
        .format({
            'Cantidad':    '{:,.4f}',
            'PPP':         '${:,.4f}',
            'Precio Hoy':  '${:,.4f}',
            'Valor (USD)': 'US$ {:,.2f}',
            'Ganancia (USD)': 'US$ {:,.2f}',
            'Rent %':      '{:+.2f}%',
        }, na_rep="-")
    )
    st.dataframe(styled, use_container_width=True, hide_index=True)
else:
    st.info("Sin posiciones abiertas.")

st.divider()

# ── OPERATIONS HISTORY ────────────────────────────────────────────
section_header("Historial de Operaciones")

if not operaciones_df.empty:
    if 'moneda' not in operaciones_df.columns:
        operaciones_df['moneda'] = 'USD'
    df_hist = operaciones_df.sort_values('fecha', ascending=False).copy()
    df_hist['fecha'] = pd.to_datetime(df_hist['fecha']).dt.strftime('%Y-%m-%d')

    # Header row
    cols_h = st.columns([0.5, 1, 1.2, 0.8, 0.7, 1, 1, 0.4])
    labels = ["ID","Fecha","Ticker","Tipo","Moneda","Cantidad","Precio",""]
    for col, lbl in zip(cols_h, labels):
        col.markdown(
            f'<span style="font-size:0.65rem;text-transform:uppercase;'
            f'letter-spacing:1px;color:#334155;font-family:JetBrains Mono,monospace">{lbl}</span>',
            unsafe_allow_html=True
        )
    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    for _, row in df_hist.iterrows():
        cols = st.columns([0.5, 1, 1.2, 0.8, 0.7, 1, 1, 0.4])
        tipo_color = "#10b981" if row['tipo'] == 'Compra' else "#ef4444"
        cols[0].markdown(f'<span style="color:#334155;font-family:JetBrains Mono,monospace;font-size:0.8rem">{row["id"]}</span>', unsafe_allow_html=True)
        cols[1].markdown(f'<span style="color:#64748b;font-family:JetBrains Mono,monospace;font-size:0.8rem">{row["fecha"]}</span>', unsafe_allow_html=True)
        cols[2].markdown(f'<span style="color:#e2e8f0;font-family:JetBrains Mono,monospace;font-size:0.85rem;font-weight:500">{row["ticker"]}</span>', unsafe_allow_html=True)
        cols[3].markdown(f'<span style="color:{tipo_color};font-family:JetBrains Mono,monospace;font-size:0.8rem">{row["tipo"]}</span>', unsafe_allow_html=True)
        cols[4].markdown(f'<span style="color:#64748b;font-family:JetBrains Mono,monospace;font-size:0.8rem">{row["moneda"]}</span>', unsafe_allow_html=True)
        cols[5].markdown(f'<span style="color:#cbd5e1;font-family:JetBrains Mono,monospace;font-size:0.8rem">{row["cantidad"]:.4f}</span>', unsafe_allow_html=True)
        cols[6].markdown(f'<span style="color:#cbd5e1;font-family:JetBrains Mono,monospace;font-size:0.8rem">${row["precio"]:,.4f}</span>', unsafe_allow_html=True)
        if cols[7].button("✕", key=f"del_{row['id']}", help="Eliminar operación"):
            eliminar_operacion(row['id'], USER_ID)
            st.rerun()
        st.markdown("<div style='height:2px;background:#0f1729;margin:2px 0'></div>", unsafe_allow_html=True)