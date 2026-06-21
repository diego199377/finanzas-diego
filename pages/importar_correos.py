"""Importar transacciones automáticamente desde correos del banco."""
import json
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

from core.db import execute_command, execute_query, execute_returning
from core.gmail_client import (
    TOKEN_PATH,
    buscar_correos,
    get_correo,
    get_credentials,
    get_headers,
)
from core.parsers.orchestrator import parsear_correo
from core.widgets import fecha_input_es

# ── Constantes ─────────────────────────────────────────────────────────────────
# Mapeo del tipo retornado por el parser (minúsculas) al valor CHECK de la BD
_TIPO_MAP = {
    "credito": "Credito",
    "debito": "Debito",
    "yape": "Yape",
    "efectivo": "Efectivo",
    "transferencia": "Transferencia",
}
TIPOS_DB    = ["Credito", "Debito", "Yape", "Efectivo", "Transferencia"]
BANCO_LABEL = {"bcp": "BCP", "bbva": "BBVA", "yape": "Yape", "desconocido": "?"}

try:
    _cats_raw = json.loads(Path("config/categorias.json").read_text(encoding="utf-8"))
    CATEGORIAS = list(_cats_raw.keys())
except Exception:
    CATEGORIAS = ["Alimentación", "Transporte", "Servicios fijos", "Ocio", "Salud", "Otros"]

# ── Auth guard ─────────────────────────────────────────────────────────────────
if "user" not in st.session_state:
    st.error("Debes iniciar sesión para acceder a esta página.")
    st.stop()

USER_ID = st.session_state.user["id"]

# ── Estado de sesión ───────────────────────────────────────────────────────────
if "gmail_conectado" not in st.session_state:
    st.session_state.gmail_conectado = TOKEN_PATH.exists()
if "correos_detectados" not in st.session_state:
    st.session_state.correos_detectados = []

# ── Pendientes de auto-importación (confianza baja → revisión manual) ─────────
if st.session_state.get("transacciones_pendientes_revision"):
    pendientes = st.session_state.pop("transacciones_pendientes_revision")
    # Asegurarse de que cada item tenga las claves que espera el data_editor
    for p in pendientes:
        p.setdefault("incluir", True)
        p.setdefault("categoria", p.get("categoria_sugerida", "Otros"))
    st.session_state.correos_detectados = pendientes
    n = len(pendientes)
    st.warning(
        f"⚠️ **{n} transacción{'es' if n > 1 else ''}** detectada{'s' if n > 1 else ''} "
        f"con confianza baja — revisalas antes de guardar."
    )
    st.markdown("---")

# ── Header ──────────────────────────────────────────────────────────────────────
st.title("📧 Importar de Gmail")
st.caption(
    "Detecta automáticamente tus transacciones bancarias "
    "desde correos de BCP, BBVA y Yape."
)

# ════════════════════════════════════════════════════════════════
# PASO 1 — CONECTAR GMAIL
# ════════════════════════════════════════════════════════════════
if not st.session_state.gmail_conectado:
    st.markdown("### Paso 1 — Conectar tu cuenta de Gmail")
    st.info(
        "**¿Qué leemos?**  \n"
        "Solo correos de `notificaciones@bcp.com.pe`, `notificaciones@bbva.pe` "
        "y `no-reply@yape.com.pe`.  \n\n"
        "**¿Qué NO hacemos?**  \n"
        "No enviamos correos, no leemos otros mensajes ni accedemos a tus contactos."
    )

    if st.button("🔐 Conectar Gmail", use_container_width=True, type="primary"):
        with st.spinner("Esperando autorización en el navegador..."):
            try:
                get_credentials()
                st.session_state.gmail_conectado = True
                st.success("✅ Gmail conectado exitosamente.")
                time.sleep(0.8)
                st.rerun()
            except FileNotFoundError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(f"Error al conectar Gmail: {exc}")
                st.info(
                    "Asegúrate de que `credentials.json` esté en la raíz del proyecto "
                    "y que tu usuario esté en la lista de Test Users en Google Cloud Console."
                )
    st.stop()

# ── Banner de estado (visible cuando ya está conectado) ────────────────────────
col_ok, col_disc = st.columns([5, 1])
with col_ok:
    st.success("✅ Gmail conectado")
with col_disc:
    if st.button("Desconectar", use_container_width=True):
        TOKEN_PATH.unlink(missing_ok=True)
        st.session_state.gmail_conectado = False
        st.session_state.correos_detectados = []
        st.rerun()

st.divider()

# ════════════════════════════════════════════════════════════════
# PASO 2 — BUSCAR CORREOS
# ════════════════════════════════════════════════════════════════
st.markdown("### Buscar transacciones")

col_f, col_b = st.columns([3, 2])

with col_f:
    fecha_desde = fecha_input_es(
        "Importar desde",
        default=date.today() - timedelta(days=180),
        key="fecha_importar",
        min_year=2020,
        max_year=date.today().year,
    )

with col_b:
    st.caption("**Bancos a buscar:**")
    importar_bcp  = st.checkbox("BCP",  value=True, key="chk_bcp")
    importar_bbva = st.checkbox("BBVA", value=True, key="chk_bbva")
    importar_yape = st.checkbox("Yape", value=True, key="chk_yape")

if st.button("🔍 Buscar correos en Gmail", use_container_width=True, type="primary"):
    if not any([importar_bcp, importar_bbva, importar_yape]):
        st.error("Selecciona al menos un banco.")
    else:
        # Construir query de Gmail con remitentes reales (verificados por usuario)
        senders = []
        if importar_bcp:
            senders.append("from:notificaciones@notificacionesbcp.com.pe")
            # Cobertura adicional por si BCP usa subdominios distintos
            senders.append("from:notificaciones@bcp.com.pe")
            senders.append("from:notificaciones@viabcp.com")
        if importar_bbva:
            senders.append("from:procesos@bbva.com.pe")
            senders.append("from:notificaciones@bbva.pe")
        if importar_yape:
            senders.append("from:notificaciones@yape.pe")
            senders.append("from:no-reply@yape.com.pe")

        # after: embebido en el query — no pasar como parámetro separado
        query = "(" + " OR ".join(senders) + ")"
        query += f" after:{fecha_desde.strftime('%Y/%m/%d')}"

        _bar = st.progress(0, text="Buscando correos en Gmail...")
        _log = st.empty()

        try:
            mensajes = buscar_correos(query, max_results=500)
            total = len(mensajes)

            if total == 0:
                _bar.empty()
                st.warning(
                    "No se encontraron correos en ese rango. "
                    "Prueba con una fecha más antigua."
                )
                st.stop()

            _log.info(f"📬 {total} correo(s) encontrados. Procesando...")

            # Cargar IDs ya procesados para evitar duplicados en esta sesión
            ya_procesados = execute_query(
                "SELECT gmail_message_id FROM correos_procesados WHERE user_id = %s",
                (USER_ID,),
            )
            ids_ya_procesados = {r["gmail_message_id"] for r in ya_procesados}

            detectadas = []
            saltados   = 0
            sin_parsear = 0

            for i, msg in enumerate(mensajes):
                _bar.progress((i + 1) / total, text=f"Procesando {i + 1}/{total}...")

                if msg["id"] in ids_ya_procesados:
                    saltados += 1
                    continue

                try:
                    # get_correo devuelve el mensaje completo con payload/headers/parts
                    correo_full = get_correo(msg["id"])
                    resultado   = parsear_correo(correo_full)

                    if resultado:
                        hdrs = get_headers(correo_full)
                        cat  = resultado.categoria_sugerida
                        detectadas.append({
                            "gmail_id":            msg["id"],
                            "banco":               resultado.banco,
                            "fecha":               resultado.fecha,        # date object
                            "monto":               resultado.monto,        # float
                            "establecimiento":     resultado.establecimiento,
                            "tipo":                _TIPO_MAP.get(resultado.tipo, "Debito"),
                            "categoria":           cat if cat in CATEGORIAS else CATEGORIAS[0],
                            "confianza":           resultado.confianza,
                            "asunto":              hdrs.get("Subject", ""),
                            "incluir":             True,
                            "estado_gasto_inicial": resultado.estado_gasto_inicial,
                        })
                    else:
                        sin_parsear += 1

                except Exception:
                    sin_parsear += 1

            _bar.empty()
            _log.empty()
            st.session_state.correos_detectados = detectadas

            if detectadas:
                st.success(
                    f"✅ **{len(detectadas)}** transacciones detectadas  ·  "
                    f"{saltados} ya importadas (omitidas)  ·  "
                    f"{sin_parsear} sin parsear"
                )
            else:
                st.warning(
                    f"No se detectaron transacciones nuevas. "
                    f"{saltados} ya importadas, {sin_parsear} sin parsear."
                )

        except Exception as exc:
            _bar.empty()
            _log.empty()
            st.error(f"Error al buscar correos: {exc}")

# ════════════════════════════════════════════════════════════════
# PASO 3 — REVISAR Y CONFIRMAR
# ════════════════════════════════════════════════════════════════
if not st.session_state.correos_detectados:
    st.stop()

st.divider()
st.markdown("### Revisar y confirmar")
st.caption(
    "Marca las transacciones a guardar. "
    "Edita el establecimiento, tipo o categoría si lo necesitas antes de confirmar."
)

# Construir dataframe de visualización/edición
df_display = pd.DataFrame([
    {
        "incluir":         t["incluir"],
        "fecha":           t["fecha"].strftime("%d/%m/%Y"),
        "banco":           BANCO_LABEL.get(t["banco"], t["banco"].upper()),
        "monto":           f"S/ {t['monto']:,.2f}",
        "establecimiento": t["establecimiento"],
        "tipo":            t["tipo"],
        "categoria":       t["categoria"],
        "confianza":       f"{int(t['confianza'] * 100)}%",
    }
    for t in st.session_state.correos_detectados
])

edited_df = st.data_editor(
    df_display,
    use_container_width=True,
    hide_index=True,
    column_config={
        "incluir": st.column_config.CheckboxColumn(
            "✓", help="Marcar para guardar esta transacción", default=True
        ),
        "fecha":   st.column_config.TextColumn("Fecha",  disabled=True),
        "banco":   st.column_config.TextColumn("Banco",  disabled=True),
        "monto":   st.column_config.TextColumn("Monto",  disabled=True),
        "establecimiento": st.column_config.TextColumn("Establecimiento / Persona"),
        "tipo": st.column_config.SelectboxColumn(
            "Tipo", options=TIPOS_DB, required=True
        ),
        "categoria": st.column_config.SelectboxColumn(
            "Categoría", options=CATEGORIAS, required=True
        ),
        "confianza": st.column_config.TextColumn("Confianza", disabled=True),
    },
    key="editor_importar",
)

n_seleccionadas = int(edited_df["incluir"].sum())
st.info(
    f"📝 Vas a guardar **{n_seleccionadas}** "
    f"de **{len(edited_df)}** transacciones detectadas."
)

col_ok, col_cancel = st.columns(2)

with col_ok:
    if st.button(
        "✅ Confirmar y guardar",
        use_container_width=True,
        type="primary",
        disabled=(n_seleccionadas == 0),
    ):
        with st.spinner("Guardando transacciones..."):
            from psycopg2.extras import execute_values
            from core.db import get_connection

            originales = st.session_state.correos_detectados
            incluidas = []
            for idx, row in edited_df.iterrows():
                if row["incluir"]:
                    incluidas.append((originales[idx], row))

            guardadas = 0
            errores = 0

            if incluidas:
                batch_tx = [
                    (
                        USER_ID,
                        orig["fecha"],
                        orig["monto"],
                        row["tipo"],
                        orig["banco"].upper(),
                        row["categoria"],
                        orig["asunto"],
                        row["establecimiento"],
                        orig.get("estado_gasto_inicial", "gasto"),
                    )
                    for orig, row in incluidas
                ]

                try:
                    with get_connection() as conn:
                        cur = conn.cursor()

                        # Un solo INSERT para todas las transacciones
                        inserted = execute_values(
                            cur,
                            """
                            INSERT INTO transacciones
                                (user_id, fecha_iso, monto, tipo_movimiento, banco,
                                 categoria_macro, descripcion, establecimiento, origen,
                                 estado_gasto)
                            VALUES %s
                            RETURNING id
                            """,
                            batch_tx,
                            template="(%s,%s,%s,%s,%s,%s,%s,%s,'correo',%s)",
                            page_size=500,
                            fetch=True,
                        )
                        ids_list = [r[0] for r in inserted]

                        batch_correos = [
                            (
                                USER_ID,
                                orig["gmail_id"],
                                orig["banco"],
                                orig["fecha"],
                                orig["asunto"],
                                tx_id,
                                orig["monto"],
                                row["establecimiento"],
                                row["categoria"],
                                orig["asunto"],
                            )
                            for (orig, row), tx_id in zip(incluidas, ids_list)
                        ]

                        execute_values(
                            cur,
                            """
                            INSERT INTO correos_procesados
                                (user_id, gmail_message_id, banco, fecha_correo, asunto,
                                 transaccion_id, estado, monto_detectado,
                                 establecimiento_detectado, categoria_sugerida, raw_subject)
                            VALUES %s
                            ON CONFLICT (user_id, gmail_message_id) DO UPDATE
                                SET estado         = 'confirmado',
                                    transaccion_id = EXCLUDED.transaccion_id
                            """,
                            batch_correos,
                            template="(%s,%s,%s,%s,%s,%s,'confirmado',%s,%s,%s,%s)",
                            page_size=500,
                        )

                        conn.commit()
                        cur.close()
                        guardadas = len(ids_list)

                except Exception as exc:
                    errores = len(batch_tx)
                    guardadas = 0
                    st.error(f"Error en batch insert: {exc}")

        if guardadas:
            st.success(f"✅ {guardadas} transacciones guardadas.")
        if errores:
            st.error(f"❌ {errores} transacciones no se pudieron guardar.")

        st.session_state.correos_detectados = []
        time.sleep(1.5)
        st.rerun()

with col_cancel:
    if st.button("🗑️ Descartar todo", use_container_width=True):
        st.session_state.correos_detectados = []
        st.rerun()
