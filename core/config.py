"""Configuración de variables de entorno."""
import os
from dotenv import load_dotenv

load_dotenv()

# Placeholders que indican variable sin configurar (del .env.example)
_PLACEHOLDERS = {
    "postgresql://postgres.project-id:password@aws-1-sa-east-1.pooler.supabase.com:5432/postgres",
    "generate-a-random-secret-for-sessions",
    "sk-ant-api03-your-key-here",
    "your-anthropic-key",
}

# Variables CRÍTICAS que la app necesita para arrancar
_VARS_CRITICAS = [
    "DATABASE_URL",
    "APP_SECRET_KEY",
]

# Variables OPCIONALES (la app puede arrancar sin ellas, pero algunas features no funcionarán)
_VARS_OPCIONALES = [
    "ANTHROPIC_API_KEY",  # sin esto el parser IA no funciona
]

# Cargar variables
DATABASE_URL = os.getenv("DATABASE_URL")
APP_SECRET_KEY = os.getenv("APP_SECRET_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
APP_ENV = os.getenv("APP_ENV", "development")


def is_configured() -> bool:
    """Verifica si las variables críticas están configuradas correctamente."""
    for var in _VARS_CRITICAS:
        valor = os.getenv(var)
        if valor is None or valor in _PLACEHOLDERS or valor.startswith("your-"):
            return False
    return True


def _validar():
    """Valida que las variables críticas estén configuradas. Las opcionales solo dan warning."""
    faltantes = []
    con_placeholder = []

    for var in _VARS_CRITICAS:
        valor = os.getenv(var)
        if valor is None:
            faltantes.append(var)
        elif valor in _PLACEHOLDERS or valor.startswith("your-"):
            con_placeholder.append(var)

    if faltantes:
        raise EnvironmentError(
            f"Variables de entorno faltantes: {', '.join(faltantes)}.\n"
            "Copia .env.example a .env y completa los valores reales."
        )

    if con_placeholder:
        raise EnvironmentError(
            f"Variables con placeholder sin configurar: {', '.join(con_placeholder)}.\n"
            "Edita el archivo .env con tus credenciales reales."
        )

    # Warning para opcionales (no falla, solo informa)
    opcionales_faltantes = []
    for var in _VARS_OPCIONALES:
        valor = os.getenv(var)
        if valor is None or valor in _PLACEHOLDERS or valor.startswith("your-"):
            opcionales_faltantes.append(var)

    if opcionales_faltantes:
        print(f"⚠️  Variables opcionales sin configurar: {', '.join(opcionales_faltantes)}")
        print("   La app arrancará pero algunas features estarán deshabilitadas.")
    else:
        print("✅ Variables de entorno cargadas correctamente.")


_validar()
