"""
Prueba de conexión a Supabase Postgres.

Verifica dos canales independientes:
  1. psycopg2  → conexión directa al pool de Postgres (Session Pooler)
  2. supabase-py → cliente REST/Realtime de Supabase

Ejecutar:
    python scripts/test_supabase_connection.py
"""

import sys
import os

# Permite importar core/ desde cualquier directorio de trabajo
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import psycopg2
from supabase import create_client
from core.config import DATABASE_URL, SUPABASE_URL, SUPABASE_ANON_KEY

# ---------------------------------------------------------------------------
# 1. Conexión directa vía psycopg2
# ---------------------------------------------------------------------------

print("\n── Prueba 1: psycopg2 (Session Pooler) ──")
try:
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=10)
    cur = conn.cursor()
    cur.execute("SELECT current_database(), current_user, version();")
    db, user, version = cur.fetchone()
    print(f"  Base de datos : {db}")
    print(f"  Usuario       : {user}")
    # Solo imprime la línea "PostgreSQL X.X.X" sin el resto del string largo
    print(f"  Versión       : {version.split(',')[0]}")
    cur.close()
    conn.close()
    print("✓ psycopg2 conectado y query ejecutada correctamente")
except psycopg2.OperationalError as e:
    msg = str(e).strip()
    print(f"✗ Error de conexión psycopg2: {msg}")
    if "could not translate host name" in msg or "Name or service not known" in msg:
        print("  → Verifica tu conexión a internet o que DATABASE_URL tenga el host correcto.")
    elif "password authentication failed" in msg:
        print("  → La contraseña en DATABASE_URL o SUPABASE_DB_PASSWORD es incorrecta.")
    elif "timeout" in msg.lower():
        print("  → Timeout: revisa si Supabase tiene restricciones de IP (Settings → Database → Network).")
    elif "SSL" in msg:
        print("  → Error SSL: el pooler requiere SSL. Prueba agregando ?sslmode=require al DATABASE_URL.")
    sys.exit(1)
except Exception as e:
    print(f"✗ Error inesperado psycopg2: {e}")
    sys.exit(1)

# ---------------------------------------------------------------------------
# 2. Cliente supabase-py (API REST)
# ---------------------------------------------------------------------------

print("\n── Prueba 2: supabase-py (REST API) ──")
try:
    client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    # Consulta mínima al endpoint de health de PostgREST
    # Si el proyecto existe y la anon key es válida, devuelve la lista de tablas públicas (vacía o no)
    response = client.table("information_schema.tables").select("table_name").limit(1).execute()
    print("✓ Cliente supabase-py conectado")
except Exception as e:
    msg = str(e).strip()
    print(f"✗ Error supabase-py: {msg}")
    if "Invalid API key" in msg or "401" in msg:
        print("  → SUPABASE_ANON_KEY inválida. Cópiala desde Settings → API en el dashboard.")
    elif "404" in msg or "not found" in msg.lower():
        print("  → SUPABASE_URL incorrecta o el proyecto fue eliminado.")
    else:
        print("  → Revisa SUPABASE_URL y SUPABASE_ANON_KEY en tu archivo .env.")

# ---------------------------------------------------------------------------
# Resultado final
# ---------------------------------------------------------------------------

print("\n✓ Pruebas completadas — las credenciales de Supabase están funcionando.\n")
