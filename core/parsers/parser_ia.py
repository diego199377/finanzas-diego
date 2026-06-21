"""Parser IA con Claude Haiku 4.5 — clasifica en 4 tipos antes de guardar."""


def parse_ia(email_dict: dict, banco_detectado: str = "desconocido"):
    """
    Usa Claude Haiku 4.5 para clasificar correos bancarios y extraer datos.

    Clasifica en 4 tipos:
    - GASTO_REAL: consumos, retiros, pagos servicios, yape enviado, recargas, impuestos
    - INGRESO_REAL: depósitos, yape recibido, transferencias entrantes, sueldos, reversiones
    - NEUTRO: pago CC propia, transferencia entre cuentas propias (NO se guarda)
    - NO_TRANSACCION: alertas, login, estados de cuenta, marketing (NO se guarda)

    Retorna TransaccionDetectada solo para GASTO_REAL, None en todos los demás casos.
    """
    import json
    import os
    from datetime import date, datetime

    from .base import TransaccionDetectada

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    try:
        import anthropic
    except ImportError:
        return None

    # ── Extraer campos del correo ──────────────────────────────────────────────
    subject = ""
    fecha_header = ""
    body = ""

    if "payload" in email_dict:
        for h in email_dict.get("payload", {}).get("headers", []):
            name = h.get("name", "").lower()
            if name == "subject":
                subject = h.get("value", "")
            elif name == "date":
                fecha_header = h.get("value", "")
    else:
        subject = email_dict.get("subject", "")
        fecha_header = email_dict.get("date", "")

    body = email_dict.get("body", "")
    if not body and "payload" in email_dict:
        try:
            from core.gmail_client import extraer_texto_correo
            body = extraer_texto_correo(email_dict)
        except Exception:
            body = ""

    if len(body) > 3000:
        body = body[:3000] + "... [truncado]"

    # ── Prompt ─────────────────────────────────────────────────────────────────
    prompt = f"""Eres un experto en clasificar correos bancarios peruanos (BCP, BBVA, Yape, Interbank, Scotiabank).

Analiza el correo y clasifícalo en UNO de estos 4 tipos. Responde SOLO con JSON válido, sin markdown.

═══════════════════════════════════════════════════
TIPOS DE CLASIFICACIÓN
═══════════════════════════════════════════════════

1. "GASTO_REAL" — Sale dinero de tu patrimonio (es un gasto real)
   Ejemplos:
   - "Realizaste un consumo con tu Tarjeta de Crédito/Débito"
   - "Yape enviado" / "Realizaste un Yape" / "Yapeaste a..."
   - "Pago de Servicios" (Luz del Sur, Sedapal, Movistar, Claro, Netflix, Spotify)
   - "Retiro de Cajero Automático"
   - "Pago de Impuestos" / "SUNAT" / "ITF" / "Comisión"
   - "Recarga de Celular"
   - "Cargo Automático" (suscripciones)

2. "INGRESO_REAL" — Entra dinero a tu patrimonio (es un ingreso real)
   Ejemplos:
   - "Recibiste un depósito en tu cuenta"
   - "Te yapearon" / "Recibiste un Yape" / "Te depositaron"
   - "Transferencia recibida" / "Te realizaron una transferencia"
   - "Constancia de Abono" / "Reversión de Operación"
   - "Sueldo" / "Haber"

3. "NEUTRO" — Movimiento de dinero pero no cambia tu patrimonio neto (NO guardar)
   Ejemplos:
   - "Constancia de Pago de Tarjeta de Crédito Propia" (ya gastaste cuando consumiste)
   - "Constancia de Transferencia Entre mis Cuentas" (de cuenta tuya a otra cuenta tuya)
   - "Pago de Préstamo Propio" (pago de deuda, ya recibiste el préstamo antes)
   - "Refinanciamiento" / "Operación Crediticia Interna"
   - "Transferencia a Cuenta Propia"

4. "NO_TRANSACCION" — No es operación financiera, ignorar (NO guardar)
   Ejemplos:
   - Alertas de seguridad / login
   - Estados de cuenta mensuales
   - Marketing / promociones
   - Notificaciones de cambio de password
   - Boletines

═══════════════════════════════════════════════════
CASO AMBIGUO ESPECIAL
═══════════════════════════════════════════════════

"Constancia de Transferencia a Terceros" sin contexto claro:
   Por defecto clasificar como "GASTO_REAL" pero agregar "revisar_transferencia": true
   El usuario podrá editarlo después si era cambio de dólares con familia.

   EXCEPCIONES (decidir sin marcar):
   - Si menciona "SUNAT", "Banco de la Nación", "Tributos": GASTO_REAL definitivo
   - Si menciona "Pago de servicio" o empresa conocida: GASTO_REAL definitivo

═══════════════════════════════════════════════════
INFORMACIÓN DEL CORREO A ANALIZAR
═══════════════════════════════════════════════════

Banco detectado por remitente: {banco_detectado}

ASUNTO: {subject}

CUERPO:
{body}

FECHA HEADER (úsala si no encuentras fecha en el cuerpo): {fecha_header}

═══════════════════════════════════════════════════
FORMATO DE RESPUESTA (JSON estricto)
═══════════════════════════════════════════════════

Si tipo es NEUTRO o NO_TRANSACCION:
{{"clasificacion": "NEUTRO", "razon": "explicación breve"}}

Si tipo es GASTO_REAL o INGRESO_REAL:
{{
  "clasificacion": "GASTO_REAL",
  "monto": 45.50,
  "fecha": "2026-06-19",
  "establecimiento": "GIO S REST DELIVERY",
  "tipo_movimiento": "Debito",
  "ultimos_4": "5111",
  "categoria_sugerida": "Alimentación",
  "banco": "bcp",
  "revisar_transferencia": false,
  "subtipo": "consumo_tarjeta"
}}

Reglas:
- tipo_movimiento: "Credito" (tarjeta crédito), "Debito" (tarjeta débito/cuenta), "Yape", "Efectivo", "Transferencia"
- categoria_sugerida: "Alimentación", "Transporte", "Servicios fijos", "Ocio", "Salud", "Hogar", "Tecnología", "Financiero", "Yape personal", "Otros"
- ultimos_4: null si no aparece
- revisar_transferencia: true SOLO si es transferencia a terceros ambigua
- subtipo: descripción corta del tipo de operación

Responde SOLO el JSON, ninguna otra cosa."""

    # ── Llamada a la API ───────────────────────────────────────────────────────
    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        texto = response.content[0].text.strip()

        # Limpiar markdown si el modelo lo incluye
        if texto.startswith("```"):
            texto = texto.split("```")[1]
            if texto.startswith("json"):
                texto = texto[4:]
        data = json.loads(texto.strip())

    except json.JSONDecodeError as exc:
        print(f"[parser_ia] JSON inválido: {exc}")
        return None
    except Exception as exc:
        print(f"[parser_ia] Error API: {exc}")
        return None

    # ── Clasificar resultado ───────────────────────────────────────────────────
    clasificacion = data.get("clasificacion", "")

    # NEUTRO y NO_TRANSACCION: no guardar
    if clasificacion not in ("GASTO_REAL", "INGRESO_REAL"):
        return None

    # INGRESO_REAL: pendiente para sesión futura (tabla ingresos_extras)
    if clasificacion == "INGRESO_REAL":
        return None

    # ── Extraer y normalizar campos para GASTO_REAL ────────────────────────────
    try:
        monto = float(data["monto"])
    except (KeyError, ValueError, TypeError):
        return None

    try:
        fecha_obj = datetime.strptime(data["fecha"], "%Y-%m-%d").date()
    except Exception:
        fecha_obj = date.today()

    _tipo_map = {
        "credito": "Credito",       "Credito": "Credito",
        "debito": "Debito",         "Debito": "Debito",
        "yape": "Yape",             "Yape": "Yape",
        "efectivo": "Efectivo",     "Efectivo": "Efectivo",
        "transferencia": "Transferencia", "Transferencia": "Transferencia",
    }
    tipo_movimiento = _tipo_map.get(data.get("tipo_movimiento", ""), "Debito")

    establecimiento = str(data.get("establecimiento", "Desconocido")).strip()
    if data.get("revisar_transferencia", False):
        establecimiento = "[REVISAR] " + establecimiento

    return TransaccionDetectada(
        banco=data.get("banco", banco_detectado),
        monto=monto,
        fecha=fecha_obj,
        establecimiento=establecimiento,
        descripcion=establecimiento,
        tipo=tipo_movimiento,
        ultimos_4=data.get("ultimos_4"),
        categoria_sugerida=str(data.get("categoria_sugerida", "Otros")),
        confianza=0.85,
        raw_subject=subject,
        raw_body=body[:500],
        estado_gasto_inicial="por_clasificar" if data.get("revisar_transferencia", False) else "gasto",
    )
