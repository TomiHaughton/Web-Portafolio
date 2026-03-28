import sqlite3

def anadir_tabla_watchlist():
    """
    Añade la tabla 'watchlist' a la base de datos si no existe.
    """
    try:
        conexion = sqlite3.connect('portfolio.db')
        cursor = conexion.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL UNIQUE,
            precio_objetivo REAL,
            notas TEXT
        )
        """)

        conexion.commit()
        print("✅ ¡Tabla 'watchlist' añadida o ya existente en la base de datos!")

    except Exception as e:
        print(f"❌ Ocurrió un error: {e}")

    finally:
        if conexion:
            conexion.close()

# Ejecutamos la función
if __name__ == '__main__':
    anadir_tabla_watchlist()