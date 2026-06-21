"""Validaciones compartidas para formularios y operaciones de BD."""
from datetime import date


def validar_monto(monto) -> str | None:
    try:
        m = float(monto)
    except (TypeError, ValueError):
        return "El monto debe ser un número válido."
    if m <= 0:
        return "El monto debe ser mayor a 0."
    return None


def validar_fecha(fecha_str: str) -> str | None:
    try:
        fecha = date.fromisoformat(fecha_str)
    except ValueError:
        return "Fecha inválida. Formato esperado: YYYY-MM-DD."
    if fecha > date.today():
        return "La fecha no puede ser futura."
    return None


def validar_categoria(macro: str) -> str | None:
    if not macro or not macro.strip():
        return "La categoría macro es obligatoria."
    return None
