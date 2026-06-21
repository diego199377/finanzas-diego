"""
Migración v2 — Refactor de deudas.

Reemplaza la tabla 'deudas' (vacía) por dos tablas más expresivas:
  - pagos_mensuales     : créditos bancarios, compras en cuotas, gastos fijos
  - prestamos_personales: préstamos entre personas (yo debo / me deben)

Idempotente: usa IF NOT EXISTS y CREATE OR REPLACE TRIGGER.
Todo en una sola transacción: ROLLBACK automático si algo falla.

Ejecutar:
    python scripts/migrate_v2.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg2
from core.config import DATABASE_URL

SQL_PASOS = [

    # ── Eliminar tabla anterior (vacía, sin datos que preservar) ───────────────
    (
        "DROP TABLE deudas",
        "DROP TABLE IF EXISTS deudas CASCADE;",
    ),

    # ── Tabla: pagos_mensuales ─────────────────────────────────────────────────
    # Cubre tres casos de uso con un solo tipo de registro:
    #   credito_bancario : préstamo bancario con cuotas y TEA
    #   cuotas           : compra fraccionada sin tasa explícita
    #   gasto_fijo       : servicio mensual sin fecha de término
    (
        "tabla pagos_mensuales",
        """
        CREATE TABLE IF NOT EXISTS pagos_mensuales (
            id                 BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            user_id            BIGINT  NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            concepto           TEXT    NOT NULL,
            tipo               TEXT    NOT NULL
                                   CHECK(tipo IN ('credito_bancario', 'cuotas', 'gasto_fijo')),
            monto_mensual      NUMERIC(12,2) NOT NULL CHECK(monto_mensual > 0),
            dia_pago           INTEGER CHECK(dia_pago BETWEEN 1 AND 31),
            monto_total        NUMERIC(12,2) CHECK(monto_total > 0),
            cuotas_pagadas     INTEGER DEFAULT 0 CHECK(cuotas_pagadas >= 0),
            cuotas_totales     INTEGER CHECK(cuotas_totales > 0),
            fecha_inicio       DATE    NOT NULL,
            fecha_fin_estimada DATE,
            tasa_anual         NUMERIC(5,2) CHECK(tasa_anual >= 0),
            activa             BOOLEAN NOT NULL DEFAULT TRUE,
            created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """,
    ),

    # ── Tabla: prestamos_personales ────────────────────────────────────────────
    # Registra plata prestada entre personas (no bancos).
    # direccion: 'yo_debo' (me prestaron) | 'me_deben' (yo presté)
    (
        "tabla prestamos_personales",
        """
        CREATE TABLE IF NOT EXISTS prestamos_personales (
            id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            user_id             BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            direccion           TEXT   NOT NULL CHECK(direccion IN ('yo_debo', 'me_deben')),
            persona             TEXT   NOT NULL,
            monto               NUMERIC(12,2) NOT NULL CHECK(monto > 0),
            fecha               DATE   NOT NULL,
            fecha_esperada_pago DATE,
            estado              TEXT   NOT NULL DEFAULT 'pendiente'
                                    CHECK(estado IN ('pendiente', 'pagado')),
            notas               TEXT,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """,
    ),

    # ── Índices ────────────────────────────────────────────────────────────────
    (
        "indice idx_pagos_mensuales_user",
        "CREATE INDEX IF NOT EXISTS idx_pagos_mensuales_user   ON pagos_mensuales(user_id);",
    ),
    (
        "indice idx_pagos_mensuales_activa",
        "CREATE INDEX IF NOT EXISTS idx_pagos_mensuales_activa ON pagos_mensuales(activa);",
    ),
    (
        "indice idx_prestamos_user",
        "CREATE INDEX IF NOT EXISTS idx_prestamos_user         ON prestamos_personales(user_id);",
    ),
    (
        "indice idx_prestamos_estado",
        "CREATE INDEX IF NOT EXISTS idx_prestamos_estado       ON prestamos_personales(estado);",
    ),

    # ── Row-Level Security ─────────────────────────────────────────────────────
    ("RLS en pagos_mensuales",      "ALTER TABLE pagos_mensuales      ENABLE ROW LEVEL SECURITY;"),
    ("RLS en prestamos_personales", "ALTER TABLE prestamos_personales ENABLE ROW LEVEL SECURITY;"),

    # ── Trigger updated_at en prestamos_personales ─────────────────────────────
    # Reutiliza fn_set_updated_at() creada en migrate_to_supabase.py
    (
        "trigger trg_prestamos_updated",
        """
        CREATE OR REPLACE TRIGGER trg_prestamos_updated
        BEFORE UPDATE ON prestamos_personales
        FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();
        """,
    ),
]

_TABLAS   = [n for n, _ in SQL_PASOS if n.startswith("tabla")]
_INDICES  = [n for n, _ in SQL_PASOS if n.startswith("indice")]
_TRIGGERS = [n for n, _ in SQL_PASOS if n.startswith("trigger")]


def migrar():
    print("\n-- Migracion v2: refactor de deudas --\n")

    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=10)
        conn.autocommit = False
        print("[OK] Conectado a Postgres\n")
    except psycopg2.OperationalError as e:
        print(f"[ERROR] No se pudo conectar: {e}")
        sys.exit(1)

    cur = conn.cursor()

    try:
        for nombre, sql in SQL_PASOS:
            print(f"  Ejecutando {nombre}...")
            cur.execute(sql)

        conn.commit()
        print(
            f"\n[OK] Migracion v2 completa. "
            f"{len(_TABLAS)} tabla(s) nuevas, "
            f"{len(_INDICES)} indice(s), "
            f"{len(_TRIGGERS)} trigger(s)."
        )

    except Exception as e:
        conn.rollback()
        print(f"\n[ERROR] Error durante la migracion: {e}")
        print("  → Se hizo ROLLBACK. La base de datos quedo sin cambios.")
        print("  → Revisa el mensaje de error y vuelve a ejecutar el script.")
        cur.close()
        conn.close()
        sys.exit(1)

    cur.close()
    conn.close()


if __name__ == "__main__":
    migrar()
