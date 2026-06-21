"""Tabla de transacciones con filtros y edición/eliminación inline."""
import json
import streamlit as st
import pandas as pd
from datetime import date, timedelta
from pathlib import Path

from dateutil.relativedelta import relativedelta

from core.db import execute_query, get_cursor
from core.widgets import fecha_input_es

if "user" not in st.session_state:
    st.error("Debes iniciar sesión para acceder a esta página.")
    st.stop()
USER_ID = st.session_state.user["id"]

_CATEGORIAS_PATH = Path(__file__).parent.parent / "config" / "categorias.json"

TIPOS_MOVIMIENTO = ["Efectivo", "Yape", "Plin", "Debito", "Credito", "Transferencia"]

OPCIONES_PERIODO = [
    "Este mes",
    "Mes anterior",
    "Últimos 30 días",
    "Últimos 3 meses",
    "Este año",
    "Todo el histórico",
    "Personalizado",
]

OPCIONES_TIPO_MOV = [
    "Todos",
    "Consumo",
    "Transferencia a terceros",
    "Transferencia entre cuentas",
    "Pago de servicios",
    "Yape",
    "Retiro de cajero",
    "Otros",
]


@st.cache_data
def _get_categorias() -> dict:
    return json.loads(_CATEGORIAS_PATH.read_text(encoding="utf-8"))


def _get_opciones_filtro(user_id: int) -> tuple[list[str], list[str]]:
    bancos = [r["banco"] for r in execute_query(
        "SELECT DISTINCT banco FROM transacciones WHERE banco IS NOT NULL AND user_id = %s ORDER BY banco",
        (user_id,),
    )]
    tipos = [r["tipo_movimiento"] for r in execute_query(
        "SELECT DISTINCT tipo_movimiento FROM transacciones WHERE user_id = %s ORDER BY tipo_movimiento",
        (user_id,),
    )]
    return bancos, tipos


def _guardar_cambios(df_original: pd.DataFrame, df_edited: pd.DataFrame, user_id: int):
    try:
        ids_original = set(df_original["id"].astype(int).tolist())
        ids_edited   = set(
            df_edited["id"].dropna().astype(int).tolist()
        ) if "id" in df_edited.columns else set()
        eliminados = ids_original - ids_edited

        with get_cursor() as cur:
            for del_id in eliminados:
                cur.execute(
                    "DELETE FROM transacciones WHERE id = %s AND user_id = %s",
                    (int(del_id), user_id),
                )
            for _, row in df_edited.iterrows():
                if "id" not in row or pd.isna(row["id"]):
                    continue
                cur.execute(
                    """UPDATE transacciones SET
                       monto = %s, tipo_movimiento = %s, banco = %s, tarjeta_alias = %s,
                       categoria_macro = %s, categoria_sub = %s, descripcion = %s,
                       establecimiento = %s, tag = %s, notas = %s
                       WHERE id = %s AND user_id = %s""",
                    (
                        row.get("monto"),
                        row.get("tipo_movimiento"),
                        row.get("banco") or None,
                        row.get("tarjeta_alias") or None,
                        row.get("categoria_macro"),
                        row.get("categoria_sub") or None,
                        row.get("descripcion") or None,
                        row.get("establecimiento") or None,
                        row.get("tag") or None,
                        row.get("notas") or None,
                        int(row["id"]),
                        user_id,
                    ),
                )

        st.toast(
            f"✓ {len(eliminados)} eliminada(s), {len(df_edited)} actualizada(s).",
            icon="✅",
        )
        st.rerun()
    except Exception as e:
        st.error(f"Error al guardar cambios: {e}")


def render():
    st.title("📋 Transacciones")

    categorias          = _get_categorias()
    bancos_db, tipos_db = _get_opciones_filtro(USER_ID)
    hoy                 = date.today()

    # ── Fila 1: Período + Tipo de movimiento ──────────────────────────────────
    col1, col2 = st.columns(2)
    with col1:
        periodo = st.selectbox("Período", OPCIONES_PERIODO, key="filtro_periodo")
    with col2:
        tipo_mov_filter = st.selectbox(
            "Tipo de movimiento", OPCIONES_TIPO_MOV, key="filtro_tipo_mov"
        )

    # ── Calcular rango de fechas ───────────────────────────────────────────────
    if periodo == "Este mes":
        fecha_inicio = hoy.replace(day=1)
        fecha_fin    = hoy
    elif periodo == "Mes anterior":
        fecha_fin    = hoy.replace(day=1) - timedelta(days=1)
        fecha_inicio = fecha_fin.replace(day=1)
    elif periodo == "Últimos 30 días":
        fecha_inicio = hoy - timedelta(days=30)
        fecha_fin    = hoy
    elif periodo == "Últimos 3 meses":
        fecha_inicio = hoy - relativedelta(months=3)
        fecha_fin    = hoy
    elif periodo == "Este año":
        fecha_inicio = date(hoy.year, 1, 1)
        fecha_fin    = hoy
    elif periodo == "Todo el histórico":
        fecha_inicio = date(2000, 1, 1)
        fecha_fin    = hoy
    else:  # Personalizado
        col_desde, col_hasta = st.columns(2)
        with col_desde:
            fecha_inicio = fecha_input_es(
                "Desde",
                default=hoy - timedelta(days=30),
                key="custom_desde",
                min_year=2020,
                max_year=hoy.year,
            )
        with col_hasta:
            fecha_fin = fecha_input_es(
                "Hasta",
                default=hoy,
                key="custom_hasta",
                min_year=2020,
                max_year=hoy.year,
            )
        if fecha_inicio > fecha_fin:
            st.error("La fecha 'Desde' no puede ser mayor que 'Hasta'.")
            st.stop()

    # ── Fila 2: Banco + Tipo + Categoría ──────────────────────────────────────
    col3, col4, col5 = st.columns(3)
    with col3:
        banco_sel = st.selectbox("Banco", ["Todos"] + bancos_db)
    with col4:
        tipo_sel = st.selectbox("Tipo", ["Todos"] + tipos_db)
    with col5:
        cat_sel = st.selectbox("Categoría", ["Todas"] + list(categorias.keys()))

    # ── Construir WHERE dinámico ───────────────────────────────────────────────
    where  = ["user_id = %s", "fecha_iso BETWEEN %s AND %s"]
    params = [USER_ID, fecha_inicio, fecha_fin]

    # Alias para no repetir LOWER(COALESCE(...)) en cada rama
    _d = "LOWER(COALESCE(descripcion, ''))"

    if tipo_mov_filter == "Consumo":
        where.append(f"{_d} LIKE %s")
        params.append("%consumo%")
    elif tipo_mov_filter == "Transferencia a terceros":
        where.append(f"{_d} LIKE %s")
        params.append("%transferencia a terceros%")
    elif tipo_mov_filter == "Transferencia entre cuentas":
        where.append(f"{_d} LIKE %s")
        params.append("%entre mis cuentas%")
    elif tipo_mov_filter == "Pago de servicios":
        where.append(f"({_d} LIKE %s AND {_d} NOT LIKE %s)")
        params.extend(["%pago de%", "%tarjeta de cr%"])
    elif tipo_mov_filter == "Yape":
        where.append(f"({_d} LIKE %s OR tipo_movimiento = %s)")
        params.extend(["%yape%", "Yape"])
    elif tipo_mov_filter == "Retiro de cajero":
        where.append(f"({_d} LIKE %s OR {_d} LIKE %s)")
        params.extend(["%retiro%", "%cajero%"])
    elif tipo_mov_filter == "Otros":
        # Todo lo que no encaja en ninguna categoría semántica conocida
        where.append(
            f"({_d} NOT LIKE %s"
            f" AND {_d} NOT LIKE %s"
            f" AND {_d} NOT LIKE %s"
            f" AND {_d} NOT LIKE %s"
            f" AND tipo_movimiento != %s"
            f" AND {_d} NOT LIKE %s"
            f" AND {_d} NOT LIKE %s"
            f" AND NOT ({_d} LIKE %s AND {_d} NOT LIKE %s))"
        )
        params.extend([
            "%consumo%",
            "%transferencia a terceros%",
            "%entre mis cuentas%",
            "%yape%",
            "Yape",
            "%retiro%",
            "%cajero%",
            "%pago de%",
            "%tarjeta de cr%",
        ])

    if banco_sel != "Todos":
        where.append("banco = %s")
        params.append(banco_sel)
    if tipo_sel != "Todos":
        where.append("tipo_movimiento = %s")
        params.append(tipo_sel)
    if cat_sel != "Todas":
        where.append("categoria_macro = %s")
        params.append(cat_sel)

    sql = (
        f"SELECT id, fecha_iso, monto, tipo_movimiento, banco, tarjeta_alias, "
        f"categoria_macro, categoria_sub, descripcion, establecimiento, "
        f"tag, origen, notas, estado_gasto "
        f"FROM transacciones WHERE {' AND '.join(where)} "
        "ORDER BY fecha_iso DESC, id DESC"
    )

    try:
        rows = execute_query(sql, params)
        df   = pd.DataFrame(rows) if rows else pd.DataFrame()
    except Exception as e:
        st.error(f"Error al cargar transacciones: {e}")
        return

    if not df.empty:
        df["monto"] = pd.to_numeric(df["monto"], errors="coerce")

    if df.empty:
        st.info("No hay transacciones con los filtros seleccionados.")
        return

    # ── Métricas de resumen ────────────────────────────────────────────────────
    suma_gastos   = float(df.loc[df["estado_gasto"] == "gasto",          "monto"].sum())
    cnt_pendiente = int((df["estado_gasto"] == "por_clasificar").sum())
    cnt_no_gasto  = int((df["estado_gasto"] == "no_gasto").sum())

    st.caption(f"📅 {fecha_inicio.strftime('%d/%m/%Y')} → {fecha_fin.strftime('%d/%m/%Y')}")
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Total filas", len(df))
    with m2:
        st.metric("✅ Gastos reales", f"S/ {suma_gastos:,.2f}", help="Solo estos cuentan en totales")
    with m3:
        st.metric("🔍 Por clasificar", cnt_pendiente, help="Visita 'Por Clasificar' para decidir")
    with m4:
        st.metric("❌ No gastos", cnt_no_gasto, help="No cuentan en totales")

    df["fecha"] = pd.to_datetime(df["fecha_iso"]).dt.strftime("%d/%m/%Y")
    df["estado_visual"] = df["estado_gasto"].map(
        {"gasto": "✅", "no_gasto": "❌", "por_clasificar": "🔍"}
    )

    cols_order = [
        "id", "estado_visual", "fecha", "monto", "tipo_movimiento", "banco", "tarjeta_alias",
        "categoria_macro", "categoria_sub", "descripcion", "establecimiento",
        "tag", "origen", "notas",
    ]
    cols_present = [c for c in cols_order if c in df.columns]

    edited = st.data_editor(
        df[cols_present],
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "id":              st.column_config.NumberColumn("ID",           disabled=True),
            "estado_visual":   st.column_config.TextColumn("",               disabled=True, width="small"),
            "fecha":           st.column_config.TextColumn("Fecha",          disabled=True),
            "monto":           st.column_config.NumberColumn("Monto",        format="S/ %.2f", min_value=0.01),
            "tipo_movimiento": st.column_config.SelectboxColumn("Tipo",      options=TIPOS_MOVIMIENTO),
            "banco":           st.column_config.TextColumn("Banco"),
            "tarjeta_alias":   st.column_config.TextColumn("Tarjeta"),
            "categoria_macro": st.column_config.SelectboxColumn("Categoría", options=list(categorias.keys())),
            "categoria_sub":   st.column_config.TextColumn("Sub-cat."),
            "descripcion":     st.column_config.TextColumn("Descripción"),
            "establecimiento": st.column_config.TextColumn("Establecimiento"),
            "tag":             st.column_config.TextColumn("Tag"),
            "origen":          st.column_config.TextColumn("Origen",         disabled=True),
            "notas":           st.column_config.TextColumn("Notas"),
        },
        hide_index=True,
        key="editor_transacciones",
    )

    col_a, _ = st.columns([2, 5])
    with col_a:
        if st.button("Guardar cambios", type="primary", use_container_width=True):
            _guardar_cambios(df[cols_present], edited, USER_ID)


render()
