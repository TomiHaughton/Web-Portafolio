import streamlit as st
import psycopg2
import hashlib

st.set_page_config(page_title="Portfolio · Login", layout="centered")

# ── STYLES ────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=swap');

html, body, .stApp {
    background-color: #070c18 !important;
    color: #e2e8f0 !important;
}

/* Financial grid background */
.stApp::before {
    content: '';
    position: fixed;
    inset: 0;
    background-image:
        linear-gradient(rgba(16,185,129,0.03) 1px, transparent 1px),
        linear-gradient(90deg, rgba(16,185,129,0.03) 1px, transparent 1px);
    background-size: 40px 40px;
    pointer-events: none;
    z-index: 0;
}
/* Glow spots */
.stApp::after {
    content: '';
    position: fixed;
    inset: 0;
    background:
        radial-gradient(ellipse 60% 40% at 20% 20%, rgba(16,185,129,0.04) 0%, transparent 70%),
        radial-gradient(ellipse 50% 35% at 80% 75%, rgba(59,130,246,0.04) 0%, transparent 70%);
    pointer-events: none;
    z-index: 0;
}
*, p, span, div, label { font-family: 'DM Sans', sans-serif !important; }

/* Hide sidebar only on login screen — shown via JS after login */
.hide-sidebar [data-testid="stSidebar"] { display: none !important; }
.hide-sidebar [data-testid="collapsedControl"] { display: none !important; }

h1, h2, h3 {
    font-family: 'DM Sans', sans-serif !important;
    color: #f1f5f9 !important;
}

/* Inputs */
.stTextInput > div > div > input {
    background: #0f1729 !important;
    color: #e2e8f0 !important;
    border: 1px solid #1e2e4a !important;
    border-radius: 10px !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.9rem !important;
    padding: 10px 14px !important;
}
.stTextInput > div > div > input:focus {
    border-color: #10b981 !important;
    box-shadow: 0 0 0 2px rgba(16,185,129,0.12) !important;
}
.stTextInput label {
    color: #475569 !important;
    font-size: 0.72rem !important;
    text-transform: uppercase !important;
    letter-spacing: 1px !important;
    font-family: 'JetBrains Mono', monospace !important;
}

/* Forms */
[data-testid="stForm"] {
    background: #0b1220 !important;
    border: 1px solid #1a2540 !important;
    border-radius: 16px !important;
    padding: 28px !important;
}

/* Submit buttons */
[data-testid="stFormSubmitButton"] > button {
    background: linear-gradient(135deg, #059669, #10b981) !important;
    color: #f0fdf4 !important;
    border: none !important;
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.9rem !important;
    border-radius: 10px !important;
    padding: 10px 24px !important;
    width: 100% !important;
    transition: opacity 0.2s !important;
}
[data-testid="stFormSubmitButton"] > button:hover { opacity: 0.88 !important; }

/* Alerts */
.stSuccess { background: rgba(16,185,129,0.08) !important; border: 1px solid rgba(16,185,129,0.3) !important; border-radius: 10px !important; color: #6ee7b7 !important; }
.stError   { background: rgba(239,68,68,0.08)  !important; border: 1px solid rgba(239,68,68,0.3)  !important; border-radius: 10px !important; color: #fca5a5 !important; }

/* Divider */
hr { border-color: #1a2540 !important; margin: 24px 0 !important; }

/* Sidebar */
[data-testid="stSidebar"] {
    background: #0b1220 !important;
    border-right: 1px solid #1a2540 !important;
}

.material-symbols-rounded {
    font-family: 'Material Symbols Rounded' !important;
    font-size: 20px !important;
    line-height: 1 !important;
}

/* Scrollbar */
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: #070c18; }
::-webkit-scrollbar-thumb { background: #1e2e4a; border-radius: 2px; }

@keyframes fadeUp {
    from { opacity: 0; transform: translateY(12px); }
    to   { opacity: 1; transform: translateY(0); }
}
.fade-in { animation: fadeUp 0.4s ease-out; }
</style>
""", unsafe_allow_html=True)

# ── DB ────────────────────────────────────────────────────────────
def conectar_db():
    return psycopg2.connect(
        host=st.secrets["connections"]["supabase"]["host"],
        database=st.secrets["connections"]["supabase"]["database"],
        user=st.secrets["connections"]["supabase"]["username"],
        password=st.secrets["connections"]["supabase"]["password"],
        port=st.secrets["connections"]["supabase"]["port"]
    )

def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def verify_password(password, hashed):
    return hash_password(password) == hashed

def anadir_usuario(username, password):
    conn = conectar_db()
    try:
        conn.cursor().execute(
            "INSERT INTO usuarios (username, password) VALUES (%s, %s)",
            (username, hash_password(password))
        )
        conn.commit()
        return True
    except:
        return False
    finally:
        conn.close()

def obtener_usuario(username):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM usuarios WHERE username = %s", (username,))
    user = cursor.fetchone()
    conn.close()
    return user

# ── SESSION ───────────────────────────────────────────────────────
if 'user' not in st.session_state:
    st.session_state.user = None

def ocultar_pagina(nombre):
    st.markdown(
        f'<style>[data-testid="stSidebarNav"] li a[href*="/{nombre}"] {{display:none}}</style>',
        unsafe_allow_html=True
    )

if st.session_state.user:
    if not st.session_state.user[3]:
        ocultar_pagina("Admin")
else:
    # Hide sidebar on login screen
    st.markdown('<style>[data-testid="stSidebar"]{display:none!important}[data-testid="collapsedControl"]{display:none!important}</style>', unsafe_allow_html=True)
    for p in ["Dashboard","Watchlist","Ingresos_y_Gastos","Análisis_Gráfico","Dividendos","Admin"]:
        ocultar_pagina(p)

# ── LOGGED IN STATE ───────────────────────────────────────────────
if st.session_state.user:
    username = st.session_state.user[1]

    st.markdown(f"""
        <div class="fade-in" style="text-align:center;padding:60px 0 40px">
            <div style="
                width:64px;height:64px;border-radius:50%;
                background:linear-gradient(135deg,#059669,#10b981);
                display:flex;align-items:center;justify-content:center;
                margin:0 auto 20px;font-size:1.6rem
            ">📊</div>
            <h1 style="font-size:1.8rem;margin:0 0 8px">Bienvenido, {username}</h1>
            <p style="color:#475569;font-family:JetBrains Mono,monospace;font-size:0.85rem;margin:0">
                Tu portafolio te espera
            </p>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("""
        <div style="
            background:#0b1220;border:1px solid #1a2540;border-left:3px solid #10b981;
            border-radius:12px;padding:16px 20px;margin-bottom:24px;text-align:center
        ">
            <span style="color:#475569;font-size:0.8rem;font-family:JetBrains Mono,monospace">
                Conectado a Supabase
            </span>
            <span style="color:#10b981;font-size:0.8rem;font-family:JetBrains Mono,monospace;margin-left:8px">
                ● En línea
            </span>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("""
        <div style="
            background:#0b1220;border:1px solid #1a2540;border-radius:12px;
            padding:20px 24px;margin-bottom:24px
        ">
            <div style="color:#475569;font-size:0.65rem;text-transform:uppercase;
                        letter-spacing:1.2px;font-family:JetBrains Mono,monospace;margin-bottom:12px">
                Acceso rápido
            </div>
            <div style="color:#94a3b8;font-size:0.88rem;line-height:1.8">
                👈 Seleccioná una página en la barra lateral para empezar
            </div>
        </div>
    """, unsafe_allow_html=True)

    if st.button("Cerrar sesión", use_container_width=True):
        st.session_state.user = None
        st.session_state['portfolio_label'] = None
        st.session_state['portfolio_id']    = None
        st.rerun()

# ── LOGIN SCREEN ──────────────────────────────────────────────────
else:
    # Header
    st.markdown("""
        <div class="fade-in" style="text-align:center;padding:48px 0 28px">
            <!-- Mini ticker tape -->
            <div style="
                display:flex;justify-content:center;gap:16px;margin-bottom:28px;
                overflow:hidden;opacity:0.5
            ">
                <span style="color:#10b981;font-size:0.72rem;font-family:JetBrains Mono,monospace">SPY +0.8%</span>
                <span style="color:#334155;font-size:0.72rem">|</span>
                <span style="color:#ef4444;font-size:0.72rem;font-family:JetBrains Mono,monospace">BTC -1.2%</span>
                <span style="color:#334155;font-size:0.72rem">|</span>
                <span style="color:#10b981;font-size:0.72rem;font-family:JetBrains Mono,monospace">GLD +0.3%</span>
                <span style="color:#334155;font-size:0.72rem">|</span>
                <span style="color:#10b981;font-size:0.72rem;font-family:JetBrains Mono,monospace">QQQ +1.1%</span>
                <span style="color:#334155;font-size:0.72rem">|</span>
                <span style="color:#ef4444;font-size:0.72rem;font-family:JetBrains Mono,monospace">MELI -0.4%</span>
            </div>
            <div style="
                font-size:2.4rem;font-weight:800;color:#f1f5f9;
                font-family:'DM Sans',sans-serif;letter-spacing:-1px;margin-bottom:8px
            ">Portfolio</div>
            <div style="
                color:#334155;font-size:0.78rem;
                font-family:'JetBrains Mono',monospace;letter-spacing:2.5px;
                text-transform:uppercase
            ">Control total sobre tus inversiones</div>
        </div>
    """, unsafe_allow_html=True)

    # Stats bar
    st.markdown("""
        <div style="
            display:flex;justify-content:center;gap:32px;
            margin-bottom:36px;padding:16px;
            background:#0b1220;border:1px solid #1a2540;border-radius:12px
        ">
            <div style="text-align:center">
                <div style="color:#10b981;font-size:1.1rem;font-weight:500;
                            font-family:'JetBrains Mono',monospace">Multi</div>
                <div style="color:#334155;font-size:0.68rem;text-transform:uppercase;
                            letter-spacing:1px;margin-top:2px">Portafolios</div>
            </div>
            <div style="width:1px;background:#1a2540"></div>
            <div style="text-align:center">
                <div style="color:#3b82f6;font-size:1.1rem;font-weight:500;
                            font-family:'JetBrains Mono',monospace">Real</div>
                <div style="color:#334155;font-size:0.68rem;text-transform:uppercase;
                            letter-spacing:1px;margin-top:2px">Tiempo</div>
            </div>
            <div style="width:1px;background:#1a2540"></div>
            <div style="text-align:center">
                <div style="color:#f59e0b;font-size:1.1rem;font-weight:500;
                            font-family:'JetBrains Mono',monospace">ARS</div>
                <div style="color:#334155;font-size:0.68rem;text-transform:uppercase;
                            letter-spacing:1px;margin-top:2px">+ USD</div>
            </div>
            <div style="width:1px;background:#1a2540"></div>
            <div style="text-align:center">
                <div style="color:#8b5cf6;font-size:1.1rem;font-weight:500;
                            font-family:'JetBrains Mono',monospace">VS</div>
                <div style="color:#334155;font-size:0.68rem;text-transform:uppercase;
                            letter-spacing:1px;margin-top:2px">Benchmarks</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    tab_login, tab_register = st.tabs(["Iniciar sesión", "Registrarse"])

    with tab_login:
        with st.form("login_form"):
            st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
            login_user = st.text_input("Usuario", placeholder="Tu nombre de usuario", key="login_user")
            login_pass = st.text_input("Contraseña", type="password", placeholder="••••••••", key="login_pass")
            st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

            if st.form_submit_button("Ingresar", use_container_width=True):
                try:
                    user_data = obtener_usuario(login_user)
                    if user_data and verify_password(login_pass, user_data[2]):
                        st.session_state.user = user_data
                        st.rerun()
                    else:
                        st.error("Usuario o contraseña incorrectos.")
                except Exception as e:
                    st.error(f"Error de conexión: {e}")

    with tab_register:
        with st.form("register_form"):
            st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
            reg_user = st.text_input("Elegí un usuario", placeholder="nombre_usuario", key="reg_user")
            reg_pass = st.text_input("Elegí una contraseña", type="password", placeholder="••••••••", key="reg_pass")
            st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

            if st.form_submit_button("Crear cuenta", use_container_width=True):
                if reg_user and reg_pass:
                    if anadir_usuario(reg_user, reg_pass):
                        st.success("Cuenta creada. Ahora iniciá sesión.")
                    else:
                        st.error("Ese usuario ya existe.")
                else:
                    st.warning("Completá usuario y contraseña.")

    # Footer
    st.markdown("""
        <div style="text-align:center;margin-top:32px;color:#1e2e4a;
                    font-size:0.72rem;font-family:'JetBrains Mono',monospace">
            Datos en tiempo real vía Yahoo Finance · DB en Supabase
        </div>
    """, unsafe_allow_html=True)