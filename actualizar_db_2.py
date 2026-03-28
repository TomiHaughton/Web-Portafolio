import sqlite3

def anadir_tabla_finanzas():
    """
    Añade la tabla 'finanzas_personales' a la base de datos si no existe.
    """
    try:
        conexion = sqlite3.connect('portfolio.db')
        cursor = conexion.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS finanzas_personales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha DATE NOT NULL,
            tipo TEXT NOT NULL, -- 'Ingreso' o 'Gasto'
            categoria TEXT,
            monto REAL NOT NULL,
            descripcion TEXT
        )
        """)

        conexion.commit()
        print("✅ ¡Tabla 'finanzas_personales' añadida o ya existente!")

    except Exception as e:
        print(f"❌ Ocurrió un error: {e}")

    finally:
        if conexion:
            conexion.close()

if __name__ == '__main__':
    anadir_tabla_finanzas()