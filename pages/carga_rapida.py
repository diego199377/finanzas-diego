"""Página principal — carga rápida de transacciones en texto libre."""
import json
import streamlit as st
import pandas as pd
from datetime import date
from pathlib import Path

from core.db import execute_query, execute_command
from core.parser_express import parsear_texto

if "user" not in st.session_state:
    st.error("Debes iniciar sesión para acceder a esta página.")
    st.stop()
USER_ID = st.session_state.user["id"]

_CATEGORIAS_PATH = Path(__file__).parent.parent / "config" / "categorias.json"


def _get_metricas(user_id: int) -> tuple[float, float, float, str | None]:
    hoy        = date.today().isoformat()
    inicio_mes = date.today().replace(day=1).isoformat()

    rows = execute_query(
        """SELECT COALESCE(SUM(monto), 0) AS total FROM transacciones
           WHERE fecha_iso = %s AND user_id = %s AND estado_gasto = 'gasto'""",
        (hoy, user_id),
    )
    gastado_hoy = float(rows[0]["total"]) if rows else 0.0

    rows = execute_query(
        """SELECT COALESCE(SUM(monto), 0) AS total FROM transacciones
           WHERE fecha_iso >= %s AND user_id = %s AND estado_gasto = 'gasto'""",
        (inicio_mes, user_id),
    )
    gastado_mes = float(rows[0]["total"]) if rows else 0.0

    tarjetas = execute_query(
        """SELECT t.alias, t.linea_aprobada,
                  COALESCE(SUM(tr.monto), 0) AS gastado
           FROM tarjetas t
           LEFT JOIN transacciones tr
                  ON tr.tarjeta_alias = t.alias
                 AND tr.fecha_iso >= %s
                 AND tr.user_id = %s
                 AND tr.estado_gasto = 'gasto'
           WHERE t.tipo = 'Credito' AND t.activa = TRUE AND t.linea_aprobada > 0
             AND t.user_id = %s
           GROUP BY t.alias, t.linea_aprobada""",
        (inicio_mes, user_id, user_id),
    )

    pct_max, alias_max = 0.0, None
    for row in tarjetas:
        pct = float(row["gastado"]) / float(row["linea_aprobada"]) * 100
        if pct > pct_max:
            pct_max, alias_max = pct, row["alias"]

    return float(gastado_hoy), float(gastado_mes), pct_max, alias_max


def _get_umbral(user_id: int) -> float:
    rows = execute_query(
        "SELECT valor FROM config_usuario WHERE clave = 'alerta_corte_pct' AND user_id = %s",
        (user_id,),
    )
    return float(rows[0]["valor"]) if rows else 70.0


def _guardar_transacciones(df: pd.DataFrame, user_id: int):
    hoy   = date.today().isoformat()
    count = 0
    try:
        for _, row in df.iterrows():
            monto = row.get("Monto")
            if monto is None or pd.isna(monto) or float(monto) <= 0:
                continue
            execute_command(
                """INSERT INTO transacciones
                   (user_id, fecha_iso, monto, tipo_movimiento, banco,
                    categoria_macro, categoria_sub, descripcion, origen)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'express')""",
                (
                    user_id,
                    hoy,
                    round(float(monto), 2),
                    row.get("Tipo") or "Efectivo",
                    row.get("Banco") or None,
                    row.get("Categoría") or "Otros",
                    row.get("Sub") or None,
                    row.get("Descripción") or None,
                ),
            )
            count += 1
        st.toast(f"✓ {count} transacción(es) guardadas.", icon="✅")
        st.session_state.pop("cr_parsed_rows", None)
        st.session_state.pop("cr_show_preview", None)
        st.rerun()
    except Exception as e:
        st.error(f"Error al guardar: {e}")


def render():
    st.title("⚡ Carga Rápida")

    try:
        gastado_hoy, gastado_mes, pct_max, alias_max = _get_metricas(USER_ID)
        umbral = _get_umbral(USER_ID)
    except Exception as e:
        st.error(f"Error cargando métricas: {e}")
        return

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Gastado hoy", f"S/ {gastado_hoy:,.2f}")
    with col2:
        st.metric("Mes acumulado", f"S/ {gastado_mes:,.2f}")
    with col3:
        label     = f"% usado · {alias_max}" if alias_max else "% Tarjeta crédito"
        valor_str = f"{pct_max:.1f}%"
        if pct_max >= umbral:
            st.html(
                f'<div style="background:#fef3c7;border:1px solid #fbbf24;'
                f'border-radius:12px;padding:20px 24px;">'
                f'<div style="color:#92400e;font-size:0.78rem;font-weight:600;'
                f'text-transform:uppercase;letter-spacing:0.05em;">{label}</div>'
                f'<div style="color:#b45309;font-size:1.75rem;font-weight:700;">{valor_str} ⚠️</div>'
                f'</div>'
            )
        else:
            st.metric(label, valor_str)

    st.divider()

    texto = st.text_area(
        "Ingresa tus transacciones (1 por línea)",
        placeholder=(
            "Ej: 35 yape almuerzo\n"
            "120 efectivo grifo\n"
            "12.50 yape uber\n"
            "250 credito bcp supermercado\n"
            "45.90 debito bbva farmacia"
        ),
        height=180,
        key="cr_texto",
    )

    col_a, _ = st.columns([2, 5])
    with col_a:
        if st.button("Parsear y previsualizar", type="primary", use_container_width=True):
            if texto.strip():
                resultados = parsear_texto(texto)
                if not resultados:
                    st.warning("No se encontraron transacciones válidas en el texto ingresado.")
                else:
                    st.session_state["cr_parsed_rows"] = resultados
                    st.session_state["cr_show_preview"] = True
            else:
                st.warning("El campo de texto está vacío.")

    if st.session_state.get("cr_show_preview") and st.session_state.get("cr_parsed_rows"):
        st.markdown("### Vista previa — edita antes de confirmar")

        _cats = json.loads(_CATEGORIAS_PATH.read_text(encoding="utf-8"))

        df = pd.DataFrame(st.session_state["cr_parsed_rows"])
        df.insert(0, "Fecha", date.today().strftime("%d/%m/%Y"))

        cols_show = ["Fecha", "monto", "tipo_movimiento", "banco",
                     "categoria_macro", "categoria_sub", "descripcion", "confianza"]
        df_display = df[cols_show].copy()
        df_display.columns = ["Fecha", "Monto", "Tipo", "Banco",
                               "Categoría", "Sub", "Descripción", "Confianza"]

        edited = st.data_editor(
            df_display,
            use_container_width=True,
            num_rows="fixed",
            column_config={
                "Fecha":       st.column_config.TextColumn(disabled=True),
                "Monto":       st.column_config.NumberColumn(format="S/ %.2f", min_value=0.01),
                "Tipo":        st.column_config.SelectboxColumn(
                                   options=["Efectivo","Yape","Plin","Debito","Credito","Transferencia"]),
                "Banco":       st.column_config.TextColumn(),
                "Categoría":   st.column_config.SelectboxColumn(options=list(_cats.keys())),
                "Sub":         st.column_config.TextColumn(),
                "Descripción": st.column_config.TextColumn(),
                "Confianza":   st.column_config.TextColumn(disabled=True),
            },
            key="cr_editor",
        )

        col_b, _ = st.columns([2, 5])
        with col_b:
            if st.button("Confirmar y guardar", type="primary", use_container_width=True):
                _guardar_transacciones(edited, USER_ID)


render()
