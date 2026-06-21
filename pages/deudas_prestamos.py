"""Deudas y préstamos: pagos mensuales fijos y préstamos personales."""
import streamlit as st
from datetime import date

from core.db import execute_query, execute_command
from core.widgets import fecha_input_es

if "user" not in st.session_state:
    st.error("Debes iniciar sesión para acceder a esta página.")
    st.stop()
USER_ID = st.session_state.user["id"]

_TIPO_LABEL = {
    "credito_bancario": "Crédito bancario",
    "cuotas":           "Compra en cuotas",
    "gasto_fijo":       "Gasto fijo mensual",
}
_TIPO_COLOR = {
    "credito_bancario": "#dc2626",
    "cuotas":           "#d97706",
    "gasto_fijo":       "#2563eb",
}


def _fmt_fecha(d) -> str:
    if d is None:
        return "—"
    if hasattr(d, "strftime"):
        return d.strftime("%d/%m/%Y")
    return str(d)


def render():
    st.title("💸 Deudas y Préstamos")
    tab1, tab2, tab3 = st.tabs(["Pagos mensuales", "Yo debo", "Me deben"])
    with tab1:
        _tab_pagos_mensuales()
    with tab2:
        _tab_prestamos("yo_debo")
    with tab3:
        _tab_prestamos("me_deben")


# ── Pagos mensuales ───────────────────────────────────────────────────────────

def _registrar_cuota(pago_id: int, pagadas: int, totales: int, user_id: int):
    if pagadas >= totales:
        st.warning("Este pago ya tiene todas las cuotas registradas.")
        return
    try:
        execute_command(
            "UPDATE pagos_mensuales SET cuotas_pagadas = cuotas_pagadas + 1 WHERE id = %s AND user_id = %s",
            (pago_id, user_id),
        )
        st.toast(f"✓ Cuota {pagadas + 1}/{totales} registrada.", icon="✅")
        st.rerun()
    except Exception as e:
        st.error(f"Error: {e}")


def _desactivar_pago(pago_id: int, user_id: int):
    try:
        execute_command(
            "UPDATE pagos_mensuales SET activa = FALSE WHERE id = %s AND user_id = %s",
            (pago_id, user_id),
        )
        st.toast("✓ Pago desactivado.", icon="✅")
        st.rerun()
    except Exception as e:
        st.error(f"Error: {e}")


def _tab_pagos_mensuales():
    st.caption("Lo que pagas todos los meses: créditos bancarios, compras en cuotas, gastos fijos.")

    pagos = execute_query(
        """SELECT * FROM pagos_mensuales
           WHERE user_id = %s AND activa = TRUE
           ORDER BY tipo, concepto""",
        (USER_ID,),
    )

    if pagos:
        for p in pagos:
            tipo_label = _TIPO_LABEL.get(p["tipo"], p["tipo"])
            tipo_color = _TIPO_COLOR.get(p["tipo"], "#64748b")

            with st.expander(f"{p['concepto']}  —  S/ {float(p['monto_mensual']):,.2f}/mes"):
                st.html(
                    f'<span style="background:{tipo_color};color:white;padding:3px 12px;'
                    f'border-radius:12px;font-size:0.8rem;font-weight:600;">'
                    f'{tipo_label}</span><br/>'
                )

                c1, c2, c3 = st.columns(3)
                c1.metric("Cuota mensual", f"S/ {float(p['monto_mensual']):,.2f}")
                if p.get("dia_pago"):
                    c2.metric("Día de pago", f"Día {p['dia_pago']}")
                if p.get("monto_total"):
                    c3.metric("Monto total", f"S/ {float(p['monto_total']):,.2f}")

                if p.get("cuotas_totales"):
                    pagadas = p.get("cuotas_pagadas") or 0
                    totales = p["cuotas_totales"]
                    pct     = pagadas / totales if totales else 0
                    st.progress(
                        min(pct, 1.0),
                        f"Cuota {pagadas}/{totales} — {pct * 100:.0f}%",
                    )

                extra = []
                if p.get("tasa_anual"):
                    extra.append(f"TEA: {float(p['tasa_anual']):.2f}%")
                if p.get("fecha_fin_estimada"):
                    extra.append(f"Fin estimado: {_fmt_fecha(p['fecha_fin_estimada'])}")
                if extra:
                    st.caption("  ·  ".join(extra))

                col_a, col_b, _ = st.columns([1, 1, 4])
                with col_a:
                    if p.get("cuotas_totales"):
                        pag = p.get("cuotas_pagadas") or 0
                        if pag < p["cuotas_totales"]:
                            if st.button("✓ Cuota", key=f"cuota_{p['id']}"):
                                _registrar_cuota(p["id"], pag, p["cuotas_totales"], USER_ID)
                with col_b:
                    if st.button("Desactivar", key=f"deact_{p['id']}"):
                        _desactivar_pago(p["id"], USER_ID)
    else:
        st.info("No tienes pagos mensuales activos.")

    desactivados = execute_query(
        """SELECT * FROM pagos_mensuales
           WHERE user_id = %s AND activa = FALSE
           ORDER BY concepto""",
        (USER_ID,),
    )
    if desactivados:
        with st.expander(f"Desactivados ({len(desactivados)})"):
            for p in desactivados:
                st.markdown(
                    f"- **{p['concepto']}** — S/ {float(p['monto_mensual']):,.2f}/mes"
                    f"  ·  {_TIPO_LABEL.get(p['tipo'], p['tipo'])}"
                )

    st.divider()
    st.markdown("#### Agregar pago mensual")

    # Selectbox FUERA del formulario para poder renderizar campos condicionales
    tipo_add = st.selectbox(
        "Tipo de pago",
        options=["credito_bancario", "cuotas", "gasto_fijo"],
        format_func=lambda x: _TIPO_LABEL[x],
        key="pm_add_tipo",
    )

    # Checkbox opcional también fuera del form (se reactualiza sin submit)
    tiene_fecha_fin = False
    if tipo_add in ("credito_bancario", "cuotas"):
        tiene_fecha_fin = st.checkbox("¿Tiene fecha estimada de fin?", key="pm_check_fin")

    with st.form("form_pago_mensual", clear_on_submit=True):
        concepto = st.text_input(
            "Concepto *",
            placeholder="Ej: Crédito vehicular BCP, Laptop 12 cuotas, Seguro médico",
        )

        c1, c2 = st.columns(2)
        with c1:
            monto_mensual = st.number_input("Monto mensual (S/)", min_value=0.01, step=10.0, format="%.2f")
            dia_pago      = st.number_input("Día de pago", min_value=1, max_value=31, value=1)
            fecha_inicio = fecha_input_es("Fecha inicio", default=date.today(), key="pm_inicio")
        with c2:
            if tipo_add in ("credito_bancario", "cuotas"):
                monto_total    = st.number_input("Monto total (S/)", min_value=0.01, step=100.0, format="%.2f")
                cuotas_totales = st.number_input("Total de cuotas", min_value=1, step=1, value=12)
                if tiene_fecha_fin:
                    fecha_fin = fecha_input_es("Fecha fin estimada", key="pm_fin")
                else:
                    fecha_fin = None
            else:
                monto_total    = None
                cuotas_totales = None
                fecha_fin      = None

            if tipo_add == "credito_bancario":
                tasa_anual = st.number_input("TEA %", min_value=0.0, step=0.1, format="%.2f")
            else:
                tasa_anual = None

            activa = st.checkbox("Activa", value=True)

        if st.form_submit_button("Agregar pago mensual", type="primary"):
            if not concepto.strip():
                st.error("El concepto es obligatorio.")
            else:
                try:
                    execute_command(
                        """INSERT INTO pagos_mensuales
                           (user_id, concepto, tipo, monto_mensual, dia_pago,
                            monto_total, cuotas_totales, fecha_inicio,
                            fecha_fin_estimada, tasa_anual, activa)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        (
                            USER_ID,
                            concepto.strip(),
                            tipo_add,
                            monto_mensual,
                            dia_pago,
                            monto_total if tipo_add in ("credito_bancario", "cuotas") else None,
                            int(cuotas_totales) if cuotas_totales and tipo_add in ("credito_bancario", "cuotas") else None,
                            fecha_inicio.isoformat(),
                            fecha_fin.isoformat() if fecha_fin and tipo_add in ("credito_bancario", "cuotas") else None,
                            tasa_anual if tasa_anual and tipo_add == "credito_bancario" else None,
                            activa,
                        ),
                    )
                    st.toast("✓ Pago mensual agregado.", icon="✅")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar: {e}")


# ── Préstamos personales ──────────────────────────────────────────────────────

def _marcar_pagado(prestamo_id: int, user_id: int):
    try:
        execute_command(
            "UPDATE prestamos_personales SET estado = 'pagado' WHERE id = %s AND user_id = %s",
            (prestamo_id, user_id),
        )
        st.toast("✓ Marcado como pagado.", icon="✅")
        st.rerun()
    except Exception as e:
        st.error(f"Error: {e}")


def _tab_prestamos(direccion: str):
    if direccion == "yo_debo":
        st.caption("Plata que pediste prestada a familia o amigos (no a un banco).")
        label_persona = "¿A quién le debes? *"
        label_btn_add = "Registrar lo que debo"
        label_btn_pay = "Marcar como pagado"
        lbl_pend      = "Lo que debes"
        lbl_cerrados  = "Ya pagados"
    else:
        st.caption("Plata que prestaste y aún no te devuelven.")
        label_persona = "¿Quién te debe? *"
        label_btn_add = "Registrar lo que me deben"
        label_btn_pay = "Marcar como cobrado"
        lbl_pend      = "Lo que te deben"
        lbl_cerrados  = "Ya cobrados"

    pendientes = execute_query(
        """SELECT * FROM prestamos_personales
           WHERE user_id = %s AND direccion = %s AND estado = 'pendiente'
           ORDER BY fecha_esperada_pago NULLS LAST, fecha""",
        (USER_ID, direccion),
    )

    if pendientes:
        total = sum(float(p["monto"]) for p in pendientes)
        st.metric(lbl_pend, f"S/ {total:,.2f}")

        for p in pendientes:
            titulo = f"{p['persona']}  —  S/ {float(p['monto']):,.2f}"
            if p.get("fecha_esperada_pago"):
                titulo += f"  |  esperado: {_fmt_fecha(p['fecha_esperada_pago'])}"

            with st.expander(titulo):
                c1, c2 = st.columns(2)
                c1.metric("Monto", f"S/ {float(p['monto']):,.2f}")
                c2.metric("Fecha del préstamo", _fmt_fecha(p["fecha"]))
                if p.get("notas"):
                    st.caption(f"Notas: {p['notas']}")

                if st.button(label_btn_pay, key=f"pay_{p['id']}"):
                    _marcar_pagado(p["id"], USER_ID)
    else:
        st.info(f"No hay registros pendientes en '{lbl_pend}'.")

    cerrados = execute_query(
        """SELECT * FROM prestamos_personales
           WHERE user_id = %s AND direccion = %s AND estado = 'pagado'
           ORDER BY updated_at DESC""",
        (USER_ID, direccion),
    )
    if cerrados:
        with st.expander(f"{lbl_cerrados} ({len(cerrados)})"):
            for p in cerrados:
                st.markdown(
                    f"- **{p['persona']}** — S/ {float(p['monto']):,.2f}"
                    f"  (prestado {_fmt_fecha(p['fecha'])})"
                )

    st.divider()
    st.markdown(f"#### Agregar — {lbl_pend.lower()}")

    tiene_fecha_esp = st.checkbox("¿Hay fecha esperada de pago?", key=f"check_esp_{direccion}")

    with st.form(f"form_prestamo_{direccion}", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            persona = st.text_input(label_persona)
            monto   = st.number_input("Monto (S/)", min_value=0.01, step=10.0, format="%.2f")
        with c2:
            fecha = fecha_input_es("Fecha del préstamo", default=date.today(), key=f"prest_f_{direccion}")
            if tiene_fecha_esp:
                fecha_esp = fecha_input_es("Fecha esperada de pago", key=f"prest_esp_{direccion}")
            else:
                fecha_esp = None

        notas = st.text_area("Notas", height=68)

        if st.form_submit_button(label_btn_add, type="primary"):
            if not persona.strip():
                st.error("El nombre es obligatorio.")
            elif monto <= 0:
                st.error("El monto debe ser mayor a 0.")
            else:
                try:
                    execute_command(
                        """INSERT INTO prestamos_personales
                           (user_id, direccion, persona, monto, fecha,
                            fecha_esperada_pago, notas)
                           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                        (
                            USER_ID, direccion,
                            persona.strip(), monto,
                            fecha.isoformat(),
                            fecha_esp.isoformat() if fecha_esp else None,
                            notas.strip() or None,
                        ),
                    )
                    st.toast("✓ Registrado.", icon="✅")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar: {e}")


render()
