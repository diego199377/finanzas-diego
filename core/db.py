"""Capa de acceso a Postgres (Supabase). Toda conexión pasa por aquí."""
import psycopg2
import psycopg2.pool
import psycopg2.extras
from contextlib import contextmanager
from core.config import DATABASE_URL

_pool = None


def _get_pool() -> psycopg2.pool.SimpleConnectionPool:
    global _pool
    if _pool is None:
        try:
            _pool = psycopg2.pool.SimpleConnectionPool(
                minconn=1,
                maxconn=5,
                dsn=DATABASE_URL,
            )
        except psycopg2.OperationalError as e:
            msg = str(e).lower()
            if "could not translate host name" in msg or "name or service not known" in msg:
                raise ConnectionError(
                    "No se pudo resolver el host de la BD. "
                    "Verifica DATABASE_URL en .env y tu conexión a internet."
                ) from e
            if "password authentication failed" in msg:
                raise ConnectionError(
                    "Contraseña incorrecta. Verifica DATABASE_URL en .env."
                ) from e
            if "timeout" in msg or "timed out" in msg:
                raise ConnectionError(
                    "Timeout al conectar a la BD. Verifica tu conexión."
                ) from e
            raise ConnectionError(f"Error al conectar a Postgres: {e}") from e
    return _pool


@contextmanager
def get_connection():
    """Context manager: obtiene conexión del pool y la devuelve al terminar."""
    pool = _get_pool()
    conn = pool.getconn()
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


@contextmanager
def get_cursor(commit: bool = True):
    """Context manager: cursor con RealDictCursor, commit automático en éxito."""
    with get_connection() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            yield cur
            if commit:
                conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()


def execute_query(sql: str, params=None) -> list[dict]:
    """SELECT — devuelve lista de dicts."""
    with get_cursor(commit=False) as cur:
        cur.execute(sql, params)
        return [dict(row) for row in cur.fetchall()]


def execute_command(sql: str, params=None) -> int:
    """INSERT/UPDATE/DELETE — devuelve rowcount."""
    with get_cursor(commit=True) as cur:
        cur.execute(sql, params)
        return cur.rowcount


def execute_returning(sql: str, params=None) -> dict | None:
    """INSERT ... RETURNING — devuelve el dict de la fila insertada."""
    with get_cursor(commit=True) as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
        return dict(row) if row else None
