"""Parser de correos BBVA con regex."""

import re
from datetime import date, datetime
from email.utils import parsedate_to_datetime
from typing import Optional

from .base import TransaccionDetectada

# ── Patrones de monto ──────────────────────────────────────────────────────────
_RE_MONTO_IMPORTE = re.compile(r"[Ii]mporte[:\s]+S/\s*([\d,]+\.\d{2})")
_RE_MONTO_MONTO   = re.compile(r"[Mm]onto[:\s]+S/\s*([\d,]+\.\d{2})")
_RE_MONTO_GENERICO = re.compile(r"S/\s*([\d,]+\.\d{2})")

# ── Patrones de establecimiento ────────────────────────────────────────────────
_RE_ESTAB_ESTABL  = re.compile(r"[Ee]stablecimiento[:\s]+(.+?)(?:\r?\n|$)")
_RE_ESTAB_COMERCIO = re.compile(r"[Cc]omercio[:\s]+(.+?)(?:\r?\n|$)")
_RE_ESTAB_EN      = re.compile(
    r"\ben\s+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúña-z0-9\s&'.,-]{2,50}?)(?:\r?\n|\*|Tarjeta|Fecha)",
    re.UNICODE,
)

# ── Patrones de tarjeta ────────────────────────────────────────────────────────
_RE_TARJETA_ASTERISCO = re.compile(r"\*{4,}\s*(\d{4})")
_RE_TARJETA_TERMINADA = re.compile(r"terminada\s+en\s+(\d{4})", re.IGNORECASE)

# ── Fecha dentro del correo (formato BBVA: DD/MM/YYYY) ────────────────────────
_RE_FECHA_BBVA = re.compile(r"(\d{2}/\d{2}/\d{4})")

# ── Tipo de movimiento ─────────────────────────────────────────────────────────
_RE_CREDITO = re.compile(r"cr[eé]dito", re.IGNORECASE)
_RE_DEBITO  = re.compile(r"d[eé]bito|compra|cargo", re.IGNORECASE)


def _extraer_fecha(email_dict: dict, texto: str) -> date:
    # Primero buscar fecha en el cuerpo (DD/MM/YYYY)
    m = _RE_FECHA_BBVA.search(texto)
    if m:
        try:
            return datetime.strptime(m.group(1), "%d/%m/%Y").date()
        except ValueError:
            pass
    # Fallback: fecha del header
    headers = {h["name"]: h["value"] for h in email_dict.get("payload", {}).get("headers", [])}
    date_str = headers.get("Date", "")
    try:
        return parsedate_to_datetime(date_str).date()
    except Exception:
        return date.today()


def _extraer_monto(texto: str) -> Optional[float]:
    for pattern in [_RE_MONTO_IMPORTE, _RE_MONTO_MONTO, _RE_MONTO_GENERICO]:
        m = pattern.search(texto)
        if m:
            return float(m.group(1).replace(",", ""))
    return None


def _extraer_establecimiento(texto: str) -> str:
    for pattern in [_RE_ESTAB_ESTABL, _RE_ESTAB_COMERCIO, _RE_ESTAB_EN]:
        m = pattern.search(texto)
        if m:
            return m.group(1).strip()
    return "Desconocido"


def _extraer_ultimos_4(texto: str) -> Optional[str]:
    for pattern in [_RE_TARJETA_ASTERISCO, _RE_TARJETA_TERMINADA]:
        m = pattern.search(texto)
        if m:
            return m.group(1)
    return None


def _detectar_tipo(texto: str) -> str:
    if _RE_CREDITO.search(texto):
        return "credito"
    if _RE_DEBITO.search(texto):
        return "debito"
    return "debito"


def parse_bbva(email_dict: dict) -> Optional[TransaccionDetectada]:
    """
    Parsea un correo del BBVA usando regex.
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

    return TransaccionDetectada(
        banco="bbva",
        monto=monto,
        fecha=_extraer_fecha(email_dict, texto),
        establecimiento=_extraer_establecimiento(texto),
        descripcion=subject,
        tipo=_detectar_tipo(texto),
        ultimos_4=_extraer_ultimos_4(texto),
        raw_subject=subject,
        raw_body=body,
    )
