"""Parser de correos Yape con regex."""

import re
from datetime import date
from email.utils import parsedate_to_datetime
from typing import Optional

from .base import TransaccionDetectada

# ── Patrones de monto ──────────────────────────────────────────────────────────
# "Realizaste un pago de S/ 50.00" / "te yapearon S/ 50.00" / "S/50.00"
_RE_MONTO_PAGO    = re.compile(r"pago\s+de\s+S/\s*([\d,]+\.\d{2})", re.IGNORECASE)
_RE_MONTO_YAPEADO = re.compile(r"yapea(?:ron|o)\s+S/\s*([\d,]+\.\d{2})", re.IGNORECASE)
_RE_MONTO_PAGARON = re.compile(r"pagaron\s+S/\s*([\d,]+\.\d{2})", re.IGNORECASE)
_RE_MONTO_GENERICO = re.compile(r"S/\s*([\d,]+\.\d{2})")

# ── Patrones de persona / establecimiento ──────────────────────────────────────
# "a Juan Pérez" / "de Juan Pérez"
_RE_PERSONA_A  = re.compile(r"\ba\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s]{2,40})(?:\r?\n|$|\.|,)", re.UNICODE)
_RE_PERSONA_DE = re.compile(r"\bde\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s]{2,40})(?:\r?\n|$|\.|,)", re.UNICODE)

# ── Tipo de operación ──────────────────────────────────────────────────────────
_RE_RECIBIDO = re.compile(r"yapea(?:ron|o)|te\s+pag(?:aron|o)|recib(?:iste|ió)", re.IGNORECASE)
_RE_ENVIADO  = re.compile(r"realizaste|enviaste|pagaste", re.IGNORECASE)


def _extraer_fecha(email_dict: dict) -> date:
    headers = {h["name"]: h["value"] for h in email_dict.get("payload", {}).get("headers", [])}
    date_str = headers.get("Date", "")
    try:
        return parsedate_to_datetime(date_str).date()
    except Exception:
        return date.today()


def _extraer_monto(texto: str) -> Optional[float]:
    for pattern in [_RE_MONTO_PAGO, _RE_MONTO_YAPEADO, _RE_MONTO_PAGARON, _RE_MONTO_GENERICO]:
        m = pattern.search(texto)
        if m:
            return float(m.group(1).replace(",", ""))
    return None


def _extraer_persona(texto: str) -> str:
    for pattern in [_RE_PERSONA_A, _RE_PERSONA_DE]:
        m = pattern.search(texto)
        if m:
            nombre = m.group(1).strip()
            # Excluir palabras genéricas que no son nombres
            if nombre.lower() not in {"través", "traves", "medio", "través de"}:
                return nombre
    return "Desconocido"


def _detectar_tipo(texto: str) -> str:
    if _RE_RECIBIDO.search(texto):
        return "yape"
    return "yape"


def parse_yape(email_dict: dict) -> Optional[TransaccionDetectada]:
    """
    Parsea un correo de Yape usando regex.
    Retorna TransaccionDetectada o None si no detecta monto.
    """
    from core.gmail_client import extraer_texto_correo

    headers = {h["name"]: h["value"] for h in email_dict.get("payload", {}).get("headers", [])}
    subject = headers.get("Subject", "")
    body = extraer_texto_correo(email_dict)
    texto = f"{subject}\n{body}"

    monto = _extraer_monto(texto)
    if not monto:
        return None

    persona = _extraer_persona(texto)

    return TransaccionDetectada(
        banco="yape",
        monto=monto,
        fecha=_extraer_fecha(email_dict),
        establecimiento=persona,
        descripcion=subject,
        tipo="yape",
        categoria_sugerida="Transferencia",
        raw_subject=subject,
        raw_body=body,
    )
