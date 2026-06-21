"""Página de perfil del usuario — editar nombre y contraseña."""
import streamlit as st
from core.styles import get_tema, heading_ejecutivo
from core.auth import update_user_profile, get_full_user

if "user" not in st.session_state:
    st.error("Debes iniciar sesión para acceder a esta página.")
    st.stop()

USER_ID = st.session_state.user["id"]
p = get_tema()

heading_ejecutivo(
    label_uppercase="Configuración personal",
    titulo="Mi perfil",
    subtitulo="Edita tu información personal y de seguridad",
)

user = get_full_user(USER_ID)
if not user:
    st.error("No se pudieron cargar tus datos.")
    st.stop()

created_at = user.get("created_at")
if created_at and hasattr(created_at, "strftime"):
    created_str = created_at.strftime("%d/%m/%Y")
elif created_at:
    created_str = str(created_at)[:10]
else:
    created_str = "N/A"

st.html(f"""
<div class="card-ejecutivo" style="margin-bottom: 24px;">
    <div class="label-ejecutivo">Cuenta registrada</div>
    <div style="color: {p['texto_primario']}; font-size: 15px; font-weight: 500; margin-top: 4px;">{user['email']}</div>
    <div style="color: {p['texto_terciario']}; font-size: 11px; margin-top: 6px;">
        Miembro desde: {created_str}
    </div>
</div>
""")

# === Editar nombre ===
st.markdown("### Nombre para mostrar")
st.caption("Este es el nombre que aparece en tu sidebar y en pantallas. Puedes cambiarlo cuando quieras.")

with st.form("form_nombre"):
    nuevo_nombre = st.text_input(
        "Nombre",
        value=user.get("nombre_display") or "",
        placeholder="Ej: Diego, Jesús Sinche, Mi Dinero",
    )
    submit_nombre = st.form_submit_button("Guardar nombre")

if submit_nombre:
    if not nuevo_nombre.strip():
        st.error("El nombre no puede estar vacío.")
    else:
        success, msg = update_user_profile(USER_ID, nombre_display=nuevo_nombre)
        if success:
            st.session_state.user["nombre_display"] = nuevo_nombre.strip()
            st.success("Nombre actualizado. Recarga la página para ver el cambio en el sidebar.")
            st.rerun()
        else:
            st.error(msg)

st.divider()

# === Cambiar contraseña ===
st.markdown("### Cambiar contraseña")
st.caption("Por seguridad, necesitas ingresar tu contraseña actual antes de cambiarla.")

with st.form("form_password"):
    current_pwd = st.text_input("Contraseña actual", type="password")
    new_pwd = st.text_input("Nueva contraseña", type="password", help="Mínimo 8 caracteres")
    confirm_pwd = st.text_input("Confirmar nueva contraseña", type="password")
    submit_pwd = st.form_submit_button("Cambiar contraseña")

if submit_pwd:
    if not current_pwd or not new_pwd:
        st.error("Todos los campos son obligatorios.")
    elif new_pwd != confirm_pwd:
        st.error("Las contraseñas nuevas no coinciden.")
    else:
        success, msg = update_user_profile(
            USER_ID,
            new_password=new_pwd,
            current_password=current_pwd,
        )
        if success:
            st.success("Contraseña cambiada exitosamente.")
        else:
            st.error(msg)
