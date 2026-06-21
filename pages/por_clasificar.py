"""Página para clasificar transferencias ambiguas como gasto o no gasto."""
import time
import streamlit as st

from core.db import execute_command, execute_query

if "user" not in st.session_state:
    st.error("Debes iniciar sesión.")
    st.stop()

USER_ID = st.session_state.user["id"]

st.title("🔍 Por Clasificar")
st.caption(
    "Transferencias ambiguas detectadas por la IA. "
    "Decide cuáles fueron un gasto real y cuáles no (cambios de dólares, devoluciones, etc.)."
)

pendientes = execute_query(
    """
    SELECT id, fecha_iso, monto, descripcion, banco, categoria_macro
    FROM transacciones
    WHERE user_id = %s AND estado_gasto = 'por_clasificar'
    ORDER BY fecha_iso DESC, monto DESC
    """,
    (USER_ID,),
)

if not pendientes:
    st.success("🎉 No hay transacciones por clasificar. ¡Todo en orden!")
    st.stop()

total_pendiente = sum(float(p["monto"]) for p in pendientes)

# ── Métricas de resumen ────────────────────────────────────────────────────────
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Pendientes", len(pendientes))
with col2:
    st.metric("Monto total", f"S/ {total_pendiente:,.2f}")
with col3:
    st.metric("Promedio", f"S/ {total_pendiente / len(pendientes):,.2f}")

st.markdown("---")
st.info(
    "💡 **Gasto** = pagaste a alguien por algo (servicio, producto, deuda).  \n"
    "**No es gasto** = cambio de dólares con familia, devolución que te hicieron, "
    "préstamo que diste y te regresaron."
)
st.markdown("---")

# ── Acciones masivas ───────────────────────────────────────────────────────────
col_m1, col_m2 = st.columns(2)
with col_m1:
    if st.button("✅ Marcar TODAS como Gasto", use_container_width=True):
        execute_command(
            "UPDATE transacciones SET estado_gasto = 'gasto' WHERE user_id = %s AND estado_gasto = 'por_clasificar'",
            (USER_ID,),
        )
        st.success("Todas marcadas como Gasto.")
        time.sleep(1)
        st.rerun()
with col_m2:
    if st.button("❌ Marcar TODAS como No Gasto", use_container_width=True):
        execute_command(
            "UPDATE transacciones SET estado_gasto = 'no_gasto' WHERE user_id = %s AND estado_gasto = 'por_clasificar'",
            (USER_ID,),
        )
        st.success("Todas marcadas como No Gasto.")
        time.sleep(1)
        st.rerun()

st.markdown("---")

# ── Lista individual ───────────────────────────────────────────────────────────
for p in pendientes:
    with st.container(border=True):
        col_info, col_g, col_ng = st.columns([4, 1, 1])

        with col_info:
            fecha_str = p["fecha_iso"].strftime("%d/%m/%Y")
            st.markdown(
                f"**{fecha_str}** · S/ {float(p['monto']):,.2f} · "
                f"{(p['banco'] or '').upper()}"
            )
            st.caption(str(p["descripcion"] or "")[:120])

        with col_g:
            if st.button("✅ Gasto", key=f"gasto_{p['id']}", use_container_width=True, type="primary"):
                execute_command(
                    "UPDATE transacciones SET estado_gasto = 'gasto' WHERE id = %s AND user_id = %s",
                    (p["id"], USER_ID),
                )
                st.rerun()

        with col_ng:
            if st.button("❌ No gasto", key=f"nogasto_{p['id']}", use_container_width=True):
                execute_command(
                    "UPDATE transacciones SET estado_gasto = 'no_gasto' WHERE id = %s AND user_id = %s",
                    (p["id"], USER_ID),
                )
                st.rerun()
