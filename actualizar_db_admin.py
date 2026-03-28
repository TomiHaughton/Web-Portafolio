import sqlite3

def anadir_columna_admin():
    """
    Añade la columna 'is_admin' a la tabla de usuarios si no existe.
    """
    try:
        conexion = sqlite3.connect('portfolio.db')
        cursor = conexion.cursor()

        # Añadimos la columna 'is_admin'
        # BOOLEAN DEFAULT 0 significa que por defecto, nadie es admin.
        cursor.execute("ALTER TABLE usuarios ADD COLUMN is_admin BOOLEAN DEFAULT 0")
        print("✅ Columna 'is_admin' añadida a la tabla 'usuarios'.")

        conexion.commit()

    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("⚠️  La columna 'is_admin' ya existía.")
        else:
            raise e
    except Exception as e:
        print(f"❌ Ocurrió un error: {e}")
    finally:
        if conexion:
            conexion.close()

if __name__ == '__main__':
    anadir_columna_admin()