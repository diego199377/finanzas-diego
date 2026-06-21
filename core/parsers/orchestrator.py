"""Orquestador principal: detecta banco y decide qué parser usar."""

import os

from . import parser_bcp, parser_bbva, parser_yape, parser_ia


def detectar_banco(email_dict: dict) -> str:
    """Detecta el banco según el remitente (from header).

    Maneja tanto email_dict simplificado como estructura Gmail API (payload.headers).
    """
    sender = ""

    # Intentar campo simple "from"
    if isinstance(email_dict.get("from"), str):
        sender = email_dict["from"].lower()
    # Fallback: estructura Gmail API completa
    elif "payload" in email_dict:
        for h in email_dict.get("payload", {}).get("headers", []):
            if h.get("name", "").lower() == "from":
                sender = h.get("value", "").lower()
                break

    # Orden importa — Yape primero por si sus correos mencionan "bcp" en el asunto
    if "yape" in sender:
        return "yape"
    elif "bbva" in sender:
        return "bbva"
    elif "bcp" in sender or "viabcp" in sender or "notificacionesbcp" in sender:
        return "bcp"

    return "desconocido"


def parsear_correo(email_dict: dict):
    """
    Estrategia HÍBRIDA — IA primero para máxima cobertura, regex como respaldo rápido.

    Flujo:
    1. Detecta banco según remitente.
    2. Si ANTHROPIC_API_KEY configurada: intenta Claude Haiku primero.
       IA es robusta ante variaciones de formato y bancos desconocidos.
    3. Si IA falla o no hay API key: intenta regex específico del banco.
    4. Si todo falla: retorna None (correo marcado como "sin parsear").
    """
    banco = detectar_banco(email_dict)
    has_api_key = bool(os.getenv("ANTHROPIC_API_KEY"))

    # Sin banco detectado y sin IA: no hay nada que hacer
    if banco == "desconocido" and not has_api_key:
        return None

    # === Intento 1: Claude Haiku ===
    if has_api_key:
        try:
            resultado = parser_ia.parse_ia(email_dict, banco)
            if resultado:
                resultado.confianza = 0.85
                # Si la IA no pudo determinar el banco, usar el del remitente
                if resultado.banco == "desconocido" and banco != "desconocido":
                    resultado.banco = banco
                return resultado
        except Exception as exc:
            print(f"[orchestrator] IA falló, intentando regex: {exc}")

    # === Intento 2: Regex específico del banco ===
    resultado = None
    if banco == "bcp":
        resultado = parser_bcp.parse_bcp(email_dict)
    elif banco == "bbva":
        resultado = parser_bbva.parse_bbva(email_dict)
    elif banco == "yape":
        resultado = parser_yape.parse_yape(email_dict)

    if resultado:
        resultado.confianza = 0.95  # regex = patrón conocido, alta confianza
        return resultado

    return None
