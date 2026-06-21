"""
Persistencia de sesión mediante cookie firmada con itsdangerous.

Flujo:
  login exitoso  → save_session(user_id)  → cookie válida 7 días (via JS)
  recarga página → load_session()         → devuelve user dict o None
                                            (lee cookie del HTTP request)
  logout         → clear_session()        → borra cookie (via JS)

Requiere Streamlit >= 1.38 (st.context.cookies) y 1.40 (st.html con JS).
La cookie solo contiene el user_id firmado con APP_SECRET_KEY + itsdangerous.
Nunca se guarda la contraseña ni datos sensibles.
"""

import streamlit as st
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from core.auth import get_user_by_id
from core.config import APP_SECRET_KEY

COOKIE_NAME = "fz_session"
_SALT       = "fz-session-v1"
_DAYS       = 7
_MAX_AGE    = _DAYS * 86400   # segundos


def _serializer() -> URLSafeTimedSerializer:
    key = APP_SECRET_KEY or "dev-only-insecure-fallback"
    return URLSafeTimedSerializer(key, salt=_SALT)


def make_token(user_id: int) -> str:
    return _serializer().dumps(user_id)


def verify_token(token: str) -> int | None:
    """Devuelve user_id si el token es válido y no expiró; None si no."""
    try:
        uid = _serializer().loads(token, max_age=_MAX_AGE)
        return int(uid)
    except (BadSignature, SignatureExpired, Exception):
        return None


def save_session(user_id: int) -> None:
    """
    Escribe la cookie firmada via components.html() (iframe).
    A diferencia de st.html(), components.html() ejecuta el JS de forma
    síncrona antes de que Streamlit procese el siguiente rerun, garantizando
    que la cookie exista cuando el navegador recargue la página.
    window.top.document accede al documento principal (no al iframe).
    """
    import streamlit.components.v1 as components

    token = make_token(user_id)
    components.html(f"""
    <script>
        var topDoc = window.top.document;
        topDoc.cookie = "{COOKIE_NAME}={token};max-age={_MAX_AGE};path=/;SameSite=Lax";
        console.log("[fz] cookie guardada:", topDoc.cookie.includes("{COOKIE_NAME}="));
    </script>
    """, height=0)


def load_session() -> dict | None:
    """
    Lee la cookie del request HTTP actual via st.context.cookies (Streamlit ≥ 1.38).
    Disponible desde que el navegador envía la cookie en el header de la petición.
    En la misma sesión WebSocket en que se hizo save_session(), la cookie
    se lee en la siguiente recarga de página (F5) o apertura de pestaña.
    """
    try:
        token = st.context.cookies.get(COOKIE_NAME)
    except AttributeError:
        return None   # Streamlit < 1.38 (no debería ocurrir en producción)

    if not token:
        return None

    uid = verify_token(token)
    if uid is None:
        clear_session()   # cookie corrupta o expirada: borrarla
        return None

    user = get_user_by_id(uid)
    if user is None:
        clear_session()   # usuario eliminado de la BD: borrar cookie huérfana
        return None

    return user


def clear_session() -> None:
    """Elimina la cookie del navegador via JavaScript en el top window."""
    import streamlit.components.v1 as components

    components.html(f"""
    <script>
        const topDoc = window.top.document;
        topDoc.cookie = "{COOKIE_NAME}=;max-age=0;path=/;SameSite=Lax";
        topDoc.cookie = "{COOKIE_NAME}=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/;SameSite=Lax";
        console.log("Cookie borrada");
    </script>
    """, height=0)
