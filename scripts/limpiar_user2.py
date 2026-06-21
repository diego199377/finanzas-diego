"""Limpiar data sucia de user_id=2 antes de reimportar."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.db import get_connection


def main():
    print("\n=== LIMPIEZA DE DATA SUCIA — user_id=2 ===\n")

    confirmacion = input(
        "Esto borrará TODA la data de user_id=2 "
        "(transacciones + correos_procesados). "
        "¿Continuar? (escribe 'SI' para confirmar): "
    )
    if confirmacion.strip() != "SI":
        print("Cancelado.")
        return

    try:
        with get_connection() as conn:
            cur = conn.cursor()

            # Contar antes
            cur.execute("SELECT COUNT(*) FROM transacciones WHERE user_id = 2")
            tx_antes = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM correos_procesados WHERE user_id = 2")
            correos_antes = cur.fetchone()[0]

            print(f"\nAntes del borrado:")
            print(f"  - Transacciones user_id=2:      {tx_antes}")
            print(f"  - Correos procesados user_id=2: {correos_antes}")

            # Borrar en orden correcto (FK: correos → transacciones)
            cur.execute("DELETE FROM correos_procesados WHERE user_id = 2")
            cur.execute("DELETE FROM transacciones WHERE user_id = 2")

            # Verificar post-borrado
            cur.execute("SELECT COUNT(*) FROM transacciones WHERE user_id = 2")
            tx_despues = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM correos_procesados WHERE user_id = 2")
            correos_despues = cur.fetchone()[0]

            # Confirmar que user_id=1 está intacto
            cur.execute("SELECT COUNT(*) FROM transacciones WHERE user_id = 1")
            tx_user1 = cur.fetchone()[0]

            conn.commit()
            cur.close()

        print(f"\n[OK] Limpieza completada:")
        print(f"  - Transacciones user_id=2:             {tx_despues} (era {tx_antes})")
        print(f"  - Correos procesados user_id=2:        {correos_despues} (era {correos_antes})")
        print(f"  - Transacciones user_id=1 (INTACTAS):  {tx_user1}")

    except Exception as e:
        print(f"\n[ERROR] {e}")


if __name__ == "__main__":
    main()
