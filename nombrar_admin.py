import sqlite3

def hacer_admin(username):
    """
    Busca un usuario por su nombre y le da permisos de administrador.
    """
    try:
        conexion = sqlite3.connect('portfolio.db')
        cursor = conexion.cursor()

        # Buscamos al usuario y actualizamos su estado de is_admin a 1 (verdadero)
        cursor.execute("UPDATE usuarios SET is_admin = 1 WHERE username = ?", (username,))

        # Verificamos si la operación afectó a alguna fila
        if cursor.rowcount == 0:
            print(f"❌ Error: No se encontró ningún usuario con el nombre '{username}'.")
        else:
            conexion.commit()
            print(f"✅ ¡Éxito! El usuario '{username}' ahora es administrador.")

    except Exception as e:
        print(f"❌ Ocurrió un error: {e}")
    finally:
        if conexion:
            conexion.close()

if __name__ == '__main__':
    # Pedimos al usuario que ingrese el nombre de usuario
    nombre_usuario = input("Ingresa el nombre de usuario que quieres hacer administrador: ")
    if nombre_usuario:
        hacer_admin(nombre_usuario)
    else:
        print("No se ingresó un nombre de usuario.")