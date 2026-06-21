"""Carga individual de transacciones — formulario completo con validaciones."""
import json
import streamlit as st
from datetime import date
from pathlib import Path

from core.db import execute_query, execute_command
from core.validators import validar_monto, validar_fecha, validar_categoria
from core.widgets import fecha_input_es

if "user" not in st.session_state:
    st.error("Debes iniciar sesión para acceder a esta página.")
    st.stop()
USER_ID = st.session_state.user["id"]

_CATEGORIAS_PATH = Path(__file__).parent.parent / "config" / "categorias.json"

TIPOS  = ["Efectivo", "Yape", "Plin", "Debito", "Credito", "Transferencia"]
BANCOS = ["", "BCP", "BBVA", "Interbank", "Scotiabank", "Otro"]


@st.cache_data
def _get_categorias() -> dict:
    return json.loads(_CATEGORIAS_PATH.read_text(encoding="utf-8"))


def _get_tarjetas_activas() -> list[str]:
    rows = execute_query(
        "SELECT alias FROM tarjetas WHERE activa = TRUE AND user_id = %s ORDER BY alias",
        (USER_ID,),
    )
    return [r["alias"] for r in rows]


def _get_tarjeta_id(alias: str) -> int | None:
    rows = execute_query(
        "SELECT id FROM tarjetas WHERE alias = %s AND user_id = %s",
        (alias, USER_ID),
    )
    return rows[0]["id"] if rows else None


def render():
    st.title("✏️ Carga Individual")

    categorias = _get_categorias()
    tarjetas   = ["(ninguna)"] + _get_tarjetas_activas()
    macros     = list(categorias.keys())

    with st.form("form_carga_individual", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            fecha       = fecha_input_es("Fecha", default=date.today(), key="ci_fecha", max_year=date.today().year)
            monto       = st.number_input("Monto (S/)", min_value=0.01, step=0.10, format="%.2f")
            tipo        = st.selectbox("Tipo de movimiento", TIPOS)
            banco       = st.selectbox("Banco", BANCOS)
            tarjeta     = st.selectbox("Tarjeta (opcional)", tarjetas)

        with col2:
            macro       = st.selectbox("Categoría macro *", macros)
            subs        = categorias.get(macro, [])
            sub         = (
                st.selectbox("Sub-categoría", [""] + subs)
                if subs else st.text_input("Sub-categoría")
            )
            descripcion     = st.text_input("Descripción")
            establecimiento = st.text_input("Establecimiento")

        col3, col4 = st.columns(2)
        with col3:
            tag   = st.text_input("Tag (ej: viaje-cusco)")
        with col4:
            notas = st.text_area("Notas", height=68)

        submitted = st.form_submit_button("Guardar y agregar otra", type="primary")

    if submitted:
        errores = []
        err = validar_monto(monto)
        if err:
            errores.append(err)
        err = validar_fecha(fecha.isoformat())
        if err:
            errores.append(err)
        err = validar_categoria(macro)
        if err:
            errores.append(err)

        if errores:
            for e in errores:
                st.error(e)
            return

        try:
            tarjeta_alias_val = None if tarjeta == "(ninguna)" else tarjeta
            tarjeta_id_val    = _get_tarjeta_id(tarjeta) if tarjeta != "(ninguna)" else None

            execute_command(
                """INSERT INTO transacciones
                   (user_id, fecha_iso, monto, tipo_movimiento, banco,
                    tarjeta_id, tarjeta_alias, categoria_macro, categoria_sub,
                    descripcion, establecimiento, tag, notas, origen)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'manual')""",
                (
                    USER_ID,
                    fecha.isoformat(),
                    round(float(monto), 2),
                    tipo,
                    banco or None,
                    tarjeta_id_val,
                    tarjeta_alias_val,
                    macro,
                    sub or None,
                    descripcion or None,
                    establecimiento or None,
                    tag or None,
                    notas or None,
                ),
            )
            st.success("✓ Transacción guardada. Formulario listo para otra.")
        except Exception as e:
            st.error(f"Error al guardar: {e}")


render()
