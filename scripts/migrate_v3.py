"""
Migración v3 — Tabla correos_procesados.

Agrega la tabla para trackear correos de Gmail ya procesados,
evitando importar el mismo correo dos veces.
Referencia transacciones(id) para vincular el correo con la transacción creada.

Idempotente: usa IF NOT EXISTS.
Todo en una sola transacción: ROLLBACK automático si algo falla.

Ejecutar:
    python scripts/migrate_v3.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg2
from core.config import DATABASE_URL

SQL_PASOS = [

    # ── Tabla: correos_procesados ──────────────────────────────────────────
    # Evita duplicados: UNIQUE(user_id, gmail_message_id).
    # estado: ciclo de vida del correo desde que se detecta hasta confirmar.
    (
        "tabla correos_procesados",
        """
        CREATE TABLE IF NOT EXISTS correos_procesados (
            id                      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            user_id                 BIGINT       NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            gmail_message_id        TEXT         NOT NULL,
            banco                   TEXT         NOT NULL
                                        CHECK(banco IN ('bcp', 'bbva', 'yape', 'desconocido')),
            fecha_correo            TIMESTAMPTZ  NOT NULL,
            asunto                  TEXT,
            procesado_at            TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            transaccion_id          BIGINT       REFERENCES transacciones(id) ON DELETE SET NULL,
            estado                  TEXT         NOT NULL DEFAULT 'pendiente'
                                        CHECK(estado IN ('pendiente', 'confirmado', 'descartado', 'error')),
            monto_detectado         NUMERIC(12,2),
            establecimiento_detectado TEXT,
            categoria_sugerida      TEXT,
            raw_subject             TEXT,
            notas                   TEXT,
            UNIQUE(user_id, gmail_message_id)
        );
        """,
    ),

    # ── Índices ────────────────────────────────────────────────────────────
    (
        "indice idx_correos_user_estado",
        "CREATE INDEX IF NOT EXISTS idx_correos_user_estado ON correos_procesados(user_id, estado);",
    ),
    (
        "indice idx_correos_gmail_id",
        "CREATE INDEX IF NOT EXISTS idx_correos_gmail_id ON correos_procesados(gmail_message_id);",
    ),

    # ── Row-Level Security ─────────────────────────────────────────────────
    (
        "RLS en correos_procesados",
        "ALTER TABLE correos_procesados ENABLE ROW LEVEL SECURITY;",
    ),
]

_TABLAS  = [n for n, _ in SQL_PASOS if n.startswith("tabla")]
_INDICES = [n for n, _ in SQL_PASOS if n.startswith("indice")]


def migrar():
    print("\n-- Migracion v3: tabla correos_procesados --\n")

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
            f"\n[OK] Migracion v3 completa. "
            f"{len(_TABLAS)} tabla(s) nueva(s), "
            f"{len(_INDICES)} indice(s)."
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
