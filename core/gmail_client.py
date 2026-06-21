"""Cliente Gmail con OAuth 2.0. Funciona en local, Streamlit Cloud y Render."""

import base64
import json
import os
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

_BASE_DIR = Path(__file__).parent.parent
TOKEN_PATH = _BASE_DIR / "token.json"

QUERIES_BANCO = {
    "bcp":  "from:notificaciones@bcp.com.pe OR from:notificaciones@viabcp.com",
    "bbva": "from:notificaciones@bbva.pe OR from:bbvacontinental@bbva.pe",
    "yape": "from:no-reply@yape.com.pe OR subject:Yape",
}


def _es_produccion() -> bool:
    """Detecta si la app corre en un entorno de producción (Streamlit Cloud o Render)."""
    if os.getenv("STREAMLIT_SHARING_MODE") or os.getenv("STREAMLIT_SERVER_HEADLESS"):
        return True
    if os.getenv("RENDER"):
        return True
    return os.getenv("APP_ENV", "development") == "production"


def _es_render() -> bool:
    """Detecta específicamente si corre en Render."""
    return bool(os.getenv("RENDER"))


def _es_streamlit_cloud() -> bool:
    """Detecta específicamente si corre en Streamlit Cloud."""
    return bool(os.getenv("STREAMLIT_SHARING_MODE") or os.getenv("STREAMLIT_SERVER_HEADLESS"))


def _get_client_config() -> dict:
    """
    Lee la configuración OAuth del lugar correcto según ambiente:
    - Render:          /etc/secrets/credentials-web.json
    - Streamlit Cloud: st.secrets["gmail_credentials"]
    - Local:           credentials-web.json o credentials.json en raíz
    """
    if _es_render():
        render_path = Path("/etc/secrets/credentials-web.json")
        if render_path.exists():
            with open(render_path, encoding="utf-8") as f:
                return json.load(f)
        raise FileNotFoundError(
            "No se encontró /etc/secrets/credentials-web.json en Render. "
            "Verifica que el Secret File esté configurado en el dashboard."
        )

    if _es_streamlit_cloud():
        try:
            import streamlit as st
            s = st.secrets["gmail_credentials"]
            return {
                "web": {
                    "client_id":                   s["client_id"],
                    "project_id":                  s["project_id"],
                    "auth_uri":                    s["auth_uri"],
                    "token_uri":                   s["token_uri"],
                    "auth_provider_x509_cert_url": s["auth_provider_x509_cert_url"],
                    "client_secret":               s["client_secret"],
                    "redirect_uris":               list(s["redirect_uris"]),
                }
            }
        except Exception as exc:
            raise RuntimeError(
                "No se pudieron leer credentials de st.secrets['gmail_credentials']. "
                f"Verifica la configuración en Streamlit Cloud. Error: {exc}"
            ) from exc

    # Local: preferir Web client; fallback a Desktop
    for fname in ("credentials-web.json", "credentials.json"):
        path = _BASE_DIR / fname
        if path.exists():
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    raise FileNotFoundError(
        "No se encontró credentials-web.json ni credentials.json. "
        "Descarga las credenciales OAuth desde Google Cloud Console."
    )


def _get_token_dict() -> Optional[dict]:
    """
    Lee el token OAuth según ambiente:
    - Render:          /etc/secrets/token.json
    - Streamlit Cloud: st.secrets["gmail_token"]
    - Local:           token.json en raíz
    """
    if _es_render():
        render_path = Path("/etc/secrets/token.json")
        if render_path.exists():
            try:
                with open(render_path, encoding="utf-8") as f:
                    return json.load(f)
            except Exception as exc:
                print(f"[gmail_client] Error leyendo token.json desde Render: {exc}")
        return None

    if _es_streamlit_cloud():
        try:
            import streamlit as st
            s = st.secrets["gmail_token"]
            return {
                "token":         s["token"],
                "refresh_token": s["refresh_token"],
                "token_uri":     s["token_uri"],
                "client_id":     s["client_id"],
                "client_secret": s["client_secret"],
                "scopes":        list(s["scopes"]),
            }
        except Exception as exc:
            print(f"[gmail_client] No se pudo leer gmail_token de st.secrets: {exc}")
            return None

    # Local
    if TOKEN_PATH.exists():
        try:
            with open(TOKEN_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            print(f"[gmail_client] Error leyendo token.json local: {exc}")
    return None


def get_credentials() -> Credentials:
    """
    Obtiene credenciales OAuth válidas.
    - Local:           token.json del disco; abre navegador si no existe.
    - Render:          /etc/secrets/token.json; falla claro si no existe.
    - Streamlit Cloud: st.secrets["gmail_token"]; falla claro si no hay token.
    """
    creds: Optional[Credentials] = None

    token_data = _get_token_dict()
    if token_data:
        try:
            creds = Credentials.from_authorized_user_info(token_data, SCOPES)
        except Exception as exc:
            print(f"[gmail_client] Error creando Credentials desde token: {exc}")
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                if not _es_produccion():
                    TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
            except Exception as exc:
                print(f"[gmail_client] Refresh falló: {exc}")
                creds = None

        if not creds:
            if _es_produccion():
                raise RuntimeError(
                    "En producción se requiere un token válido. "
                    "Render: sube token.json a /etc/secrets/. "
                    "Streamlit Cloud: actualiza st.secrets['gmail_token']. "
                    "Regenera el token localmente si expiró."
                )
            client_config = _get_client_config()
            flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
            creds = flow.run_local_server(port=0)
            TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")

    return creds


def get_gmail_service():
    """Retorna el cliente autenticado de Gmail API."""
    return build("gmail", "v1", credentials=get_credentials())


def buscar_correos(
    query: str,
    max_results: int = 500,
    after: Optional[str] = None,
) -> list[dict]:
    """
    Busca correos según query Gmail con paginación automática.
    after: fecha desde en formato YYYY-MM-DD.
    Retorna lista de {id, threadId}.
    """
    service = get_gmail_service()
    if after:
        fecha_fmt = after.replace("-", "/")
        query = f"{query} after:{fecha_fmt}"

    messages: list[dict] = []
    page_token: Optional[str] = None

    while len(messages) < max_results:
        batch = min(500, max_results - len(messages))
        kwargs: dict = {
            "userId": "me",
            "q": query,
            "maxResults": batch,
        }
        if page_token:
            kwargs["pageToken"] = page_token

        result = service.users().messages().list(**kwargs).execute()
        msgs = result.get("messages", [])
        messages.extend(msgs)

        page_token = result.get("nextPageToken")
        if not page_token or not msgs:
            break

    return messages[:max_results]


def get_correo(message_id: str) -> dict:
    """Trae el contenido completo de un correo (headers + body)."""
    service = get_gmail_service()
    return service.users().messages().get(
        userId="me",
        id=message_id,
        format="full",
    ).execute()


# ── Extracción de texto ────────────────────────────────────────────────────────

def _decode_data(data: str) -> str:
    """Decodifica base64url a string, probando encodings comunes."""
    padding = 4 - len(data) % 4
    if padding != 4:
        data += "=" * padding
    raw = base64.urlsafe_b64decode(data)
    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _extract_parts(payload: dict) -> tuple[str, str]:
    """Extrae (texto_plano, texto_html) del payload de forma recursiva."""
    mime = payload.get("mimeType", "")
    body_data = payload.get("body", {}).get("data", "")

    if mime == "text/plain" and body_data:
        return _decode_data(body_data), ""
    if mime == "text/html" and body_data:
        return "", _decode_data(body_data)

    plain, html = "", ""
    for part in payload.get("parts", []):
        p, h = _extract_parts(part)
        plain += p
        html += h
    return plain, html


def extraer_texto_correo(message_dict: dict) -> str:
    """
    Extrae el texto del correo priorizando plain text.
    Si solo hay HTML, lo convierte a texto limpio con BeautifulSoup.
    """
    payload = message_dict.get("payload", {})
    plain, html = _extract_parts(payload)

    if plain.strip():
        return plain.strip()

    if html.strip():
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style"]):
            tag.decompose()
        return soup.get_text(separator="\n").strip()

    return ""


def get_headers(message_dict: dict) -> dict[str, str]:
    """Devuelve los headers del correo como dict {nombre: valor}."""
    headers = message_dict.get("payload", {}).get("headers", [])
    return {h["name"]: h["value"] for h in headers}
