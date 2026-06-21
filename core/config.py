import os
from dotenv import load_dotenv

load_dotenv()

_PLACEHOLDERS = {
    "https://your-project.supabase.co",
    "your-anon-key-here",
    "your-service-role-key-here",
    "your-db-password-here",
    "postgresql://postgres.project-id:password@aws-1-sa-east-1.pooler.supabase.com:5432/postgres",
    "generate-a-random-secret-for-sessions",
}

_VARS_CRITICAS = [
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
    "SUPABASE_DB_PASSWORD",
    "DATABASE_URL",
    "APP_SECRET_KEY",
]

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_DB_PASSWORD = os.getenv("SUPABASE_DB_PASSWORD")
DATABASE_URL = os.getenv("DATABASE_URL")
APP_ENV = os.getenv("APP_ENV", "development")
APP_SECRET_KEY = os.getenv("APP_SECRET_KEY")


def is_configured() -> bool:
    for var in _VARS_CRITICAS:
        valor = os.getenv(var)
        if valor is None or valor in _PLACEHOLDERS or valor.startswith("your-"):
            return False
    return True


def _validar():
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
            "Edita el archivo .env con tus credenciales reales de Supabase."
        )

    print("Variables de entorno cargadas correctamente.")


_validar()
