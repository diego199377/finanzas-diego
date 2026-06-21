"""Página de gestión de tarjetas — grid de cards + formulario de alta."""
import streamlit as st
from datetime import date

from core.db import execute_query, execute_command

if "user" not in st.session_state:
    st.error("Debes iniciar sesión para acceder a esta página.")
    st.stop()
USER_ID = st.session_state.user["id"]

BANCOS = ["BCP", "BBVA", "Interbank", "Scotiabank", "Otro"]


def _get_gastos_mes_por_tarjeta() -> dict[str, float]:
    inicio_mes = date.today().replace(day=1).isoformat()
    rows = execute_query(
        """SELECT tarjeta_alias, COALESCE(SUM(monto), 0) AS total
           FROM transacciones
           WHERE tarjeta_alias IS NOT NULL AND fecha_iso >= %s AND user_id = %s
           GROUP BY tarjeta_alias""",
        (inicio_mes, USER_ID),
    )
    return {r["tarjeta_alias"]: float(r["total"]) for r in rows}


def _render_card(t: dict, gasto: float):
    color = t.get("color_hex", "#2563eb")
    linea = float(t["linea_aprobada"]) if t.get("linea_aprobada") else None

    pct_html = ""
    if linea and linea > 0:
        pct = gasto / linea * 100
        bar_color = "#fbbf24" if pct >= 70 else "#ffffff55"
        pct_html = (
            f'<div style="margin-top:12px;">'
            f'<div style="display:flex;justify-content:space-between;'
            f'font-size:0.8rem;opacity:0.9;margin-bottom:4px;">'
            f'<span>{pct:.1f}% usado</span><span>S/ {linea:,.0f}</span>'
            f'</div>'
            f'<div style="background:#ffffff33;border-radius:4px;height:6px;">'
            f'<div style="background:{bar_color};border-radius:4px;'
            f'height:6px;width:{min(pct, 100):.1f}%;"></div>'
            f'</div></div>'
        )

    corte = f"Corte: día <b>{t['dia_corte']}</b>" if t.get("dia_corte") else ""
    pago  = f"&nbsp;·&nbsp;Pago: día <b>{t['dia_pago']}</b>" if t.get("dia_pago") else ""

    st.html(
        f'<div style="background:linear-gradient(135deg,{color} 0%,{color}bb 100%);'
        f'border-radius:16px;padding:24px;color:white;margin-bottom:16px;'
        f'box-shadow:0 4px 20px rgba(0,0,0,0.18);">'
        f'<div style="font-size:1.1rem;font-weight:700;letter-spacing:0.01em;">'
        f'{t["alias"]}</div>'
        f'<div style="opacity:0.8;font-size:0.82rem;margin-top:2px;">'
        f'{t["banco"]} · {t["tipo"]} · ····{t.get("ultimos4", "????")}</div>'
        f'<div style="margin-top:14px;font-size:1.6rem;font-weight:700;">'
        f'S/ {gasto:,.2f}</div>'
        f'<div style="opacity:0.75;font-size:0.78rem;">gastado este mes</div>'
        f'{pct_html}'
        f'<div style="margin-top:10px;font-size:0.78rem;opacity:0.8;">'
        f'{corte}{pago}</div>'
        f'</div>'
    )


def render():
    st.title("💳 Tarjetas")

    tarjetas = execute_query(
        "SELECT * FROM tarjetas WHERE activa = TRUE AND user_id = %s ORDER BY banco, alias",
        (USER_ID,),
    )

    if tarjetas:
        gastos = _get_gastos_mes_por_tarjeta()
        cols = st.columns(min(len(tarjetas), 3))
        for i, t in enumerate(tarjetas):
            with cols[i % 3]:
                _render_card(t, gastos.get(t["alias"], 0.0))
    else:
        st.info("No hay tarjetas activas registradas. Agrega una abajo.")

    st.divider()
    st.subheader("Agregar tarjeta")

    with st.form("form_tarjeta", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            alias     = st.text_input("Alias *  (ej: BCP Crédito)")
            banco     = st.selectbox("Banco", BANCOS)
            tipo      = st.selectbox("Tipo", ["Credito", "Debito"])
        with c2:
            ultimos4  = st.text_input("Últimos 4 dígitos", max_chars=4)
            linea     = st.number_input("Línea aprobada (S/)", min_value=0.0,
                                         step=500.0, format="%.2f",
                                         help="Dejar en 0 si es débito o sin límite definido")
            color_hex = st.color_picker("Color de la card", value="#2563eb")
        with c3:
            dia_corte = st.number_input("Día de corte", min_value=1, max_value=31, value=15)
            dia_pago  = st.number_input("Día de pago",  min_value=1, max_value=31, value=5)
            activa    = st.checkbox("Activa", value=True)

        if st.form_submit_button("Agregar tarjeta", type="primary"):
            if not alias.strip():
                st.error("El alias es obligatorio.")
            elif ultimos4 and len(ultimos4) != 4:
                st.error("Los últimos 4 dígitos deben ser exactamente 4 caracteres.")
            else:
                try:
                    execute_command(
                        """INSERT INTO tarjetas
                           (user_id, alias, banco, tipo, ultimos4, linea_aprobada,
                            dia_corte, dia_pago, activa, color_hex)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        (
                            USER_ID,
                            alias.strip(), banco, tipo,
                            ultimos4 if ultimos4 else None,
                            linea if linea > 0 else None,
                            dia_corte, dia_pago, activa, color_hex,
                        ),
                    )
                    st.success(f"✓ Tarjeta '{alias}' agregada.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar: {e}")

    if tarjetas:
        st.divider()
        st.subheader("Desactivar tarjeta")
        alias_sel = st.selectbox("Tarjeta a desactivar", [t["alias"] for t in tarjetas])
        if st.button("Desactivar", type="primary"):
            try:
                execute_command(
                    "UPDATE tarjetas SET activa = FALSE WHERE alias = %s AND user_id = %s",
                    (alias_sel, USER_ID),
                )
                st.success(f"✓ Tarjeta '{alias_sel}' desactivada.")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")


render()
