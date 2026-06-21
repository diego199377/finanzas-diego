"""
Verificación post-migración a Supabase Postgres.

Lista tablas, índices, estado de RLS y triggers en el schema public.

Ejecutar:
    python scripts/verify_migration.py
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg2
from psycopg2.extras import RealDictCursor
from core.config import DATABASE_URL

TABLAS_ESPERADAS = [
    "users",
    "tarjetas",
    "transacciones",
    "ingresos_recurrentes",
    "ingresos_extras",
    "deudas",
    "config_usuario",
]


def verificar():
    print("\n── Verificación de migración ──\n")

    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=10)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        print("✓ Conectado a Postgres\n")
    except psycopg2.OperationalError as e:
        print(f"✗ Error de conexión: {e}")
        sys.exit(1)

    # ── 1. Tablas en schema public ─────────────────────────────────────────
    cur.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_type   = 'BASE TABLE'
        ORDER BY table_name;
    """)
    tablas_bd = {row["table_name"] for row in cur.fetchall()}

    print("── Tablas en schema public ──")
    for tabla in sorted(tablas_bd):
        marca = "✓" if tabla in TABLAS_ESPERADAS else "?"
        print(f"  {marca} {tabla}")

    faltantes = set(TABLAS_ESPERADAS) - tablas_bd
    if faltantes:
        print(f"\n  ✗ Faltan: {', '.join(sorted(faltantes))}")
    else:
        print(f"\n  Todas las {len(TABLAS_ESPERADAS)} tablas esperadas están presentes.")

    # ── 2. Índices por tabla ───────────────────────────────────────────────
    print("\n── Índices por tabla ──")
    cur.execute("""
        SELECT tablename, count(*) AS total
        FROM pg_indexes
        WHERE schemaname = 'public'
        GROUP BY tablename
        ORDER BY tablename;
    """)
    for row in cur.fetchall():
        print(f"  {row['tablename']:<25} {row['total']} índice(s)")

    # ── 3. Row-Level Security ──────────────────────────────────────────────
    print("\n── Row-Level Security ──")
    cur.execute("""
        SELECT relname AS tabla, relrowsecurity AS rls_activo
        FROM pg_class
        JOIN pg_namespace ON pg_namespace.oid = pg_class.relnamespace
        WHERE nspname = 'public'
          AND relkind = 'r'
        ORDER BY relname;
    """)
    for row in cur.fetchall():
        estado = "HABILITADO ✓" if row["rls_activo"] else "deshabilitado"
        print(f"  {row['tabla']:<25} RLS {estado}")

    # ── 4. Triggers ────────────────────────────────────────────────────────
    print("\n── Triggers en schema public ──")
    cur.execute("""
        SELECT trigger_name, event_object_table AS tabla, event_manipulation AS evento
        FROM information_schema.triggers
        WHERE trigger_schema = 'public'
        ORDER BY trigger_name;
    """)
    triggers = cur.fetchall()
    if triggers:
        for row in triggers:
            print(f"  ✓ {row['trigger_name']} ({row['evento']} ON {row['tabla']})")
    else:
        print("  — No se encontraron triggers.")

    # ── 5. Función fn_set_updated_at ───────────────────────────────────────
    print("\n── Funciones PL/pgSQL ──")
    cur.execute("""
        SELECT routine_name
        FROM information_schema.routines
        WHERE routine_schema = 'public'
          AND routine_type   = 'FUNCTION'
        ORDER BY routine_name;
    """)
    funciones = cur.fetchall()
    if funciones:
        for row in funciones:
            print(f"  ✓ {row['routine_name']}()")
    else:
        print("  — No se encontraron funciones.")

    print("\n── Verificación completa ──\n")
    cur.close()
    conn.close()


if __name__ == "__main__":
    verificar()
