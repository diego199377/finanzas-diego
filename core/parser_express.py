"""Parser de carga rápida: convierte texto libre (1 línea = 1 transacción) en dicts."""
import re

_TIPO_MAP = {
    "yape":          "Yape",
    "plin":          "Plin",
    "efectivo":      "Efectivo",
    "credito":       "Credito",
    "crédito":       "Credito",
    "debito":        "Debito",
    "débito":        "Debito",
    "transferencia": "Transferencia",
    "transf":        "Transferencia",
}

_BANCO_MAP = {
    "bcp":        "BCP",
    "bbva":       "BBVA",
    "interbank":  "Interbank",
    "scotiabank": "Scotiabank",
}

# keyword → (macro, sub)
_CATEGORIA_HINTS: dict[str, tuple[str, str]] = {
    # Alimentación
    "almuerzo":    ("Alimentación", "Restaurantes"),
    "desayuno":    ("Alimentación", "Restaurantes"),
    "cena":        ("Alimentación", "Restaurantes"),
    "restaurant":  ("Alimentación", "Restaurantes"),
    "restaurante": ("Alimentación", "Restaurantes"),
    "pollería":    ("Alimentación", "Restaurantes"),
    "polleria":    ("Alimentación", "Restaurantes"),
    "delivery":    ("Alimentación", "Delivery"),
    "rappi":       ("Alimentación", "Delivery"),
    "pedidos":     ("Alimentación", "Delivery"),
    "mercado":     ("Alimentación", "Mercado"),
    "supermercado":("Alimentación", "Mercado"),
    "super":       ("Alimentación", "Mercado"),
    "plaza vea":   ("Alimentación", "Mercado"),
    "tottus":      ("Alimentación", "Mercado"),
    "wong":        ("Alimentación", "Mercado"),
    "metro":       ("Alimentación", "Mercado"),
    "bodega":      ("Alimentación", "Bodega"),
    "cafe":        ("Alimentación", "Café"),
    "café":        ("Alimentación", "Café"),
    "coffee":      ("Alimentación", "Café"),
    "starbucks":   ("Alimentación", "Café"),
    # Transporte
    "grifo":       ("Transporte", "Combustible"),
    "combustible": ("Transporte", "Combustible"),
    "gasolina":    ("Transporte", "Combustible"),
    "petroleo":    ("Transporte", "Combustible"),
    "petróleo":    ("Transporte", "Combustible"),
    "uber":        ("Transporte", "Taxi/Uber"),
    "taxi":        ("Transporte", "Taxi/Uber"),
    "cabify":      ("Transporte", "Taxi/Uber"),
    "bus":         ("Transporte", "Público"),
    "combi":       ("Transporte", "Público"),
    "metropolitano":("Transporte","Público"),
    "peaje":       ("Transporte", "Peajes"),
    # Servicios fijos
    "internet":    ("Servicios fijos", "Internet"),
    "movistar":    ("Servicios fijos", "Internet"),
    "claro":       ("Servicios fijos", "Celular"),
    "entel":       ("Servicios fijos", "Celular"),
    "bitel":       ("Servicios fijos", "Celular"),
    "celular":     ("Servicios fijos", "Celular"),
    "netflix":     ("Servicios fijos", "Streaming"),
    "spotify":     ("Servicios fijos", "Streaming"),
    "disney":      ("Servicios fijos", "Streaming"),
    "hbo":         ("Servicios fijos", "Streaming"),
    "amazon prime":("Servicios fijos", "Streaming"),
    "luz":         ("Servicios fijos", "Luz"),
    "enel":        ("Servicios fijos", "Luz"),
    "agua":        ("Servicios fijos", "Agua"),
    "sedapal":     ("Servicios fijos", "Agua"),
    "gas":         ("Servicios fijos", "Gas"),
    # Salud
    "farmacia":    ("Salud", "Farmacia"),
    "botica":      ("Salud", "Farmacia"),
    "inkafarma":   ("Salud", "Farmacia"),
    "mifarma":     ("Salud", "Farmacia"),
    "doctor":      ("Salud", "Consultas"),
    "médico":      ("Salud", "Consultas"),
    "medico":      ("Salud", "Consultas"),
    "clinica":     ("Salud", "Consultas"),
    "clínica":     ("Salud", "Consultas"),
    "gimnasio":    ("Salud", "Gimnasio"),
    "gym":         ("Salud", "Gimnasio"),
    # Tecnología
    "github":      ("Tecnología", "Suscripciones"),
    "openai":      ("Tecnología", "Suscripciones"),
    "cursor":      ("Tecnología", "Suscripciones"),
    "adobe":       ("Tecnología", "Suscripciones"),
    "microsoft":   ("Tecnología", "Software"),
    "office":      ("Tecnología", "Software"),
    # Financiero
    "comision":    ("Financiero", "Comisiones"),
    "comisión":    ("Financiero", "Comisiones"),
    "interes":     ("Financiero", "Intereses"),
    "interés":     ("Financiero", "Intereses"),
}


def _sugerir_categoria(texto: str) -> tuple[str, str, str]:
    lower = texto.lower()
    # Buscar frases primero (más específicas)
    for keyword in sorted(_CATEGORIA_HINTS, key=len, reverse=True):
        if keyword in lower:
            macro, sub = _CATEGORIA_HINTS[keyword]
            return macro, sub, "alta"
    return "Otros", "", "baja"


def parsear_linea(linea: str) -> dict | None:
    linea = linea.strip()
    if not linea:
        return None

    # Monto: primer número con/sin decimales (acepta punto o coma)
    monto_match = re.search(r'\b(\d+(?:[.,]\d{1,2})?)\b', linea)
    if not monto_match:
        return None
    monto = round(float(monto_match.group(1).replace(",", ".")), 2)
    if monto <= 0:
        return None

    resto = linea[monto_match.end():].strip()

    # Tipo de movimiento
    tipo = "Efectivo"
    tipo_kw = None
    for kw, val in _TIPO_MAP.items():
        if re.search(r'\b' + re.escape(kw) + r'\b', resto, re.IGNORECASE):
            tipo = val
            tipo_kw = kw
            break
    if tipo_kw:
        resto = re.sub(r'\b' + re.escape(tipo_kw) + r'\b', '', resto, flags=re.IGNORECASE).strip()

    # Banco
    banco = None
    for kw, val in _BANCO_MAP.items():
        if re.search(r'\b' + re.escape(kw) + r'\b', resto, re.IGNORECASE):
            banco = val
            resto = re.sub(r'\b' + re.escape(kw) + r'\b', '', resto, flags=re.IGNORECASE).strip()
            break

    descripcion = re.sub(r'\s+', ' ', resto).strip()
    macro, sub, confianza = _sugerir_categoria(descripcion + " " + linea)

    return {
        "monto":          monto,
        "tipo_movimiento": tipo,
        "banco":          banco or "",
        "categoria_macro": macro,
        "categoria_sub":  sub,
        "descripcion":    descripcion,
        "confianza":      confianza,
        "linea_original": linea,
    }


def parsear_texto(texto: str) -> list[dict]:
    resultados = []
    for linea in texto.splitlines():
        r = parsear_linea(linea)
        if r:
            resultados.append(r)
    return resultados
