import sqlite3

def anadir_tabla_categorias():
    """
    Añade la tabla 'categorias' para que los usuarios
    puedan gestionar sus propias categorías.
    """
    try:
        conexion = sqlite3.connect('portfolio.db')
        cursor = conexion.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS categorias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            tipo TEXT NOT NULL, -- 'Ingreso' o 'Gasto'
            nombre TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES usuarios (id)
        )
        """)
        print("✅ Tabla 'categorias' creada o ya existente.")

        conexion.commit()

    except Exception as e:
        print(f"❌ Ocurrió un error: {e}")
    finally:
        if conexion:
            conexion.close()

if __name__ == '__main__':
    anadir_tabla_categorias()