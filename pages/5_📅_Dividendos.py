import streamlit as st
import psycopg2
import pandas as pd
import yfinance as yf
from utils import apply_styles, metric_card, section_header

if 'user' not in st.session_state or st.session_state.user is None:
    st.error("Debes iniciar sesión."); st.stop()
USER_ID = st.session_state.user[0]

st.set_page_config(layout="wide", page_title="Dividendos · Portfolio")
apply_styles()

def conectar_db():
    return psycopg2.connect(
        host=st.secrets["connections"]["supabase"]["host"],
        database=st.secrets["connections"]["supabase"]["database"],
        user=st.secrets["connections"]["supabase"]["username"],
        password=st.secrets["connections"]["supabase"]["password"],
        port=st.secrets["connections"]["supabase"]["port"]
    )

def ver_operaciones(user_id):
    conn = conectar_db()
    df = pd.read_sql_query(
        "SELECT * FROM operaciones WHERE user_id=%s ORDER BY fecha ASC",
        conn, params=(user_id,)
    )
    conn.close()
    return df

@st.cache_data(ttl=3600)
def info_divs(tickers):
    d = {}
    for t in tickers:
        try:
            obj  = yf.Ticker(t)
            info = obj.info
            rate = info.get('dividendRate') or 0
            cal  = obj.calendar
            ex   = pd.to_datetime(cal.get('Ex-Dividend Date')).strftime('%Y-%m-%d') if cal and cal.get('Ex-Dividend Date') else "N/A"
            pay  = pd.to_datetime(cal.get('Dividend Date')).strftime('%Y-%m-%d')    if cal and cal.get('Dividend Date')    else "N/A"
            yield_pct = (info.get('dividendYield') or 0) * 100
            d[t] = {'rate': rate, 'ex': ex, 'pay': pay, 'yield': yield_pct}
        except:
            d[t] = {'rate': 0, 'ex': 'Err', 'pay': 'Err', 'yield': 0}
    return d

# ── HEADER ────────────────────────────────────────────────────────
st.markdown("<h1>Proyección de Dividendos</h1>", unsafe_allow_html=True)
st.markdown(
    '<div style="color:#475569;font-size:0.85rem;font-family:JetBrains Mono,monospace;'
    'margin-top:-8px;margin-bottom:24px">Estimación anual basada en posiciones actuales</div>',
    unsafe_allow_html=True
)

ops = ver_operaciones(USER_ID)

if not ops.empty:
    ops['cant_neta'] = ops.apply(lambda x: x['cantidad'] if x['tipo']=='Compra' else -x['cantidad'], axis=1)
    pos = ops.groupby('ticker')['cant_neta'].sum().reset_index()
    pos = pos[pos['cant_neta'] > 0]

    if not pos.empty:
        inf = info_divs(pos['ticker'].tolist())
        div_df = pd.DataFrame.from_dict(inf, orient='index').reset_index().rename(columns={'index':'ticker'})
        res = pos.merge(div_df, on='ticker')
        res_con_div = res[res['rate'] > 0].copy()

        if not res_con_div.empty:
            res_con_div['est_anual']     = res_con_div['cant_neta'] * res_con_div['rate']
            res_con_div['est_mensual']   = res_con_div['est_anual'] / 12
            total_anual   = res_con_div['est_anual'].sum()
            total_mensual = total_anual / 12

            # ── SUMMARY METRICS ───────────────────────────────────
            c1, c2, c3 = st.columns(3)
            with c1: metric_card("Total anual estimado",   f"US$ {total_anual:,.2f}",   color="green")
            with c2: metric_card("Promedio mensual",        f"US$ {total_mensual:,.2f}", color="blue")
            with c3: metric_card("Acciones que pagan div.", f"{len(res_con_div)}",
                                 subtitle=f"de {len(pos)} en cartera", color="default")

            st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

            # ── TABLE ─────────────────────────────────────────────
            section_header("Detalle por activo")

            cols_h = st.columns([1.2, 1, 1, 1, 1.2, 1.2, 1.2])
            for col, lbl in zip(cols_h, ["Ticker","Acciones","Div/Acc","Yield","Est. Anual","Ex-Div","Pago"]):
                col.markdown(
                    f'<span style="font-size:0.65rem;text-transform:uppercase;letter-spacing:1px;'
                    f'color:#334155;font-family:JetBrains Mono,monospace">{lbl}</span>',
                    unsafe_allow_html=True
                )
            st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

            for _, r in res_con_div.sort_values('est_anual', ascending=False).iterrows():
                cols = st.columns([1.2, 1, 1, 1, 1.2, 1.2, 1.2])
                cols[0].markdown(f'<span style="color:#e2e8f0;font-family:JetBrains Mono,monospace;font-weight:500;font-size:0.9rem">{r["ticker"]}</span>', unsafe_allow_html=True)
                cols[1].markdown(f'<span style="color:#94a3b8;font-family:JetBrains Mono,monospace;font-size:0.82rem">{r["cant_neta"]:.4f}</span>', unsafe_allow_html=True)
                cols[2].markdown(f'<span style="color:#cbd5e1;font-family:JetBrains Mono,monospace;font-size:0.82rem">${r["rate"]:.4f}</span>', unsafe_allow_html=True)
                yield_color = "#10b981" if r['yield'] > 3 else "#94a3b8"
                cols[3].markdown(f'<span style="color:{yield_color};font-family:JetBrains Mono,monospace;font-size:0.82rem">{r["yield"]:.2f}%</span>', unsafe_allow_html=True)
                cols[4].markdown(f'<span style="color:#10b981;font-family:JetBrains Mono,monospace;font-size:0.85rem;font-weight:500">${r["est_anual"]:,.2f}</span>', unsafe_allow_html=True)
                ex_color  = "#f59e0b" if r['ex']  != "N/A" else "#334155"
                pay_color = "#3b82f6" if r['pay'] != "N/A" else "#334155"
                cols[5].markdown(f'<span style="color:{ex_color};font-family:JetBrains Mono,monospace;font-size:0.78rem">{r["ex"]}</span>', unsafe_allow_html=True)
                cols[6].markdown(f'<span style="color:{pay_color};font-family:JetBrains Mono,monospace;font-size:0.78rem">{r["pay"]}</span>', unsafe_allow_html=True)
                st.markdown("<div style='height:2px;background:#0a0f1e;margin:3px 0'></div>", unsafe_allow_html=True)

            # ── SIN DIVIDENDO ─────────────────────────────────────
            sin_div = res[res['rate'] == 0]
            if not sin_div.empty:
                st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
                tickers_sin = ", ".join(sin_div['ticker'].tolist())
                st.markdown(
                    f'<div style="color:#334155;font-size:0.8rem;font-family:JetBrains Mono,monospace;'
                    f'padding:12px;border:1px solid #1a2540;border-radius:8px">'
                    f'Sin dividendo: {tickers_sin}</div>',
                    unsafe_allow_html=True
                )
        else:
            st.info("Ninguna de tus acciones actuales paga dividendos.")
    else:
        st.info("Sin posiciones abiertas.")
else:
    st.info("Sin datos de operaciones.")