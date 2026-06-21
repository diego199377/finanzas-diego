"""Punto de entrada — configuración de página, login y navegación."""
import streamlit as st

from core.styles import inject_css, get_tema
from core import session_persist

# ── Inicialización de estado (antes de cualquier render) ─────────────────────
if "tema" not in st.session_state:
    st.session_state.tema = "oscuro"

# set_page_config debe ser el primer comando de render de Streamlit
st.set_page_config(
    page_title="Finanzas Diego",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Forzar sidebar cerrado en móvil (workaround Streamlit Cloud)
st.markdown("""
<script>
(function() {
    const checkMobile = () => window.innerWidth < 768;
    const closeSidebar = () => {
        if (!checkMobile()) return;
        const sidebar = window.parent.document.querySelector('[data-testid="stSidebar"]');
        if (sidebar) {
            const ariaExpanded = sidebar.getAttribute('aria-expanded');
            if (ariaExpanded === 'true') {
                const closeBtn = window.parent.document.querySelector('[data-testid="stSidebarCollapseButton"] button, [kind="header"]');
                if (closeBtn) closeBtn.click();
            }
        }
    };
    // Intentar varias veces porque Streamlit es lento al cargar
    setTimeout(closeSidebar, 100);
    setTimeout(closeSidebar, 500);
    setTimeout(closeSidebar, 1000);
    setTimeout(closeSidebar, 2000);
})();
</script>
""", unsafe_allow_html=True)
# ── HANDLER DE LOGOUT ────────────────────────────────────────────────────────
# Flujo: botón → ?logout=1 en URL → rerun → este handler → cookie borrada
# → session limpia → rerun limpio.
# El flag _logout_done evita que load_session() re-autentique con la cookie
# que st.context.cookies aún tiene en caché para esta sesión WebSocket.
if "logout" in st.query_params:
    session_persist.clear_session()          # borra cookie via JS
    if "user" in st.session_state:
        del st.session_state.user
    st.session_state["_logout_done"] = True  # bloquea load_session en esta sesión
    import time
    time.sleep(0.8)                          # dar tiempo al JS para ejecutar
    st.query_params.clear()
    st.rerun()

# ── 1. Estado inicial ────────────────────────────────────────────────────────
_logged_in = "user" in st.session_state

inject_css()

# ── Forzar locale español-Perú en date pickers nativos del navegador ─────────
st.html("""
<script>
(function() {
    document.documentElement.lang = 'es-PE';
    function aplicarLocale() {
        document.querySelectorAll('input[type="date"], input[type="datetime-local"], input[type="time"]').forEach(function(input) {
            input.setAttribute('lang', 'es-PE');
        });
    }
    aplicarLocale();
    var observer = new MutationObserver(aplicarLocale);
    observer.observe(document.body, { childList: true, subtree: true });
})();
</script>
""")

# ── 2. Restaurar sesión desde cookie ─────────────────────────────────────────
# Omitir si acabamos de hacer logout: st.context.cookies aún tiene la cookie
# del request original y load_session() volvería a autenticar al usuario.
if not _logged_in and not st.session_state.get("_logout_done"):
    _user = session_persist.load_session()
    if _user:
        st.session_state.user = _user
        st.rerun()


# ── 3. Pantalla de login / registro (vistas separadas) ───────────────────────

def _vista_login(p: dict):
    """Vista de iniciar sesión — solo 1 password input, Chrome no sugiere nueva."""
    st.html(f"""
    <div style="text-align: center; margin-bottom: 1.5rem;">
        <div style="color: {p['texto_terciario']}; font-size: 13px;">Acceso seguro a tu información financiera</div>
    </div>
    """)

    with st.form("form_login", enter_to_submit=True):
        email = st.text_input(
            "Correo electrónico",
            placeholder="tu.correo@gmail.com",
            key="login_email",
        )
        password = st.text_input(
            "Contraseña",
            type="password",
            placeholder="••••••••",
            key="login_password",
        )
        submit = st.form_submit_button("Iniciar sesión", use_container_width=True)

    st.html("""
    <script>
    setTimeout(() => {
        const doc = window.parent.document;
        doc.querySelectorAll('input[type="text"]').forEach(i => {
            if ((i.placeholder || '').toLowerCase().includes('correo') ||
                (i.getAttribute('aria-label') || '').toLowerCase().includes('correo')) {
                i.setAttribute('autocomplete', 'email');
            }
        });
        doc.querySelectorAll('input[type="password"]').forEach(i => {
            i.setAttribute('autocomplete', 'current-password');
        });
    }, 100);
    </script>
    """)

    if submit:
        if not email or not password:
            st.error("Ingresa tu email y contraseña.")
        else:
            from core.auth import authenticate_user
            user = authenticate_user(email, password)
            if user:
                st.session_state.user = user
                session_persist.save_session(user["id"])
                import time
                time.sleep(0.5)
                st.rerun()
            else:
                st.error("Email o contraseña incorrectos.")

    st.html(f"""
    <div style="text-align: center; margin-top: 1.5rem; padding-top: 1.5rem; border-top: 1px solid {p['borde']};">
        <div style="color: {p['texto_terciario']}; font-size: 13px; margin-bottom: 8px;">¿No tienes cuenta?</div>
    </div>
    """)
    if st.button("Crear cuenta nueva →", use_container_width=True, key="ir_a_registro"):
        st.session_state.vista_auth = "registro"
        st.rerun()


def _vista_registro(p: dict):
    """Vista de crear cuenta — 2 password inputs, Chrome sí sugiere contraseña fuerte."""
    st.html(f"""
    <div style="text-align: center; margin-bottom: 1.5rem;">
        <div style="color: {p['texto_terciario']}; font-size: 13px;">Crea tu cuenta personal</div>
    </div>
    """)

    with st.form("form_registro", enter_to_submit=True):
        nombre = st.text_input(
            "Nombre para mostrar",
            placeholder="Ej: Diego, Jesús Sinche, Mi Dinero",
            key="reg_nombre",
        )
        email = st.text_input(
            "Correo electrónico",
            placeholder="tu.correo@gmail.com",
            key="reg_email",
        )
        password = st.text_input(
            "Contraseña",
            type="password",
            placeholder="Mínimo 8 caracteres",
            key="reg_password",
        )
        password_confirm = st.text_input(
            "Confirmar contraseña",
            type="password",
            key="reg_password_confirm",
        )
        submit = st.form_submit_button("Crear cuenta", use_container_width=True)

    st.html("""
    <script>
    setTimeout(() => {
        const doc = window.parent.document;
        doc.querySelectorAll('input[type="text"]').forEach(i => {
            const label = (i.getAttribute('aria-label') || '').toLowerCase();
            if (label.includes('correo') || label.includes('email')) {
                i.setAttribute('autocomplete', 'email');
            } else if (label.includes('nombre')) {
                i.setAttribute('autocomplete', 'name');
            }
        });
        doc.querySelectorAll('input[type="password"]').forEach(i => {
            i.setAttribute('autocomplete', 'new-password');
        });
    }, 100);
    </script>
    """)

    if submit:
        if not nombre or not email or not password:
            st.error("Todos los campos son obligatorios.")
        elif password != password_confirm:
            st.error("Las contraseñas no coinciden.")
        elif len(password) < 8:
            st.error("La contraseña debe tener al menos 8 caracteres.")
        else:
            from core.auth import create_user
            success, msg, uid = create_user(email, password, nombre)
            if success:
                st.success("¡Cuenta creada! Ahora puedes iniciar sesión.")
                st.session_state.vista_auth = "login"
                import time
                time.sleep(1.5)
                st.rerun()
            else:
                st.error(msg)

    st.html(f"""
    <div style="text-align: center; margin-top: 1.5rem; padding-top: 1.5rem; border-top: 1px solid {p['borde']};">
        <div style="color: {p['texto_terciario']}; font-size: 13px; margin-bottom: 8px;">¿Ya tienes cuenta?</div>
    </div>
    """)
    if st.button("← Iniciar sesión", use_container_width=True, key="ir_a_login"):
        st.session_state.vista_auth = "login"
        st.rerun()


def _mostrar_login():
    """Pantalla de autenticación con vistas separadas login / registro."""
    p = get_tema()

    if "vista_auth" not in st.session_state:
        st.session_state.vista_auth = "login"

    st.html(f"""<style>
    [data-testid="stSidebar"] {{ display: none !important; }}
    [data-testid="stSidebarCollapsedControl"] {{ display: none !important; }}
    [data-testid="InputInstructions"] {{ display: none !important; }}
    .stApp {{ background: {p["bg_principal"]} !important; }}
    </style>""")

    col_izq, col_centro, col_der = st.columns([1, 1.2, 1])
    with col_centro:
        st.html(f"""
        <div style="text-align: center; padding-top: 2rem; margin-bottom: 1.5rem;">
            <div style="display: inline-flex; align-items: center; gap: 14px;">
                <div style="width: 48px; height: 48px; background: {p['azul_corporativo']}; border-radius: 10px; display: flex; align-items: center; justify-content: center;">
                    <span style="color: white; font-size: 24px; font-weight: 600; font-family: Georgia, serif;">F</span>
                </div>
                <div style="text-align: left;">
                    <div style="color: {p['texto_secundario']}; font-size: 10px; letter-spacing: 2.5px; text-transform: uppercase; margin-bottom: 2px;">Gestión financiera</div>
                    <div style="color: {p['texto_primario']}; font-size: 20px; font-weight: 500; font-family: Georgia, serif;">Finanzas</div>
                </div>
            </div>
            <div style="height: 1px; background: {p['borde']}; margin: 24px auto; max-width: 240px;"></div>
        </div>
        """)

        if st.session_state.vista_auth == "login":
            _vista_login(p)
        else:
            _vista_registro(p)

        st.html(f"""
        <div style="text-align: center; margin-top: 2rem;">
            <div style="color: {p['texto_terciario']}; font-size: 10px; letter-spacing: 1px;">SEGURO · CIFRADO · PRIVADO</div>
        </div>
        """)


if not _logged_in:
    _mostrar_login()
    st.stop()

# ── CSS post-login: sidebar siempre visible ───────────────────────────────────
st.html("""<style>
[data-testid="stSidebar"] {
    display: flex !important;
    visibility: visible !important;
    transform: none !important;
    margin-left: 0 !important;
    min-width: 244px !important;
}
[data-testid="stSidebar"][aria-expanded="false"] {
    display: flex !important;
    transform: translateX(0) !important;
}
[data-testid="stSidebarCollapsedControl"] {
    display: flex !important;
    visibility: visible !important;
    opacity: 1 !important;
}
[data-testid="stSidebarNav"] > div > div > div > p,
[data-testid="stSidebarNav"] > div > div > div > div > p,
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] p {
    font-size: 0.75rem !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
    color: #8b8e98 !important;
    margin-top: 1rem !important;
    margin-bottom: 0.5rem !important;
    padding-left: 0.5rem !important;
    display: block !important;
}
</style>""")

# ── 4. Sidebar superior: header ejecutivo + toggle tema ───────────────────────
with st.sidebar:
    nombre = st.session_state.user.get("nombre_display") or "Usuario"
    p = get_tema()

    st.html(f"""
    <div style="padding: 8px 4px 20px; border-bottom: 1px solid {p['borde']}; margin-bottom: 16px;">
        <div style="color: {p['texto_secundario']}; font-size: 9px; letter-spacing: 2px; text-transform: uppercase; margin-bottom: 4px;">Gestión financiera</div>
        <div style="color: {p['texto_primario']}; font-family: Georgia, serif; font-size: 16px; font-weight: 500;">Finanzas · {nombre}</div>
    </div>
    """)

    tema_actual = st.session_state.get("tema", "oscuro")
    icono = "☀️ Modo claro" if tema_actual == "oscuro" else "🌙 Modo oscuro"
    if st.button(icono, use_container_width=True, key="toggle_tema"):
        st.session_state.tema = "claro" if tema_actual == "oscuro" else "oscuro"
        st.rerun()

    st.divider()

# ── 5. Navegación ─────────────────────────────────────────────────────────────
paginas = {
    "Día a día": [
        st.Page("pages/carga_rapida.py",      title="Carga Rápida",       icon="⚡", default=True),
        st.Page("pages/carga_individual.py",  title="Carga Individual",   icon="✏️"),
        st.Page("pages/importar_correos.py",  title="Importar de Gmail",  icon="📧"),
        st.Page("pages/por_clasificar.py",    title="Por Clasificar",     icon="🔍"),
        st.Page("pages/transacciones.py",     title="Transacciones",      icon="📋"),
    ],
    "Análisis": [
        st.Page("pages/dashboard.py",        title="Panel",              icon="📊"),
    ],
    "Configuración": [
        st.Page("pages/ingresos.py",         title="Ingresos",           icon="💰"),
        st.Page("pages/deudas_prestamos.py", title="Deudas y Préstamos", icon="💸"),
        st.Page("pages/tarjetas.py",         title="Tarjetas",           icon="💳"),
        st.Page("pages/perfil.py",           title="Mi perfil",          icon="👤"),
    ],
}

pg = st.navigation(paginas)

# ── Banner de auto-importación ────────────────────────────────────────────────
# Verifica correos nuevos una vez por sesión; se apoya en session_state como
# caché para no llamar a Gmail en cada rerun.
from core.auto_import import (
    contar_correos_nuevos,
    gmail_esta_conectado,
    procesar_correos_nuevos_auto,
)

_uid = st.session_state.user["id"]

if "correos_nuevos_count" not in st.session_state:
    if gmail_esta_conectado():
        try:
            _cant, _desde = contar_correos_nuevos(_uid)
        except Exception:
            _cant, _desde = 0, None
        st.session_state.correos_nuevos_count = _cant
        st.session_state.correos_nuevos_fecha = _desde
    else:
        st.session_state.correos_nuevos_count = 0
        st.session_state.correos_nuevos_fecha = None

if (
    st.session_state.correos_nuevos_count > 0
    and not st.session_state.get("banner_descartado", False)
):
    _n = st.session_state.correos_nuevos_count
    _s = "s" if _n > 1 else ""

    bcol1, bcol2, bcol3 = st.columns([4, 1, 0.5])
    with bcol1:
        st.info(f"📧 **{_n} correo{_s} nuevo{_s} del banco** sin procesar")
    with bcol2:
        if st.button("Procesar", key="btn_auto_procesar", type="primary", use_container_width=True):
            with st.spinner(f"Procesando {_n} correo{_s}..."):
                _res = procesar_correos_nuevos_auto(_uid)
            _ag  = _res.get("auto_guardadas", 0)
            _pend = _res.get("pendientes_revision", 0)
            partes = []
            if _ag:
                partes.append(f"✅ {_ag} guardada{'s' if _ag > 1 else ''} automáticamente")
            if _pend:
                partes.append(f"⚠️ {_pend} requiere{'n' if _pend > 1 else ''} revisión → Importar de Gmail")
            if partes:
                st.success(" | ".join(partes))
            else:
                st.info("No se detectaron transacciones nuevas.")
            st.session_state.correos_nuevos_count = 0
            import time; time.sleep(2)
            st.rerun()
    with bcol3:
        if st.button("✕", key="btn_banner_cerrar", help="Ocultar este aviso"):
            st.session_state.banner_descartado = True
            st.rerun()
    st.markdown("---")

# ── Sidebar inferior: cerrar sesión ──────────────────────────────────────────
with st.sidebar:
    st.divider()
    if st.button("Cerrar sesión", use_container_width=True, key="logout_btn"):
        # Marcar logout en URL — trigger para el handler al inicio del script
        st.query_params["logout"] = "1"
        st.rerun()

pg.run()
