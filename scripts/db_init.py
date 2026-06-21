"""Inicializa la base de datos SQLite con el schema completo y datos semilla."""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.db import get_connection, DB_PATH

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS tarjetas (
    alias           TEXT    PRIMARY KEY,
    banco           TEXT    NOT NULL,
    tipo            TEXT    NOT NULL CHECK(tipo IN ('Credito','Debito')),
    ultimos4        TEXT    CHECK(length(ultimos4) = 4),
    linea_aprobada  REAL,
    dia_corte       INTEGER CHECK(dia_corte BETWEEN 1 AND 31),
    dia_pago        INTEGER CHECK(dia_pago  BETWEEN 1 AND 31),
    activa          INTEGER NOT NULL DEFAULT 1 CHECK(activa IN (0,1)),
    color_hex       TEXT    DEFAULT '#2563eb'
);

CREATE TABLE IF NOT EXISTS transacciones (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha_iso       TEXT    NOT NULL,
    monto           REAL    NOT NULL CHECK(monto > 0),
    tipo_movimiento TEXT    NOT NULL CHECK(tipo_movimiento IN
                            ('Credito','Debito','Yape','Plin','Efectivo','Transferencia')),
    banco           TEXT,
    tarjeta_alias   TEXT    REFERENCES tarjetas(alias) ON DELETE SET NULL,
    categoria_macro TEXT    NOT NULL,
    categoria_sub   TEXT,
    descripcion     TEXT,
    establecimiento TEXT,
    tag             TEXT,
    origen          TEXT    NOT NULL DEFAULT 'manual'
                            CHECK(origen IN ('manual','correo','express')),
    notas           TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_transacciones_fecha     ON transacciones(fecha_iso);
CREATE INDEX IF NOT EXISTS idx_transacciones_categoria ON transacciones(categoria_macro);
CREATE INDEX IF NOT EXISTS idx_transacciones_tarjeta   ON transacciones(tarjeta_alias);
CREATE INDEX IF NOT EXISTS idx_transacciones_tipo      ON transacciones(tipo_movimiento);

CREATE TABLE IF NOT EXISTS ingresos_recurrentes (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    concepto     TEXT    NOT NULL,
    monto        REAL    NOT NULL CHECK(monto > 0),
    dia_mes      INTEGER NOT NULL CHECK(dia_mes BETWEEN 1 AND 31),
    activo       INTEGER NOT NULL DEFAULT 1 CHECK(activo IN (0,1)),
    fecha_inicio TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS ingresos_extras (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha_iso TEXT    NOT NULL,
    concepto  TEXT    NOT NULL,
    monto     REAL    NOT NULL CHECK(monto > 0),
    notas     TEXT
);

CREATE TABLE IF NOT EXISTS deudas (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    concepto           TEXT    NOT NULL,
    monto_total        REAL    NOT NULL CHECK(monto_total > 0),
    cuota_mensual      REAL    NOT NULL CHECK(cuota_mensual > 0),
    fecha_inicio       TEXT    NOT NULL,
    fecha_fin_estimada TEXT,
    cuotas_pagadas     INTEGER NOT NULL DEFAULT 0 CHECK(cuotas_pagadas >= 0),
    cuotas_totales     INTEGER NOT NULL CHECK(cuotas_totales > 0),
    tasa_anual         REAL    CHECK(tasa_anual >= 0),
    activa             INTEGER NOT NULL DEFAULT 1 CHECK(activa IN (0,1))
);

CREATE INDEX IF NOT EXISTS idx_deudas_activa ON deudas(activa);

CREATE TABLE IF NOT EXISTS config_global (
    clave       TEXT PRIMARY KEY,
    valor       TEXT NOT NULL,
    descripcion TEXT
);

CREATE TRIGGER IF NOT EXISTS trg_transacciones_updated
AFTER UPDATE ON transacciones
BEGIN
    UPDATE transacciones
    SET updated_at = datetime('now','localtime')
    WHERE id = NEW.id;
END;
"""

CONFIG_DEFAULTS = [
    ("alerta_corte_pct",        "70",  "% de línea usada que activa alerta en tarjeta de crédito"),
    ("alerta_corte_dias_antes", "10",  "Días antes del corte para mostrar alerta"),
]


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_connection() as conn:
        conn.executescript(SCHEMA_SQL)
        for clave, valor, desc in CONFIG_DEFAULTS:
            conn.execute(
                "INSERT OR IGNORE INTO config_global(clave, valor, descripcion) VALUES (?,?,?)",
                (clave, valor, desc),
            )
        conn.commit()
    print(f"✓ BD inicializada: {DB_PATH}")


def seed_tarjetas():
    config_path = Path(__file__).parent.parent / "config" / "tarjetas.json"
    tarjetas = json.loads(config_path.read_text(encoding="utf-8"))
    with get_connection() as conn:
        for t in tarjetas:
            conn.execute(
                """INSERT OR IGNORE INTO tarjetas
                   (alias, banco, tipo, ultimos4, linea_aprobada,
                    dia_corte, dia_pago, activa, color_hex)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    t["alias"], t["banco"], t["tipo"], t.get("ultimos4"),
                    t.get("linea_aprobada"), t.get("dia_corte"), t.get("dia_pago"),
                    t.get("activa", 1), t.get("color_hex", "#2563eb"),
                ),
            )
        conn.commit()
    print(f"✓ Tarjetas semilla cargadas ({len(tarjetas)})")


if __name__ == "__main__":
    init_db()
    seed_tarjetas()
    print("\n✓ Setup completo.")
    print("  Siguiente: streamlit run app.py")
