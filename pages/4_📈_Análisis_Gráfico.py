import streamlit as st
import psycopg2
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from datetime import date
from utils import apply_styles, metric_card, section_header, apply_plotly_style, portfolio_selector_sidebar

if 'user' not in st.session_state or st.session_state.user is None:
    st.error("Debes iniciar sesión."); st.stop()
USER_ID = st.session_state.user[0]

st.set_page_config(layout="wide", page_title="Análisis · Portfolio")
apply_styles()
st.markdown("""<style>
.material-symbols-rounded,[data-testid="stNumberInputStepDown"] span,
[data-testid="stNumberInputStepUp"] span{font-size:0!important}
</style>""", unsafe_allow_html=True)

# ── DB ────────────────────────────────────────────────────────────
def conectar_db():
    return psycopg2.connect(
        host=st.secrets["connections"]["supabase"]["host"],
        database=st.secrets["connections"]["supabase"]["database"],
        user=st.secrets["connections"]["supabase"]["username"],
        password=st.secrets["connections"]["supabase"]["password"],
        port=st.secrets["connections"]["supabase"]["port"]
    )

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

@st.cache_data(ttl=600)
def obtener_precios(tickers):
    if not tickers: return {}
    try:
        return yf.Tickers(" ".join(tickers)).history(period='1d')['Close'].iloc[-1].to_dict()
    except: return {}

def calcular(df_ops):
    if df_ops.empty: return pd.DataFrame(), pd.DataFrame()
    df = df_ops.copy()
    if 'moneda' not in df.columns: df['moneda'] = 'USD'
    df['cantidad_neta'] = df.apply(lambda x: x['cantidad'] if x['tipo']=='Compra' else -x['cantidad'], axis=1)
    df['coste']   = df['cantidad'] * df['precio']
    df['ingreso'] = df['cantidad'] * df['precio']

    pos = df.groupby(['ticker','moneda']).agg(
        cant         =('cantidad_neta', 'sum'),
        coste_compras=('coste',   lambda x: x[df.loc[x.index,'tipo']=='Compra'].sum()),
        cant_compras =('cantidad', lambda x: x[df.loc[x.index,'tipo']=='Compra'].sum()),
        total_ventas =('ingreso', lambda x: x[df.loc[x.index,'tipo']=='Venta'].sum()),
        cant_ventas  =('cantidad', lambda x: x[df.loc[x.index,'tipo']=='Venta'].sum()),
    ).reset_index()

    pos['ppp']       = pos.apply(lambda x: x['coste_compras']/x['cant_compras'] if x['cant_compras']>0 else 0, axis=1)
    pos['realizado'] = pos['total_ventas'] - (pos['ppp'] * pos['cant_ventas'])

    abiertas = pos[pos['cant'] > 0.000001].copy()
    if not abiertas.empty:
        precios = obtener_precios(abiertas['ticker'].unique().tolist())
        abiertas['precio']        = abiertas['ticker'].map(precios).fillna(0)
        abiertas['valor_usd']     = abiertas.apply(
            lambda x: (x['cant']*x['precio'])/1150 if x['moneda']=='ARS' else x['cant']*x['precio'], axis=1
        )
        abiertas['coste_usd']     = abiertas.apply(
            lambda x: (x['cant']*x['ppp'])/1150 if x['moneda']=='ARS' else x['cant']*x['ppp'], axis=1
        )
        abiertas['ganancia_no_real'] = abiertas['valor_usd'] - abiertas['coste_usd']
    return abiertas, pos[['ticker','realizado']]

@st.cache_data(ttl=3600)
def calcular_evolucion_portfolio(df_ops, precio_dolar):
    """Calcula el valor total del portfolio día a día en USD."""
    if df_ops.empty: return None
    df_ops = df_ops.copy()
    df_ops['fecha'] = pd.to_datetime(df_ops['fecha'])
    tickers_usd = [t for t in df_ops['ticker'].unique() if not t.endswith('.BA')]
    tickers_ars = [t for t in df_ops['ticker'].unique() if t.endswith('.BA')]
    start_date  = df_ops['fecha'].min()
    rango       = pd.date_range(start=start_date, end=date.today())
    patrimonio  = pd.DataFrame(index=rango)

    def descargar(tickers):
        if not tickers: return pd.DataFrame()
        try:
            raw = yf.download(tickers, start=start_date, progress=False, auto_adjust=True)
            if isinstance(raw.columns, pd.MultiIndex):
                close = raw['Close']
            else:
                close = raw[['Close']].rename(columns={'Close': tickers[0]})
            return close[~close.index.duplicated(keep='first')]
        except: return pd.DataFrame()

    px_usd = descargar(tickers_usd)
    px_ars = descargar(tickers_ars)

    for ticker in df_ops['ticker'].unique():
        ops_t = df_ops[df_ops['ticker']==ticker].copy()
        ops_t['cantidad_neta'] = ops_t['cantidad'].where(ops_t['tipo']=='Compra', -ops_t['cantidad'])
        tenencias = ops_t.groupby('fecha')['cantidad_neta'].sum().cumsum().reindex(rango, method='ffill').fillna(0)
        es_ars = ticker.endswith('.BA')
        df_px  = px_ars if es_ars else px_usd
        if not df_px.empty and ticker in df_px.columns:
            precio_s = df_px[ticker].reindex(rango).ffill().fillna(0)
        else:
            precio_s = pd.Series(0, index=rango)
        valor = tenencias * precio_s
        if es_ars: valor = valor / precio_dolar
        patrimonio[ticker] = valor

    patrimonio['Total'] = patrimonio.sum(axis=1)
    result = patrimonio[['Total']].reset_index().rename(columns={'index':'Fecha'})
    return result[result['Fecha'] >= df_ops['fecha'].min()]

@st.cache_data(ttl=3600)
def calcular_benchmarks(start_date):
    """Descarga benchmarks y los normaliza a base 100."""
    benchmarks = {
        'S&P 500':  '^GSPC',
        'Nasdaq':   'QQQ',
        'Merval':   '^MERV',
        'Oro':      'GC=F',
    }
    result = {}
    for nombre, ticker in benchmarks.items():
        try:
            df = yf.download(ticker, start=start_date, progress=False, auto_adjust=True)
            if df.empty: continue
            close = df['Close'].dropna()
            close.index = pd.to_datetime(close.index)
            if hasattr(close.columns, '__iter__') and not isinstance(close, pd.Series):
                close = close.iloc[:, 0]
            # Normalizar a 100 en la fecha inicial
            base = close.iloc[0]
            if base and base > 0:
                result[nombre] = (close / base * 100).rename(nombre)
        except: pass
    return result

# ── PORTFOLIO SELECTOR ────────────────────────────────────────────
portfolio_id_sel, portfolio_label_sel = portfolio_selector_sidebar(USER_ID)

# ── HEADER ────────────────────────────────────────────────────────
st.markdown("<h1>Análisis Gráfico</h1>", unsafe_allow_html=True)
st.markdown(
    f'<div style="color:#475569;font-size:0.85rem;font-family:JetBrains Mono,monospace;'
    f'margin-top:-8px;margin-bottom:24px">Rendimiento por activo · {portfolio_label_sel}</div>',
    unsafe_allow_html=True
)

ops = ver_operaciones(USER_ID, portfolio_id_sel)
abiertas, realizadas = calcular(ops)

if not ops.empty:
    # ── SUMMARY METRICS ───────────────────────────────────────────
    total_no_real = abiertas['ganancia_no_real'].sum() if not abiertas.empty and 'ganancia_no_real' in abiertas.columns else 0
    total_real    = realizadas['realizado'].sum() if not realizadas.empty else 0
    total_valor   = abiertas['valor_usd'].sum() if not abiertas.empty and 'valor_usd' in abiertas.columns else 0

    c1, c2, c3 = st.columns(3)
    with c1: metric_card("Valor de mercado",   f"US$ {total_valor:,.2f}", color="default")
    with c2:
        nr_color = "green" if total_no_real >= 0 else "red"
        nr_sign  = "+" if total_no_real >= 0 else ""
        metric_card("No realizado total", f"{nr_sign}US$ {abs(total_no_real):,.2f}", color=nr_color)
    with c3:
        r_color = "green" if total_real >= 0 else "red"
        r_sign  = "+" if total_real >= 0 else ""
        metric_card("Realizado total", f"{r_sign}US$ {abs(total_real):,.2f}", color=r_color)

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    # ── CHARTS ROW 1: ganancia por activo ─────────────────────────
    c1, c2 = st.columns(2)

    with c1:
        section_header("Ganancia no realizada", "Posiciones abiertas")
        if not abiertas.empty and 'ganancia_no_real' in abiertas.columns:
            ab_sorted = abiertas.sort_values('ganancia_no_real', ascending=True)
            fig = go.Figure(go.Bar(
                x=ab_sorted['ganancia_no_real'], y=ab_sorted['ticker'],
                orientation='h',
                marker=dict(
                    color=ab_sorted['ganancia_no_real'].apply(lambda v: '#10b981' if v >= 0 else '#ef4444'),
                    line=dict(width=0),
                ),
                hovertemplate="<b>%{y}</b><br>US$ %{x:,.2f}<extra></extra>",
            ))
            fig = apply_plotly_style(fig)
            fig.update_layout(height=max(300, len(abiertas)*38), xaxis_tickprefix="$",
                              yaxis=dict(gridcolor="rgba(0,0,0,0)"))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sin posiciones abiertas.")

    with c2:
        section_header("Ganancia realizada", "Operaciones cerradas")
        real = realizadas[realizadas['realizado'] != 0]
        if not real.empty:
            real_sorted = real.sort_values('realizado', ascending=True)
            fig2 = go.Figure(go.Bar(
                x=real_sorted['realizado'], y=real_sorted['ticker'],
                orientation='h',
                marker=dict(
                    color=real_sorted['realizado'].apply(lambda v: '#10b981' if v >= 0 else '#ef4444'),
                    line=dict(width=0),
                ),
                hovertemplate="<b>%{y}</b><br>US$ %{x:,.2f}<extra></extra>",
            ))
            fig2 = apply_plotly_style(fig2)
            fig2.update_layout(height=max(300, len(real)*38), xaxis_tickprefix="$",
                               yaxis=dict(gridcolor="rgba(0,0,0,0)"))
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("Sin operaciones cerradas.")

    st.divider()

    # ── CHART: Coste vs Valor ─────────────────────────────────────
    section_header("Coste vs Valor de mercado", "Por activo en cartera")
    if not abiertas.empty and 'valor_usd' in abiertas.columns:
        melt = abiertas[['ticker','coste_usd','valor_usd']].melt(
            id_vars='ticker', value_vars=['coste_usd','valor_usd'],
            var_name='Métrica', value_name='Valor'
        )
        melt['Métrica'] = melt['Métrica'].map({'coste_usd':'Coste', 'valor_usd':'Valor actual'})
        fig3 = px.bar(melt, x='ticker', y='Valor', color='Métrica', barmode='group',
                      color_discrete_map={'Coste':'#334155','Valor actual':'#3b82f6'},
                      labels={'ticker':'','Valor':'USD'})
        fig3.update_traces(marker_line_width=0)
        fig3 = apply_plotly_style(fig3)
        fig3.update_layout(yaxis_tickprefix="$")
        st.plotly_chart(fig3, use_container_width=True)

    st.divider()

    # ── BENCHMARK COMPARISON ──────────────────────────────────────
    section_header("Portfolio vs Benchmarks", "Rendimiento en % desde el período seleccionado")

    ops['fecha'] = pd.to_datetime(ops['fecha'])
    start_date   = ops['fecha'].min()

    # Precio dólar aproximado para conversión ARS
    try:
        import requests
        r = requests.get("https://dolarapi.com/v1/dolares/cripto", timeout=5)
        precio_dolar = float(r.json()['venta']) if r.status_code == 200 else 1150.0
    except:
        precio_dolar = 1150.0

    # ── Período y opciones ────────────────────────────────────────
    ctrl_col1, ctrl_col2 = st.columns([3, 2])

    with ctrl_col1:
        periodos = {"1S": 7, "1M": 30, "3M": 90, "6M": 180, "1A": 365, "Total": None}
        periodo_sel = st.radio(
            "Período", list(periodos.keys()),
            index=5, horizontal=True, label_visibility="collapsed"
        )
        dias = periodos[periodo_sel]
        if dias is None:
            bench_start = start_date
        else:
            bench_start = pd.Timestamp(date.today()) - pd.Timedelta(days=dias)
            bench_start = max(bench_start, start_date)

    with ctrl_col2:
        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
        bc1, bc2, bc3, bc4 = st.columns(4)
        mostrar_sp   = bc1.checkbox("S&P 500", value=True)
        mostrar_ndq  = bc2.checkbox("Nasdaq",  value=True)
        mostrar_merv = bc3.checkbox("Merval",  value=False)
        mostrar_oro  = bc4.checkbox("Oro",     value=True)

    with st.spinner("Calculando..."):
        evolucion  = calcular_evolucion_portfolio(ops, precio_dolar)
        benchmarks = calcular_benchmarks(bench_start)

    if evolucion is not None and not evolucion.empty:
        fig_bench = go.Figure()

        # Portfolio — filtrar al período, normalizar a 0%
        port_vals = evolucion.set_index('Fecha')['Total']
        port_vals = port_vals[port_vals.index >= pd.Timestamp(bench_start)]
        port_vals = port_vals.dropna()

        if len(port_vals) > 0:
            base_port = port_vals.iloc[0]
            if base_port and base_port > 0:
                port_pct = (port_vals / base_port - 1) * 100
                fig_bench.add_trace(go.Scatter(
                    x=port_pct.index,
                    y=port_pct.values,
                    name='Mi Portfolio',
                    line=dict(color='#10b981', width=2.5),
                    fill='tozeroy',
                    fillcolor='rgba(16,185,129,0.05)',
                    hovertemplate="<b>Mi Portfolio</b><br>%{x|%d %b %Y}<br>%{y:+.2f}%<extra></extra>",
                ))

        # Benchmarks — también normalizados a 0% desde bench_start
        bench_config = {
            'S&P 500': ('#3b82f6', mostrar_sp),
            'Nasdaq':  ('#8b5cf6', mostrar_ndq),
            'Merval':  ('#f59e0b', mostrar_merv),
            'Oro':     ('#fbbf24', mostrar_oro),
        }

        for nombre, (color, mostrar) in bench_config.items():
            if not mostrar or nombre not in benchmarks: continue
            serie = benchmarks[nombre]
            serie = serie[serie.index >= pd.Timestamp(bench_start)]
            serie = serie.reindex(
                pd.date_range(start=bench_start, end=date.today()), method='ffill'
            ).dropna()
            if len(serie) == 0: continue
            # Renormalizar al período seleccionado (base 0%)
            base_b = serie.iloc[0]
            if base_b and base_b > 0:
                serie_pct = (serie / base_b - 1) * 100
            else:
                continue
            fig_bench.add_trace(go.Scatter(
                x=serie_pct.index,
                y=serie_pct.values,
                name=nombre,
                line=dict(color=color, width=1.5, dash='dot'),
                hovertemplate=f"<b>{nombre}</b><br>%{{x|%d %b %Y}}<br>%{{y:+.2f}}%<extra></extra>",
            ))

        fig_bench.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="#0a0f1e",
            font=dict(color="#64748b", family="JetBrains Mono"),
            xaxis=dict(gridcolor="#1a2540", zerolinecolor="#1a2540",
                       tickfont=dict(color="#475569", size=10)),
            yaxis=dict(gridcolor="#1a2540", zerolinecolor="#1a2540",
                       tickfont=dict(color="#475569", size=10),
                       ticksuffix="%", title="Rendimiento %"),
            legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="#94a3b8", size=12)),
            margin=dict(l=16, r=16, t=20, b=16),
            hovermode="x unified",
            height=420,
            shapes=[dict(
                type='line', x0=bench_start, x1=date.today(),
                y0=0, y1=0,
                line=dict(color='#1e2e4a', width=1, dash='dash')
            )]
        )
        st.plotly_chart(fig_bench, use_container_width=True)

        # ── Resumen tarjetas ──────────────────────────────────────
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        resumen_cols = st.columns(5)
        labels_res  = ['Mi Portfolio', 'S&P 500', 'Nasdaq', 'Merval', 'Oro']
        colores_res = ['#10b981',      '#3b82f6', '#8b5cf6', '#f59e0b', '#fbbf24']

        for col, label, color in zip(resumen_cols, labels_res, colores_res):
            if label == 'Mi Portfolio':
                rend = port_pct.dropna().iloc[-1] if len(port_vals) > 0 and base_port and base_port > 0 else 0
            else:
                if label not in benchmarks:
                    col.markdown(
                        f'<div style="text-align:center;padding:12px;background:#0b1220;'
                        f'border:1px solid #1a2540;border-radius:10px">'
                        f'<div style="color:{color};font-size:0.7rem;font-family:JetBrains Mono,monospace">{label}</div>'
                        f'<div style="color:#334155;font-size:0.85rem">N/D</div></div>',
                        unsafe_allow_html=True
                    )
                    continue
                s = benchmarks[label]
                s = s[s.index >= pd.Timestamp(bench_start)].dropna()
                if len(s) == 0:
                    rend = 0
                else:
                    b = s.iloc[0]
                    rend = (s.iloc[-1] / b - 1) * 100 if b and b > 0 else 0

            sign    = "+" if rend >= 0 else ""
            r_color = "#10b981" if rend >= 0 else "#ef4444"
            border  = f"border-left:3px solid {color}" if label == 'Mi Portfolio' else "border:1px solid #1a2540"
            col.markdown(
                f'<div style="text-align:center;padding:12px;background:#0b1220;'
                f'{border};border-radius:10px">'
                f'<div style="color:{color};font-size:0.7rem;font-family:JetBrains Mono,monospace;'
                f'margin-bottom:4px">{label}</div>'
                f'<div style="color:{r_color};font-size:1.1rem;font-weight:500;'
                f'font-family:JetBrains Mono,monospace">{sign}{rend:.1f}%</div>'
                f'</div>',
                unsafe_allow_html=True
            )
    else:
        st.info("Se necesitan más datos históricos para calcular la comparación.")

else:
    st.markdown("""
        <div style="height:300px;display:flex;align-items:center;justify-content:center;
                    color:#334155;font-size:0.9rem;border:1px dashed #1a2540;border-radius:12px">
            Sin datos de operaciones
        </div>
    """, unsafe_allow_html=True)