"""Crea el primer usuario interactivamente desde consola."""
import sys
import getpass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.auth import create_user


def main():
    print("=== Crear primer usuario ===\n")

    email = input("Email: ").strip()
    if not email:
        print("Error: el email no puede estar vacío.")
        sys.exit(1)

    password = getpass.getpass("Contraseña: ")
    confirmar = getpass.getpass("Confirmar contraseña: ")

    if password != confirmar:
        print("Error: las contraseñas no coinciden.")
        sys.exit(1)

    if len(password) < 8:
        print("Error: la contraseña debe tener al menos 8 caracteres.")
        sys.exit(1)

    nbytes = len(password.encode("utf-8"))
    print(f"Tamaño de contraseña: {nbytes} bytes (máximo: 72).")
    if nbytes > 72:
        print(
            f"Tu contraseña tiene {nbytes} bytes, el máximo es 72 bytes "
            "(~72 caracteres ASCII). Por favor usa una contraseña más corta."
        )
        sys.exit(1)

    nombre_display = input("Nombre para mostrar (Enter para omitir): ").strip() or None

    try:
        user = create_user(email, password, nombre_display)
        print("\nUsuario creado exitosamente:")
        print(f"  ID            : {user['id']}")
        print(f"  Email         : {user['email']}")
        if user.get("nombre_display"):
            print(f"  Nombre display: {user['nombre_display']}")
        print("\nAhora puedes iniciar la app con: streamlit run app.py")
    except ValueError as e:
        print(f"\nError: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nError inesperado: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
