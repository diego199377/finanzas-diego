"""Widgets custom reutilizables para la app."""
from datetime import date
from typing import Optional

import streamlit as st

MESES_ES = [
    "Enero", "Febrero", "Marzo", "Abril",
    "Mayo", "Junio", "Julio", "Agosto",
    "Septiembre", "Octubre", "Noviembre", "Diciembre",
]


def fecha_input_es(
    label: str,
    default: Optional[date] = None,
    key: Optional[str] = None,
    min_year: int = 2020,
    max_year: int = 2030,
    help_text: Optional[str] = None,
) -> date:
    """
    Date picker en español usando 3 selectboxes (Día / Mes / Año).

    Funciona en cualquier navegador sin depender del idioma del cliente.
    Diseñado para usuarios no-técnicos.

    Args:
        label:    Etiqueta que se muestra arriba (ej. "Fecha del préstamo")
        default:  Fecha por defecto. Si es None, usa hoy.
        key:      Sufijo único para las keys de los selectboxes.
                  Obligatorio cuando hay varios fecha_input_es en la misma página.
        min_year: Año mínimo seleccionable
        max_year: Año máximo seleccionable
        help_text: Tooltip opcional que aparece junto al label

    Returns:
        date object con la fecha seleccionada
    """
    if default is None:
        default = date.today()

    año_default = max(min_year, min(max_year, default.year))

    if help_text:
        st.caption(f"**{label}** — {help_text}")
    else:
        st.caption(f"**{label}**")

    col1, col2, col3 = st.columns([1, 2, 1.3])

    with col1:
        dia = st.selectbox(
            "Día",
            options=list(range(1, 32)),
            index=default.day - 1,
            key=f"fecha_dia_{key}" if key else None,
            label_visibility="collapsed",
        )

    with col2:
        mes = st.selectbox(
            "Mes",
            options=MESES_ES,
            index=default.month - 1,
            key=f"fecha_mes_{key}" if key else None,
            label_visibility="collapsed",
        )

    with col3:
        años = list(range(min_year, max_year + 1))
        año = st.selectbox(
            "Año",
            options=años,
            index=años.index(año_default),
            key=f"fecha_año_{key}" if key else None,
            label_visibility="collapsed",
        )

    mes_num = MESES_ES.index(mes) + 1
    try:
        return date(año, mes_num, dia)
    except ValueError:
        # Día inválido para el mes (ej. 31 de febrero) → retroceder al último día válido
        for d in range(dia - 1, 0, -1):
            try:
                return date(año, mes_num, d)
            except ValueError:
                continue
        return date(año, mes_num, 1)
