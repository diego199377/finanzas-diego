"""Sistema de diseño ejecutivo para Finanzas Diego."""
import streamlit as st

# Paletas de tema
PALETA_OSCURA = {
    "bg_principal": "#0a1024",
    "bg_card": "#0f1729",
    "borde": "#1e293b",
    "texto_primario": "#f1f5f9",
    "texto_secundario": "#94a3b8",
    "texto_terciario": "#64748b",
    "azul_corporativo": "#1e3a8a",
    "azul_acento": "#3b82f6",
    "verde_ingreso": "#10b981",
    "rojo_gasto": "#ef4444",
    "amarillo_alerta": "#f59e0b",
}

PALETA_CLARA = {
    "bg_principal": "#fafafa",
    "bg_card": "#ffffff",
    "borde": "#e2e8f0",
    "texto_primario": "#0f1729",
    "texto_secundario": "#475569",
    "texto_terciario": "#94a3b8",
    "azul_corporativo": "#1e3a8a",
    "azul_acento": "#3b82f6",
    "verde_ingreso": "#10b981",
    "rojo_gasto": "#ef4444",
    "amarillo_alerta": "#f59e0b",
}


def get_tema():
    """Devuelve la paleta activa según session_state.tema."""
    tema = st.session_state.get("tema", "oscuro")
    return PALETA_OSCURA if tema == "oscuro" else PALETA_CLARA


def inject_css():
    """Inyecta el CSS global de la app con el tema activo."""
    p = get_tema()

    st.html(f"""
    <style>
    /* === BASE === */
    .stApp {{
        background: {p["bg_principal"]} !important;
        color: {p["texto_primario"]} !important;
    }}

    /* === TIPOGRAFÍA === */
    body, .stApp, [class*="css"] {{
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }}
    h1, h2, h3, .heading-serif {{
        font-family: Georgia, 'Times New Roman', serif !important;
        font-weight: 500 !important;
        letter-spacing: -0.3px !important;
        color: {p["texto_primario"]} !important;
    }}

    /* === LABELS DE METRICAS === */
    .label-ejecutivo {{
        color: {p["texto_secundario"]};
        font-size: 11px;
        letter-spacing: 1.5px;
        text-transform: uppercase;
        font-weight: 500;
        margin-bottom: 6px;
    }}

    /* === CARDS === */
    .card-ejecutivo {{
        background: {p["bg_card"]};
        border: 1px solid {p["borde"]};
        border-radius: 10px;
        padding: 16px;
    }}

    /* === HERO METRIC === */
    .hero-metric {{
        background: {p["bg_card"]};
        border: 1px solid {p["borde"]};
        border-left: 3px solid {p["verde_ingreso"]};
        border-radius: 10px;
        padding: 20px;
        margin: 12px 0;
    }}
    .hero-metric-valor {{
        color: {p["verde_ingreso"]};
        font-family: Georgia, serif;
        font-size: 32px;
        font-weight: 400;
        letter-spacing: -1px;
        line-height: 1;
        margin-top: 6px;
    }}

    /* === BOTONES === */
    .stButton > button {{
        background: {p["azul_corporativo"]} !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 12px 20px !important;
        font-weight: 500 !important;
        font-size: 14px !important;
        transition: background 0.2s !important;
    }}
    .stButton > button:hover {{
        background: {p["azul_acento"]} !important;
    }}

    /* === INPUTS === */
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input,
    .stTextArea > div > div > textarea,
    .stSelectbox > div > div {{
        background: {p["bg_card"]} !important;
        border: 1px solid {p["borde"]} !important;
        border-radius: 8px !important;
        color: {p["texto_primario"]} !important;
    }}
    .stTextInput > div > div > input:focus,
    .stNumberInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus {{
        border-color: {p["azul_acento"]} !important;
        box-shadow: 0 0 0 1px {p["azul_acento"]} !important;
    }}

    /* === SIDEBAR === */
    section[data-testid="stSidebar"] {{
        background: {p["bg_card"]} !important;
        border-right: 1px solid {p["borde"]} !important;
    }}

    /* === TABS === */
    button[data-baseweb="tab"] {{
        color: {p["texto_secundario"]} !important;
    }}
    button[data-baseweb="tab"][aria-selected="true"] {{
        color: {p["azul_acento"]} !important;
    }}

    /* === DATAFRAMES === */
    [data-testid="stDataFrame"] {{
        background: {p["bg_card"]} !important;
        border-radius: 10px !important;
    }}

    /* === OCULTAR HEADER DE STREAMLIT === */
    header[data-testid="stHeader"] {{
        background: transparent !important;
    }}

    /* === FOOTER STREAMLIT === */
    footer {{ display: none !important; }}
    .viewerBadge_link__1S137 {{ display: none !important; }}

    /* ── Mejoras de UX en móvil (DEFINITIVA, sin romper hamburguesa) ─── */

    /* IMPORTANTE: NO ocultar botones del header (rompe la hamburguesa móvil) */

    /* Ocultar elementos de Streamlit Cloud específicos (NO el header completo) */
    [data-testid="stToolbar"] {{ display: none !important; }}
    [data-testid="stDecoration"] {{ display: none !important; }}
    [data-testid="stStatusWidget"] {{ display: none !important; }}
    [data-testid="manage-app-button"] {{ display: none !important; }}
    .viewerBadge_link__qRIco {{ display: none !important; }}
    .viewerBadge_container__1QSob {{ display: none !important; }}
    .stDeployButton {{ display: none !important; }}
    #MainMenu {{ visibility: hidden !important; }}
    footer {{ visibility: hidden !important; }}

    /* ── Móvil: ajustes responsive ─────────────────────────────────── */
    @media (max-width: 768px) {{

        /* Sidebar: ancho controlado en móvil */
        section[data-testid="stSidebar"],
        [data-testid="stSidebar"] {{
            width: 85vw !important;
            min-width: 85vw !important;
            max-width: 280px !important;
        }}

        /* Contenido principal: padding reducido */
        .main .block-container,
        [data-testid="stAppViewContainer"] .main .block-container {{
            padding-left: 1rem !important;
            padding-right: 1rem !important;
            padding-top: 1rem !important;
            padding-bottom: 4rem !important;
            max-width: 100vw !important;
        }}

        /* Títulos más legibles */
        h1, .stMarkdown h1 {{
            font-size: 1.5rem !important;
            line-height: 1.3 !important;
        }}
        h2, .stMarkdown h2 {{ font-size: 1.2rem !important; }}
        h3, .stMarkdown h3 {{ font-size: 1.05rem !important; }}

        /* Botones touch-friendly (pero NO header buttons) */
        .stButton button {{
            width: 100% !important;
            min-height: 44px !important;
            font-size: 0.95rem !important;
        }}

        /* Tablas scroll horizontal */
        [data-testid="stDataFrame"],
        [data-testid="stTable"] {{
            overflow-x: auto !important;
            -webkit-overflow-scrolling: touch !important;
            max-width: 100% !important;
        }}

        /* Métricas compactas */
        [data-testid="stMetric"] {{ margin-bottom: 0.5rem !important; }}
        [data-testid="stMetricLabel"] {{ font-size: 0.75rem !important; }}
        [data-testid="stMetricValue"] {{ font-size: 1.2rem !important; }}

        /* Inputs touch-friendly */
        .stTextInput input,
        .stTextArea textarea,
        [data-baseweb="input"] input {{
            min-height: 44px !important;
            font-size: 1rem !important;
        }}

        /* Columnas: stackear */
        [data-testid="column"] {{
            flex: 1 1 100% !important;
            width: 100% !important;
            min-width: 100% !important;
        }}

        /* Espacios verticales reducidos */
        [data-testid="stVerticalBlock"] {{
            gap: 0.5rem !important;
        }}
    }}

    /* Móvil pequeño */
    @media (max-width: 480px) {{
        .main .block-container {{
            padding-left: 0.75rem !important;
            padding-right: 0.75rem !important;
        }}
        h1, .stMarkdown h1 {{ font-size: 1.3rem !important; }}
    }}
    </style>
    """)


def heading_ejecutivo(label_uppercase: str, titulo: str, subtitulo: str = ""):
    """Renderiza un header al estilo 'REPORTE MENSUAL · Junio 2026'."""
    p = get_tema()
    sub_html = (
        f'<div style="color: {p["texto_terciario"]}; font-size: 12px; margin-top: 4px;">{subtitulo}</div>'
        if subtitulo else ""
    )
    st.html(f"""
    <div style="padding-bottom: 16px; border-bottom: 1px solid {p["borde"]}; margin-bottom: 24px;">
        <div class="label-ejecutivo" style="color: {p["texto_secundario"]}; letter-spacing: 2px; font-size: 10px; text-transform: uppercase;">{label_uppercase}</div>
        <div class="heading-serif" style="font-size: 22px; margin-top: 4px;">{titulo}</div>
        {sub_html}
    </div>
    """)


def metric_ejecutiva(label: str, valor: str, delta: str = "", delta_color: str = "neutro"):
    """Renderiza una KPI card ejecutiva. delta_color: 'verde', 'rojo', 'amarillo', 'neutro'."""
    p = get_tema()
    color_delta = {
        "verde": p["verde_ingreso"],
        "rojo": p["rojo_gasto"],
        "amarillo": p["amarillo_alerta"],
        "neutro": p["texto_terciario"],
    }.get(delta_color, p["texto_terciario"])
    delta_html = (
        f'<div style="color: {color_delta}; font-size: 11px; margin-top: 4px; font-weight: 500;">{delta}</div>'
        if delta else ""
    )
    st.html(f"""
    <div class="card-ejecutivo">
        <div class="label-ejecutivo">{label}</div>
        <div style="color: {p["texto_primario"]}; font-family: Georgia, serif; font-size: 20px; font-weight: 500; letter-spacing: -0.3px;">{valor}</div>
        {delta_html}
    </div>
    """)
