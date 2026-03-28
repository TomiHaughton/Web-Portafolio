# Importamos la librería para manejar la base de datos SQLite
import sqlite3

def crear_base_de_datos():
    """
    Esta función crea la base de datos y la tabla 'operaciones' si no existen.
    """
    try:
        # Conectamos a la base de datos (creará el archivo 'portfolio.db' si no existe)
        conexion = sqlite3.connect('portfolio.db')

        # Creamos un 'cursor', que es como el mouse para dar comandos a la base de datos
        cursor = conexion.cursor()

        # --- Comando para crear la tabla 'operaciones' ---
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS operaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha DATE NOT NULL,
            ticker TEXT NOT NULL,
            tipo TEXT NOT NULL,
            cantidad REAL NOT NULL,
            precio REAL NOT NULL
        )
        """)

        # Confirmamos los cambios en la base de datos
        conexion.commit()

        print("✅ ¡Base de datos 'portfolio.db' y tabla 'operaciones' creadas con éxito!")

    except Exception as e:
        # Si algo sale mal, imprimimos el error
        print(f"❌ Ocurrió un error: {e}")

    finally:
        # Nos aseguramos de cerrar la conexión, incluso si hubo un error
        if conexion:
            conexion.close()

# --- Ejecutamos la función para que haga su trabajo ---
if __name__ == '__main__':
    crear_base_de_datos()