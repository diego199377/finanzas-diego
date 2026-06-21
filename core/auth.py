"""Autenticación y gestión de usuarios."""
from passlib.context import CryptContext
from core.db import execute_query, execute_command, execute_returning

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

_BCRYPT_MAX_BYTES = 72


def _validar_longitud(password: str) -> None:
    nbytes = len(password.encode("utf-8"))
    if nbytes > _BCRYPT_MAX_BYTES:
        raise ValueError(
            f"La contraseña tiene {nbytes} bytes, el máximo es {_BCRYPT_MAX_BYTES}. "
            "Usa una contraseña más corta o sin caracteres especiales."
        )


def hash_password(password: str) -> str:
    _validar_longitud(password)
    return _pwd_ctx.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    if len(password.encode("utf-8")) > _BCRYPT_MAX_BYTES:
        return False
    return _pwd_ctx.verify(password, hashed)


def _sin_hash(row: dict) -> dict:
    return {k: v for k, v in row.items() if k != "password_hash"}


def create_user(email: str, password: str, nombre_display: str = None) -> tuple[bool, str, int | None]:
    """Crea usuario nuevo. Devuelve (success, mensaje, user_id | None)."""
    try:
        email = email.strip().lower()
        if not email:
            return False, "El email no puede estar vacío.", None
        if not password:
            return False, "La contraseña no puede estar vacía.", None

        if get_user_by_email(email):
            return False, f"Ya existe un usuario con el email '{email}'.", None

        row = execute_returning(
            """
            INSERT INTO users (email, password_hash, nombre_display)
            VALUES (%s, %s, %s)
            RETURNING id, email, nombre_display, activo, created_at
            """,
            (email, hash_password(password), nombre_display),
        )
        if not row:
            return False, "No se pudo crear el usuario (RETURNING vacío).", None
        return True, "Usuario creado exitosamente.", row["id"]
    except Exception as exc:
        return False, str(exc), None


def authenticate_user(email: str, password: str) -> dict | None:
    """Verifica credenciales. Devuelve dict del usuario o None si falla."""
    email = email.strip().lower()
    rows = execute_query(
        "SELECT * FROM users WHERE email = %s AND activo = TRUE",
        (email,),
    )
    if not rows:
        return None
    user = rows[0]
    if not verify_password(password, user["password_hash"]):
        return None
    execute_command(
        "UPDATE users SET ultimo_login = NOW() WHERE id = %s",
        (user["id"],),
    )
    return _sin_hash(user)


def get_user_by_id(user_id: int) -> dict | None:
    rows = execute_query(
        """
        SELECT id, email, nombre_display, activo, created_at, ultimo_login
        FROM users WHERE id = %s
        """,
        (user_id,),
    )
    return rows[0] if rows else None


def get_user_by_email(email: str) -> dict | None:
    email = email.strip().lower()
    rows = execute_query(
        """
        SELECT id, email, nombre_display, activo, created_at, ultimo_login
        FROM users WHERE email = %s
        """,
        (email,),
    )
    return rows[0] if rows else None


def update_user_profile(
    user_id: int,
    nombre_display: str = None,
    new_password: str = None,
    current_password: str = None,
) -> tuple[bool, str]:
    """
    Actualiza el perfil del usuario.
    Si se cambia password, current_password es obligatorio.
    Devuelve (success, mensaje).
    """
    updates = []
    params = []

    if nombre_display is not None and nombre_display.strip():
        updates.append("nombre_display = %s")
        params.append(nombre_display.strip())

    if new_password:
        if not current_password:
            return False, "Debes ingresar tu contraseña actual para cambiarla."
        rows = execute_query("SELECT password_hash FROM users WHERE id = %s", (user_id,))
        if not rows or not verify_password(current_password, rows[0]["password_hash"]):
            return False, "La contraseña actual es incorrecta."
        if len(new_password) < 8:
            return False, "La nueva contraseña debe tener al menos 8 caracteres."
        if len(new_password.encode("utf-8")) > 72:
            return False, "La contraseña es muy larga (máx 72 caracteres)."
        updates.append("password_hash = %s")
        params.append(hash_password(new_password))

    if not updates:
        return False, "No hay cambios para guardar."

    params.append(user_id)
    execute_command(
        f"UPDATE users SET {', '.join(updates)} WHERE id = %s",
        tuple(params),
    )
    return True, "Perfil actualizado correctamente."


def get_full_user(user_id: int) -> dict | None:
    """Devuelve user dict con todos los campos (sin password_hash)."""
    rows = execute_query(
        "SELECT id, email, nombre_display, created_at FROM users WHERE id = %s",
        (user_id,),
    )
    return dict(rows[0]) if rows else None
