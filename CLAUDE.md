# CLAUDE.md — finanzas-diego

## Convenciones generales
- Idioma: español en UI y comentarios
- Moneda: S/ con 2 decimales (`f"S/ {monto:,.2f}"`)
- Fechas en UI: DD/MM/YYYY — en BD: ISO 8601 (YYYY-MM-DD)
- Nombres Python: snake_case — archivos: kebab-case

## Base de datos (SQLite)
- SIEMPRE usar context manager: `with get_connection() as conn:`
- SIEMPRE `PRAGMA foreign_keys = ON;` justo al abrir conexión (ya en `core/db.py`)
- NUNCA `pandas.to_sql` para escribir — usar `sqlite3` parametrizado directamente
- pandas SOLO para lectura/display (`pd.read_sql_query`)
- Timestamps: `datetime('now','localtime')` — nunca UTC
- NUNCA hardcodear paths — usar `pathlib` desde `core.db.DB_PATH`

## Streamlit
- Usar `st.session_state` para estado entre reruns
- Usar `@st.cache_data` en queries de solo lectura sobre archivos de config (no BD mutable)
- try/except en toda operación BD con `st.error()`

## Validaciones
- monto > 0 (validar en Python Y en BD via CHECK)
- categoria_macro NOT NULL
- fecha no puede ser futura
- Formularios: validar antes de insertar

## Categorías y tarjetas
- Cargar desde `config/categorias.json` y `config/tarjetas.json`
- No hardcodear en código Python

## Modularidad
- Lógica de BD en `core/db.py`
- Parsing en `core/parser_express.py`
- Validaciones en `core/validators.py`
- CSS en `core/styles.py`
- Cada página en `pages/`
