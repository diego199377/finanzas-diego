# Finanzas Diego

App de finanzas personales — Python 3.11 · Streamlit · SQLite · Plotly

## Requisitos

- Python 3.11+

## Instalación

```powershell
pip install -r requirements.txt
```

## Inicializar base de datos (primera vez)

```powershell
python scripts/db_init.py
```

Crea `data/finanzas.db` con el schema completo y carga las tarjetas plantilla (BCP Crédito, BBVA Débito).

## Ejecutar

```powershell
streamlit run app.py
```

## Estructura

```
finanzas-diego/
├── app.py                   # Entrada, navegación multi-página
├── pages/
│   ├── carga_rapida.py      # ⚡ Home — entrada texto libre + parser
│   ├── carga_individual.py  # ✏️ Formulario completo
│   ├── transacciones.py     # 📋 Tabla editable con filtros
│   ├── tarjetas.py          # 💳 Grid de cards por tarjeta
│   ├── ingresos_deudas.py   # 💼 CRUD ingresos y deudas
│   └── dashboard.py         # 📊 Próximamente (sesión 3)
├── core/
│   ├── db.py                # get_connection() — FK ON, localtime
│   ├── parser_express.py    # Regex parser para carga rápida
│   ├── validators.py        # Validaciones compartidas
│   └── styles.py            # CSS custom fintech
├── config/
│   ├── categorias.json      # Jerarquía macro→sub para Perú
│   └── tarjetas.json        # Plantillas BCP y BBVA
├── data/
│   └── finanzas.db          # Creado por db_init.py (en .gitignore)
└── scripts/
    └── db_init.py           # Setup inicial + seed de tarjetas
```

## Convenciones

| Aspecto | Valor |
|---|---|
| Moneda | S/ con 2 decimales |
| Fechas UI | DD/MM/YYYY |
| Fechas BD | ISO 8601 (YYYY-MM-DD) |
| Zona horaria | Lima (`localtime`) |
| Banco 1 | BCP |
| Banco 2 | BBVA |
| Wallets | Yape, Plin |

## Variables de entorno

El archivo `.env` **no se commitea a git** (está en `.gitignore`). Contiene credenciales sensibles de Supabase.

### Configuración inicial

```powershell
# Windows
copy .env.example .env

# Linux / Mac
cp .env.example .env
```

Luego edita `.env` con tus valores reales (ver más abajo).

### Credenciales que necesitas obtener de Supabase

Ingresa a [https://supabase.com/dashboard](https://supabase.com/dashboard) y abre tu proyecto:

| Variable | Dónde encontrarla |
|---|---|
| `SUPABASE_URL` | Settings → API → Project URL |
| `SUPABASE_ANON_KEY` | Settings → API → Project API Keys → `anon public` |
| `SUPABASE_SERVICE_ROLE_KEY` | Settings → API → Project API Keys → `service_role` |
| `SUPABASE_DB_PASSWORD` | Settings → Database → Database password (el que elegiste al crear el proyecto) |
| `DATABASE_URL` | Settings → Database → Connection string → **Session pooler** (puerto 5432) |

Para `APP_SECRET_KEY` genera una cadena aleatoria segura, por ejemplo:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

## Criterios de contraseñas

| Criterio | Regla |
|---|---|
| Mínimo | 8 caracteres |
| Máximo | 72 bytes (~72 caracteres ASCII) |
| Recomendado | Mezclar mayúsculas, minúsculas, números y símbolos ASCII (`!`, `@`, `#`, `$`, `%`, `&`, `*`, `_`, `-`) |

**Evitar caracteres no-ASCII:** tildes (`á`, `é`, `í`, `ó`, `ú`), `ñ`, emojis y cualquier carácter fuera del rango ASCII.  
Cada uno ocupa 2–4 bytes y puede agotar el límite de 72 bytes antes de lo esperado.

**No reutilices** la contraseña de Gmail, GitHub ni de ningún servicio externo.

**Guarda tu contraseña** en un gestor seguro (Bitwarden, 1Password) o en un archivo en OneDrive dentro de una carpeta cifrada.

> El límite de 72 bytes es una restricción de bcrypt (algoritmo de hashing). La app rechaza contraseñas que lo excedan en lugar de truncarlas silenciosamente.

## Sesión 2 (pendiente)

- Migración de schema a Supabase Postgres
- Multi-usuario con autenticación Supabase Auth
- Upgrade visual
- Deploy a Streamlit Cloud
