import streamlit as st
import psycopg2
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from utils import apply_styles, metric_card, section_header, apply_plotly_style, portfolio_selector_sidebar

if 'user' not in st.session_state or st.session_state.user is None:
    st.error("Debes iniciar sesión."); st.stop()
USER_ID = st.session_state.user[0]

st.set_page_config(layout="wide", page_title="Análisis · Portfolio")
apply_styles()

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
        abiertas['precio'] = abiertas['ticker'].map(precios).fillna(0)
        abiertas['valor_usd']  = abiertas.apply(
            lambda x: (x['cant']*x['precio'])/1150 if x['moneda']=='ARS' else x['cant']*x['precio'], axis=1
        )
        abiertas['coste_usd']  = abiertas.apply(
            lambda x: (x['cant']*x['ppp'])/1150 if x['moneda']=='ARS' else x['cant']*x['ppp'], axis=1
        )
        abiertas['ganancia_no_real'] = abiertas['valor_usd'] - abiertas['coste_usd']

    return abiertas, pos[['ticker','realizado']]

# ── PORTFOLIO SELECTOR ───────────────────────────────────────────
portfolio_id_sel, portfolio_label_sel = portfolio_selector_sidebar(USER_ID)

# ── HEADER ────────────────────────────────────────────────────────
st.markdown("<h1>Análisis Gráfico</h1>", unsafe_allow_html=True)
st.markdown(
    '<div style="color:#475569;font-size:0.85rem;font-family:JetBrains Mono,monospace;'
    'margin-top:-8px;margin-bottom:24px">Rendimiento por activo</div>',
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
    with c1:
        metric_card("Valor de mercado", f"US$ {total_valor:,.2f}", color="default")
    with c2:
        nr_color = "green" if total_no_real >= 0 else "red"
        nr_sign  = "+" if total_no_real >= 0 else ""
        metric_card("No realizado total", f"{nr_sign}US$ {abs(total_no_real):,.2f}", color=nr_color)
    with c3:
        r_color = "green" if total_real >= 0 else "red"
        r_sign  = "+" if total_real >= 0 else ""
        metric_card("Realizado total", f"{r_sign}US$ {abs(total_real):,.2f}", color=r_color)

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    # ── CHARTS ROW 1 ──────────────────────────────────────────────
    c1, c2 = st.columns(2)

    with c1:
        section_header("Ganancia no realizada", "Posiciones abiertas")
        if not abiertas.empty and 'ganancia_no_real' in abiertas.columns:
            ab_sorted = abiertas.sort_values('ganancia_no_real', ascending=True)
            fig = go.Figure(go.Bar(
                x=ab_sorted['ganancia_no_real'],
                y=ab_sorted['ticker'],
                orientation='h',
                marker=dict(
                    color=ab_sorted['ganancia_no_real'].apply(
                        lambda v: '#10b981' if v >= 0 else '#ef4444'
                    ),
                    line=dict(width=0),
                ),
                hovertemplate="<b>%{y}</b><br>US$ %{x:,.2f}<extra></extra>",
            ))
            fig = apply_plotly_style(fig)
            fig.update_layout(
                height=max(300, len(abiertas) * 38),
                xaxis_tickprefix="$",
                yaxis=dict(gridcolor="rgba(0,0,0,0)"),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sin posiciones abiertas.")

    with c2:
        section_header("Ganancia realizada", "Operaciones cerradas")
        real = realizadas[realizadas['realizado'] != 0]
        if not real.empty:
            real_sorted = real.sort_values('realizado', ascending=True)
            fig2 = go.Figure(go.Bar(
                x=real_sorted['realizado'],
                y=real_sorted['ticker'],
                orientation='h',
                marker=dict(
                    color=real_sorted['realizado'].apply(
                        lambda v: '#10b981' if v >= 0 else '#ef4444'
                    ),
                    line=dict(width=0),
                ),
                hovertemplate="<b>%{y}</b><br>US$ %{x:,.2f}<extra></extra>",
            ))
            fig2 = apply_plotly_style(fig2)
            fig2.update_layout(
                height=max(300, len(real) * 38),
                xaxis_tickprefix="$",
                yaxis=dict(gridcolor="rgba(0,0,0,0)"),
            )
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("Sin operaciones cerradas.")

    st.divider()

    # ── CHART ROW 2: Coste vs Valor ───────────────────────────────
    section_header("Coste vs Valor de mercado", "Por activo en cartera")
    if not abiertas.empty and 'valor_usd' in abiertas.columns:
        ab2 = abiertas[['ticker','coste_usd','valor_usd']].copy()
        melt = ab2.melt(id_vars='ticker', value_vars=['coste_usd','valor_usd'],
                        var_name='Métrica', value_name='Valor')
        melt['Métrica'] = melt['Métrica'].map({'coste_usd': 'Coste', 'valor_usd': 'Valor actual'})

        fig3 = px.bar(
            melt, x='ticker', y='Valor', color='Métrica', barmode='group',
            color_discrete_map={'Coste': '#334155', 'Valor actual': '#3b82f6'},
            labels={'ticker': '', 'Valor': 'USD'},
        )
        fig3.update_traces(marker_line_width=0)
        fig3 = apply_plotly_style(fig3)
        fig3.update_layout(yaxis_tickprefix="$")
        st.plotly_chart(fig3, use_container_width=True)

else:
    st.markdown("""
        <div style="height:300px;display:flex;align-items:center;justify-content:center;
                    color:#334155;font-size:0.9rem;border:1px dashed #1a2540;border-radius:12px">
            Sin datos de operaciones
        </div>
    """, unsafe_allow_html=True)