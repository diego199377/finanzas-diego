"""
Migración de schema SQLite → Supabase Postgres.

Crea todas las tablas, índices, trigger y habilita RLS en el schema public.
Idempotente: usa IF NOT EXISTS, se puede ejecutar varias veces sin error.
Todo en una sola transacción: si algo falla hace ROLLBACK automático.

Ejecutar (solo cuando las credenciales en .env sean reales):
    python scripts/migrate_to_supabase.py
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg2
from core.config import DATABASE_URL

# ---------------------------------------------------------------------------
# SQL de migración
# ---------------------------------------------------------------------------

SQL_PASOS = [

    # ── Función para trigger updated_at ────────────────────────────────────
    (
        "función fn_set_updated_at",
        """
        CREATE OR REPLACE FUNCTION fn_set_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """,
    ),

    # ── Tabla: users ───────────────────────────────────────────────────────
    # Nota: Supabase Auth usa auth.users (schema separado).
    # Esta tabla es nuestra capa de perfil en el schema public.
    (
        "tabla users",
        """
        CREATE TABLE IF NOT EXISTS users (
            id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            email          TEXT      NOT NULL UNIQUE,
            password_hash  TEXT      NOT NULL,
            nombre_display TEXT,
            created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            ultimo_login   TIMESTAMPTZ,
            activo         BOOLEAN   NOT NULL DEFAULT TRUE
        );
        """,
    ),

    # ── Tabla: tarjetas ────────────────────────────────────────────────────
    # PK cambia de alias (TEXT) a BIGSERIAL.
    # UNIQUE(user_id, alias) garantiza que cada usuario no repita alias.
    (
        "tabla tarjetas",
        """
        CREATE TABLE IF NOT EXISTS tarjetas (
            id             BIGINT  GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            user_id        BIGINT  NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            alias          TEXT    NOT NULL,
            banco          TEXT    NOT NULL,
            tipo           TEXT    NOT NULL CHECK(tipo IN ('Credito', 'Debito')),
            ultimos4       TEXT    CHECK(length(ultimos4) = 4),
            linea_aprobada NUMERIC(12,2),
            dia_corte      INTEGER CHECK(dia_corte BETWEEN 1 AND 31),
            dia_pago       INTEGER CHECK(dia_pago  BETWEEN 1 AND 31),
            activa         BOOLEAN NOT NULL DEFAULT TRUE,
            color_hex      TEXT    DEFAULT '#2563eb',
            UNIQUE(user_id, alias)
        );
        """,
    ),

    # ── Tabla: transacciones ───────────────────────────────────────────────
    # REAL → NUMERIC(12,2) para precisión financiera exacta.
    # TEXT fecha → DATE nativo de Postgres.
    # tarjeta_alias conservado como campo denormalizado (sin FK) para
    # consultas rápidas sin JOIN; tarjeta_id es la FK real a tarjetas.
    (
        "tabla transacciones",
        """
        CREATE TABLE IF NOT EXISTS transacciones (
            id              BIGINT  GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            user_id         BIGINT  NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            fecha_iso       DATE    NOT NULL,
            monto           NUMERIC(12,2) NOT NULL CHECK(monto > 0),
            tipo_movimiento TEXT    NOT NULL
                                CHECK(tipo_movimiento IN
                                    ('Credito','Debito','Yape','Plin',
                                     'Efectivo','Transferencia')),
            banco           TEXT,
            tarjeta_id      BIGINT  REFERENCES tarjetas(id) ON DELETE SET NULL,
            tarjeta_alias   TEXT,
            categoria_macro TEXT    NOT NULL,
            categoria_sub   TEXT,
            descripcion     TEXT,
            establecimiento TEXT,
            tag             TEXT,
            origen          TEXT    NOT NULL DEFAULT 'manual'
                                CHECK(origen IN ('manual','correo','express')),
            notas           TEXT,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """,
    ),

    # ── Tabla: ingresos_recurrentes ────────────────────────────────────────
    (
        "tabla ingresos_recurrentes",
        """
        CREATE TABLE IF NOT EXISTS ingresos_recurrentes (
            id           BIGINT  GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            user_id      BIGINT  NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            concepto     TEXT    NOT NULL,
            monto        NUMERIC(12,2) NOT NULL CHECK(monto > 0),
            dia_mes      INTEGER NOT NULL CHECK(dia_mes BETWEEN 1 AND 31),
            activo       BOOLEAN NOT NULL DEFAULT TRUE,
            fecha_inicio DATE    NOT NULL
        );
        """,
    ),

    # ── Tabla: ingresos_extras ─────────────────────────────────────────────
    (
        "tabla ingresos_extras",
        """
        CREATE TABLE IF NOT EXISTS ingresos_extras (
            id        BIGINT  GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            user_id   BIGINT  NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            fecha_iso DATE    NOT NULL,
            concepto  TEXT    NOT NULL,
            monto     NUMERIC(12,2) NOT NULL CHECK(monto > 0),
            notas     TEXT
        );
        """,
    ),

    # ── Tabla: deudas ──────────────────────────────────────────────────────
    (
        "tabla deudas",
        """
        CREATE TABLE IF NOT EXISTS deudas (
            id                 BIGINT  GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            user_id            BIGINT  NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            concepto           TEXT    NOT NULL,
            monto_total        NUMERIC(12,2) NOT NULL CHECK(monto_total > 0),
            cuota_mensual      NUMERIC(12,2) NOT NULL CHECK(cuota_mensual > 0),
            fecha_inicio       DATE    NOT NULL,
            fecha_fin_estimada DATE,
            cuotas_pagadas     INTEGER NOT NULL DEFAULT 0 CHECK(cuotas_pagadas >= 0),
            cuotas_totales     INTEGER NOT NULL CHECK(cuotas_totales > 0),
            tasa_anual         NUMERIC(5,2) CHECK(tasa_anual >= 0),
            activa             BOOLEAN NOT NULL DEFAULT TRUE
        );
        """,
    ),

    # ── Tabla: config_usuario ──────────────────────────────────────────────
    # Reemplaza config_global (global → por usuario).
    # UNIQUE(user_id, clave) evita duplicados de config por usuario.
    (
        "tabla config_usuario",
        """
        CREATE TABLE IF NOT EXISTS config_usuario (
            id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            clave       TEXT   NOT NULL,
            valor       TEXT   NOT NULL,
            descripcion TEXT,
            UNIQUE(user_id, clave)
        );
        """,
    ),

    # ── Índices ────────────────────────────────────────────────────────────
    (
        "índice idx_transacciones_fecha",
        "CREATE INDEX IF NOT EXISTS idx_transacciones_fecha      ON transacciones(fecha_iso);",
    ),
    (
        "índice idx_transacciones_categoria",
        "CREATE INDEX IF NOT EXISTS idx_transacciones_categoria  ON transacciones(categoria_macro);",
    ),
    (
        "índice idx_transacciones_tarjeta",
        "CREATE INDEX IF NOT EXISTS idx_transacciones_tarjeta    ON transacciones(tarjeta_id);",
    ),
    (
        "índice idx_transacciones_tipo",
        "CREATE INDEX IF NOT EXISTS idx_transacciones_tipo       ON transacciones(tipo_movimiento);",
    ),
    (
        "índice idx_deudas_activa",
        "CREATE INDEX IF NOT EXISTS idx_deudas_activa            ON deudas(activa);",
    ),
    # Índices multi-usuario
    (
        "índice idx_transacciones_user",
        "CREATE INDEX IF NOT EXISTS idx_transacciones_user       ON transacciones(user_id);",
    ),
    (
        "índice idx_tarjetas_user",
        "CREATE INDEX IF NOT EXISTS idx_tarjetas_user            ON tarjetas(user_id);",
    ),
    (
        "índice idx_transacciones_user_fecha",
        "CREATE INDEX IF NOT EXISTS idx_transacciones_user_fecha ON transacciones(user_id, fecha_iso);",
    ),
    (
        "índice idx_transacciones_user_categoria",
        "CREATE INDEX IF NOT EXISTS idx_transacciones_user_categoria ON transacciones(user_id, categoria_macro);",
    ),

    # ── Trigger updated_at en transacciones ───────────────────────────────
    # CREATE OR REPLACE TRIGGER disponible desde Postgres 14.
    (
        "trigger trg_transacciones_updated",
        """
        CREATE OR REPLACE TRIGGER trg_transacciones_updated
        BEFORE UPDATE ON transacciones
        FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();
        """,
    ),

    # ── Row-Level Security (solo ENABLE, sin policies aún) ─────────────────
    # Las policies se definen en la sesión de multi-usuario.
    ("RLS en transacciones",        "ALTER TABLE transacciones        ENABLE ROW LEVEL SECURITY;"),
    ("RLS en tarjetas",             "ALTER TABLE tarjetas             ENABLE ROW LEVEL SECURITY;"),
    ("RLS en ingresos_recurrentes", "ALTER TABLE ingresos_recurrentes ENABLE ROW LEVEL SECURITY;"),
    ("RLS en ingresos_extras",      "ALTER TABLE ingresos_extras      ENABLE ROW LEVEL SECURITY;"),
    ("RLS en deudas",               "ALTER TABLE deudas               ENABLE ROW LEVEL SECURITY;"),
    ("RLS en config_usuario",       "ALTER TABLE config_usuario       ENABLE ROW LEVEL SECURITY;"),
]

# ---------------------------------------------------------------------------
# Contadores para el resumen final
# ---------------------------------------------------------------------------

_TABLAS   = [n for n, _ in SQL_PASOS if n.startswith("tabla")]
_INDICES  = [n for n, _ in SQL_PASOS if n.startswith("índice")]
_TRIGGERS = [n for n, _ in SQL_PASOS if n.startswith("trigger")]


def migrar():
    print("\n-- Migracion schema -> Supabase Postgres --\n")

    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=10)
        conn.autocommit = False
        print("✓ Conectado a Postgres\n")
    except psycopg2.OperationalError as e:
        print(f"✗ No se pudo conectar: {e}")
        sys.exit(1)

    cur = conn.cursor()

    try:
        for nombre, sql in SQL_PASOS:
            print(f"  Creando {nombre}...")
            cur.execute(sql)

        conn.commit()
        print(
            f"\n[OK] Migracion completa. "
            f"{len(_TABLAS)} tablas, "
            f"{len(_INDICES)} indices, "
            f"{len(_TRIGGERS)} trigger(s)."
        )

    except Exception as e:
        conn.rollback()
        print(f"\n✗ Error durante la migración: {e}")
        print("  → Se hizo ROLLBACK. La base de datos quedó sin cambios.")
        print("  → Revisa el mensaje de error y vuelve a ejecutar el script.")
        cur.close()
        conn.close()
        sys.exit(1)

    cur.close()
    conn.close()


if __name__ == "__main__":
    migrar()
