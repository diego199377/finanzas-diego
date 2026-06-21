"""Ingresos recurrentes y extras."""
import streamlit as st
import pandas as pd
from datetime import date

from core.db import execute_query, execute_command
from core.widgets import fecha_input_es

if "user" not in st.session_state:
    st.error("Debes iniciar sesión para acceder a esta página.")
    st.stop()
USER_ID = st.session_state.user["id"]


def render():
    st.title("💰 Ingresos")
    tab1, tab2 = st.tabs(["Recurrentes", "Extras"])
    with tab1:
        _tab_recurrentes()
    with tab2:
        _tab_extras()


# ── Ingresos recurrentes ──────────────────────────────────────────────────────

def _tab_recurrentes():
    st.caption("Dinero que recibes todos los meses: sueldo, alquiler, pensión, etc.")

    rows = execute_query(
        "SELECT * FROM ingresos_recurrentes WHERE user_id = %s ORDER BY dia_mes",
        (USER_ID,),
    )

    if rows:
        df = pd.DataFrame(rows)
        df["monto_fmt"]        = df["monto"].apply(lambda x: f"S/ {float(x):,.2f}")
        df["fecha_inicio_fmt"] = pd.to_datetime(df["fecha_inicio"]).dt.strftime("%d/%m/%Y")
        st.dataframe(
            df[["id", "concepto", "monto_fmt", "dia_mes", "activo", "fecha_inicio_fmt"]],
            column_config={
                "id":               st.column_config.NumberColumn("ID"),
                "concepto":         st.column_config.TextColumn("Concepto"),
                "monto_fmt":        st.column_config.TextColumn("Monto"),
                "dia_mes":          st.column_config.NumberColumn("Día del mes"),
                "activo":           st.column_config.CheckboxColumn("Activo"),
                "fecha_inicio_fmt": st.column_config.TextColumn("Desde"),
            },
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No tienes ingresos recurrentes registrados.")

    st.markdown("#### Agregar")
    with st.form("form_recurrente", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            concepto     = st.text_input("Concepto *")
            monto        = st.number_input("Monto (S/)", min_value=0.01, step=50.0, format="%.2f")
        with c2:
            dia_mes      = st.number_input("Día del mes", min_value=1, max_value=31, value=1)
            fecha_inicio = fecha_input_es("Desde", default=date.today(), key="rec_desde")
        with c3:
            activo = st.checkbox("Activo", value=True)

        if st.form_submit_button("Agregar", type="primary"):
            if not concepto.strip():
                st.error("El concepto es obligatorio.")
            elif monto <= 0:
                st.error("El monto debe ser mayor a 0.")
            else:
                try:
                    execute_command(
                        """INSERT INTO ingresos_recurrentes
                           (user_id, concepto, monto, dia_mes, activo, fecha_inicio)
                           VALUES (%s, %s, %s, %s, %s, %s)""",
                        (USER_ID, concepto.strip(), monto, dia_mes, activo,
                         fecha_inicio.isoformat()),
                    )
                    st.toast("✓ Ingreso recurrente agregado.", icon="✅")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    if rows:
        st.markdown("#### Eliminar")
        ids       = [r["id"] for r in rows]
        etiquetas = [f"ID {r['id']} — {r['concepto']}" for r in rows]
        idx       = st.selectbox("Seleccionar", range(len(ids)),
                                 format_func=lambda i: etiquetas[i],
                                 key="del_idx_rec")
        if st.button("Eliminar seleccionado", key="btn_del_rec"):
            try:
                execute_command(
                    "DELETE FROM ingresos_recurrentes WHERE id = %s AND user_id = %s",
                    (ids[idx], USER_ID),
                )
                st.toast("✓ Eliminado.", icon="✅")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")


# ── Ingresos extras ───────────────────────────────────────────────────────────

def _tab_extras():
    st.caption("Dinero que recibes ocasionalmente: bonos, freelance, ventas, etc.")

    rows = execute_query(
        "SELECT * FROM ingresos_extras WHERE user_id = %s ORDER BY fecha_iso DESC",
        (USER_ID,),
    )

    if rows:
        df = pd.DataFrame(rows)
        df["fecha_fmt"] = pd.to_datetime(df["fecha_iso"]).dt.strftime("%d/%m/%Y")
        df["monto_fmt"] = df["monto"].apply(lambda x: f"S/ {float(x):,.2f}")
        st.dataframe(
            df[["id", "fecha_fmt", "concepto", "monto_fmt", "notas"]],
            column_config={
                "id":        st.column_config.NumberColumn("ID"),
                "fecha_fmt": st.column_config.TextColumn("Fecha"),
                "concepto":  st.column_config.TextColumn("Concepto"),
                "monto_fmt": st.column_config.TextColumn("Monto"),
                "notas":     st.column_config.TextColumn("Notas"),
            },
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No tienes ingresos extras registrados.")

    st.markdown("#### Agregar")
    with st.form("form_extra", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            fecha    = fecha_input_es("Fecha", default=date.today(), key="extra_fecha", max_year=date.today().year)
            concepto = st.text_input("Concepto *")
        with c2:
            monto = st.number_input("Monto (S/)", min_value=0.01, step=50.0, format="%.2f")
            notas = st.text_input("Notas")

        if st.form_submit_button("Agregar", type="primary"):
            if not concepto.strip():
                st.error("El concepto es obligatorio.")
            elif monto <= 0:
                st.error("El monto debe ser mayor a 0.")
            else:
                try:
                    execute_command(
                        """INSERT INTO ingresos_extras
                           (user_id, fecha_iso, concepto, monto, notas)
                           VALUES (%s, %s, %s, %s, %s)""",
                        (USER_ID, fecha.isoformat(), concepto.strip(), monto, notas or None),
                    )
                    st.toast("✓ Ingreso extra agregado.", icon="✅")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    if rows:
        st.markdown("#### Eliminar")
        ids       = [r["id"] for r in rows]
        etiquetas = [f"ID {r['id']} — {r['concepto']} ({r['fecha_iso']})" for r in rows]
        idx       = st.selectbox("Seleccionar", range(len(ids)),
                                 format_func=lambda i: etiquetas[i],
                                 key="del_idx_extra")
        if st.button("Eliminar seleccionado", key="btn_del_extra"):
            try:
                execute_command(
                    "DELETE FROM ingresos_extras WHERE id = %s AND user_id = %s",
                    (ids[idx], USER_ID),
                )
                st.toast("✓ Eliminado.", icon="✅")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")


render()
