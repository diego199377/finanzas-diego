"""Migración v4 — Sistema de clasificación gasto / no_gasto / por_clasificar."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.db import get_connection


def main():
    print("\n=== MIGRACIÓN v4 — Sistema estado_gasto ===\n")

    try:
        with get_connection() as conn:
            cur = conn.cursor()

            # 1. Agregar columna si no existe (idempotente via DO $$)
            print("[1/4] Agregando columna estado_gasto...")
            cur.execute("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'transacciones'
                          AND column_name = 'estado_gasto'
                    ) THEN
                        ALTER TABLE transacciones
                        ADD COLUMN estado_gasto TEXT NOT NULL DEFAULT 'gasto'
                        CHECK (estado_gasto IN ('gasto', 'no_gasto', 'por_clasificar'));
                    END IF;
                END $$;
            """)
            print("    [OK] Columna creada (o ya existía)")

            # 2. Crear índice para queries rápidas
            print("[2/4] Creando índice...")
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_transacciones_estado_gasto
                ON transacciones(user_id, estado_gasto)
            """)
            print("    [OK] Índice creado")

            # 3. Transferencias a terceros → 'por_clasificar'
            print("[3/4] Marcando transferencias a terceros como 'por_clasificar'...")
            cur.execute(
                """
                UPDATE transacciones
                SET estado_gasto = 'por_clasificar'
                WHERE LOWER(descripcion) LIKE %s
                  AND estado_gasto = 'gasto'
                """,
                ("%transferencia a terceros%",),
            )
            afectadas = cur.rowcount
            print(f"    [OK] {afectadas} filas marcadas como 'por_clasificar'")

            # 4. Pagos CC propia y transferencias entre cuentas propias → 'no_gasto'
            print("[4/4] Marcando pagos CC propia y entre-cuentas como 'no_gasto'...")
            cur.execute(
                """
                UPDATE transacciones
                SET estado_gasto = 'no_gasto'
                WHERE (
                    LOWER(descripcion) LIKE %s
                    OR LOWER(descripcion) LIKE %s
                )
                AND estado_gasto = 'gasto'
                """,
                (
                    "%pago de tarjeta de cr%",
                    "%entre mis cuentas%",
                ),
            )
            no_gasto = cur.rowcount
            print(f"    [OK] {no_gasto} filas marcadas como 'no_gasto'")

            conn.commit()

            # Resumen final
            cur.execute("""
                SELECT estado_gasto,
                       COUNT(*)           AS cant,
                       ROUND(SUM(monto)::numeric, 2) AS suma
                FROM transacciones
                GROUP BY estado_gasto
                ORDER BY estado_gasto
            """)
            print("\n=== RESUMEN POST-MIGRACIÓN ===")
            for row in cur.fetchall():
                print(f"  {str(row[0]):20} : {row[1]:>4} filas · S/ {float(row[2]):>12,.2f}")

            cur.close()

        print("\n[OK] Migración v4 completada\n")

    except Exception as e:
        print(f"\n[ERROR] {e}\n")


if __name__ == "__main__":
    main()
