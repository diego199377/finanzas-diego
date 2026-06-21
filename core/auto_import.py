"""Lógica de auto-importación de correos nuevos al entrar a la app."""
from datetime import date, datetime, timedelta
from typing import Optional, Tuple

from core.db import execute_query


def gmail_esta_conectado() -> bool:
    """Verifica si existe token.json (usuario completó OAuth alguna vez)."""
    from core.gmail_client import TOKEN_PATH
    return TOKEN_PATH.exists()


def get_ultima_fecha_correo_procesado(user_id: int) -> Optional[date]:
    """Retorna la fecha del correo más reciente ya procesado para este usuario."""
    result = execute_query(
        "SELECT MAX(fecha_correo) AS ultima FROM correos_procesados WHERE user_id = %s",
        (user_id,),
    )
    if not result or result[0]["ultima"] is None:
        return None
    ultima = result[0]["ultima"]
    # fecha_correo puede volver como datetime (TIMESTAMPTZ) o date
    if hasattr(ultima, "date") and callable(ultima.date):
        return ultima.date()
    return ultima


def contar_correos_nuevos(user_id: int) -> Tuple[int, Optional[date]]:
    """
    Cuenta correos bancarios en Gmail desde la última importación.
    Retorna (cantidad, fecha_desde) o (0, None) si no aplica.
    """
    if not gmail_esta_conectado():
        return 0, None

    ultima = get_ultima_fecha_correo_procesado(user_id)
    if ultima is None:
        # Sin historial previo: el usuario debe hacer la carga inicial manual
        return 0, None

    fecha_desde = ultima + timedelta(days=1)
    if fecha_desde > date.today():
        return 0, None

    from core.gmail_client import buscar_correos

    senders = [
        "from:notificaciones@notificacionesbcp.com.pe",
        "from:notificaciones@bcp.com.pe",
        "from:procesos@bbva.com.pe",
        "from:notificaciones@bbva.pe",
        "from:notificaciones@yape.pe",
    ]
    query = "(" + " OR ".join(senders) + ")"
    query += f" after:{fecha_desde.strftime('%Y/%m/%d')}"

    try:
        mensajes = buscar_correos(query, max_results=100)
        return len(mensajes), fecha_desde
    except Exception as e:
        print(f"[auto_import] Error buscando correos: {e}")
        return 0, None


def procesar_correos_nuevos_auto(user_id: int) -> dict:
    """
    Procesa correos nuevos automáticamente.
    - confianza > 0.90: auto-guarda en BD con batch insert.
    - confianza <= 0.90: guarda en session_state para revisión manual.

    Retorna dict con: auto_guardadas, pendientes_revision, ya_procesados, errores.
    """
    from psycopg2.extras import execute_values

    from core.db import get_connection
    from core.gmail_client import buscar_correos, get_correo, get_headers
    from core.parsers.orchestrator import parsear_correo

    ultima = get_ultima_fecha_correo_procesado(user_id)
    if ultima is None:
        return {
            "auto_guardadas": 0, "pendientes_revision": 0,
            "ya_procesados": 0, "errores": 0,
            "mensaje": "Sin historial previo; usa 'Importar de Gmail' primero.",
        }

    fecha_desde = ultima + timedelta(days=1)
    senders = [
        "from:notificaciones@notificacionesbcp.com.pe",
        "from:notificaciones@bcp.com.pe",
        "from:procesos@bbva.com.pe",
        "from:notificaciones@bbva.pe",
        "from:notificaciones@yape.pe",
    ]
    query = "(" + " OR ".join(senders) + f") after:{fecha_desde.strftime('%Y/%m/%d')}"

    try:
        mensajes = buscar_correos(query, max_results=100)
    except Exception as e:
        print(f"[auto_import] Error buscando correos: {e}")
        return {"auto_guardadas": 0, "pendientes_revision": 0, "ya_procesados": 0, "errores": 1}

    ya_rows = execute_query(
        "SELECT gmail_message_id FROM correos_procesados WHERE user_id = %s",
        (user_id,),
    )
    ids_ya = {r["gmail_message_id"] for r in ya_rows}

    auto_guardar = []   # confianza > 0.90
    pendientes   = []   # confianza <= 0.90
    ya_count     = 0
    errores      = 0

    for msg in mensajes:
        if msg["id"] in ids_ya:
            ya_count += 1
            continue
        try:
            correo    = get_correo(msg["id"])
            resultado = parsear_correo(correo)

            if resultado is None:
                continue

            hdrs   = get_headers(correo)
            asunto = hdrs.get("Subject", "")

            item = {
                "gmail_id":            msg["id"],
                "banco":               resultado.banco,
                "fecha":               resultado.fecha,
                "monto":               resultado.monto,
                "establecimiento":     resultado.establecimiento,
                "tipo":                resultado.tipo,
                "categoria":           resultado.categoria_sugerida or "Otros",
                "confianza":           resultado.confianza,
                "asunto":              asunto,
                "incluir":             True,  # requerido por el data_editor de importar_correos
                "estado_gasto_inicial": resultado.estado_gasto_inicial,
            }

            if resultado.confianza > 0.90:
                auto_guardar.append(item)
            else:
                pendientes.append(item)

        except Exception as e:
            print(f"[auto_import] Error procesando {msg['id']}: {e}")
            errores += 1

    # ── Batch insert de las transacciones de alta confianza ───────────────────
    auto_guardadas = 0
    if auto_guardar:
        batch_tx = [
            (
                user_id,
                t["fecha"],
                t["monto"],
                t["tipo"],
                t["banco"].upper(),
                t["categoria"],
                t["asunto"],        # descripcion
                t["establecimiento"],
                t.get("estado_gasto_inicial", "gasto"),
            )
            for t in auto_guardar
        ]
        try:
            with get_connection() as conn:
                cur = conn.cursor()

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
                    page_size=200,
                    fetch=True,
                )
                ids_list = [r[0] for r in inserted]

                batch_correos = [
                    (
                        user_id,
                        t["gmail_id"],
                        t["banco"],
                        t["fecha"],
                        t["asunto"],
                        ids_list[i],
                        t["monto"],
                        t["establecimiento"],
                        t["categoria"],
                        t["asunto"],
                    )
                    for i, t in enumerate(auto_guardar)
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
                        SET estado = 'confirmado',
                            transaccion_id = EXCLUDED.transaccion_id
                    """,
                    batch_correos,
                    template="(%s,%s,%s,%s,%s,%s,'confirmado',%s,%s,%s,%s)",
                    page_size=200,
                )

                conn.commit()
                cur.close()
                auto_guardadas = len(ids_list)

        except Exception as e:
            print(f"[auto_import] Error en batch insert: {e}")
            errores += len(auto_guardar)

    # ── Dejar pendientes en session_state para revisión manual ───────────────
    if pendientes:
        import streamlit as st
        st.session_state.transacciones_pendientes_revision = pendientes

    return {
        "auto_guardadas":     auto_guardadas,
        "pendientes_revision": len(pendientes),
        "ya_procesados":      ya_count,
        "errores":            errores,
    }
