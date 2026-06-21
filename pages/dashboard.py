"""Panel principal — dashboard ejecutivo."""
import streamlit as st
from datetime import date
from core.styles import get_tema, heading_ejecutivo, metric_ejecutiva

if "user" not in st.session_state:
    st.error("Debes iniciar sesión.")
    st.stop()

USER_ID = st.session_state.user["id"]
p = get_tema()

MESES_ES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]
hoy = date.today()
mes_nombre = MESES_ES[hoy.month - 1]

heading_ejecutivo(
    label_uppercase="Reporte mensual",
    titulo=f"{mes_nombre} {hoy.year}",
    subtitulo=f"Generado al {hoy.strftime('%d/%m/%Y')} · Día {hoy.day} de {hoy.day + 16}",
)

st.info("📊 Las visualizaciones del dashboard se completarán en la próxima sub-sesión (4C).")
