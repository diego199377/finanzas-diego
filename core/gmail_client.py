"""Cliente Gmail con OAuth 2.0. Solo lectura (gmail.readonly)."""

import base64
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

_BASE_DIR = Path(__file__).parent.parent
CREDENTIALS_PATH = _BASE_DIR / "credentials.json"
TOKEN_PATH = _BASE_DIR / "token.json"

QUERIES_BANCO = {
    "bcp":  "from:notificaciones@bcp.com.pe OR from:notificaciones@viabcp.com",
    "bbva": "from:notificaciones@bbva.pe OR from:bbvacontinental@bbva.pe",
    "yape": "from:no-reply@yape.com.pe OR subject:Yape",
}


def get_credentials() -> Credentials:
    """Maneja flujo OAuth. Lee token.json si existe; lanza browser si no."""
    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_PATH.exists():
                raise FileNotFoundError(
                    f"No se encontró credentials.json en {CREDENTIALS_PATH}. "
                    "Descárgalo desde Google Cloud Console."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
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
