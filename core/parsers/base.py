from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class TransaccionDetectada:
    banco: str             # 'bcp', 'bbva', 'yape'
    monto: float
    fecha: date
    establecimiento: str
    descripcion: str
    tipo: str              # 'credito', 'debito', 'yape', 'efectivo'
    ultimos_4: Optional[str] = None       # ej: '1234'
    categoria_sugerida: Optional[str] = None
    confianza: float = 1.0                # 0.0 a 1.0
    raw_subject: str = ""
    raw_body: str = ""
    estado_gasto_inicial: str = "gasto"  # 'gasto' | 'no_gasto' | 'por_clasificar'
