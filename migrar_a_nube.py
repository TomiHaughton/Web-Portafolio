import sqlite3
import psycopg2

# --- TUS DATOS DE SUPABASE (COMPLETAR AQUÍ) ---
DB_HOST = "aws-0-us-west-2.pooler.supabase.com"
DB_NAME = "postgres"
DB_USER = "postgres.kjbhhnmkjiyhwbgkznih"
DB_PASS = "tomihgt12"
DB_PORT = "6543"

def migrar_datos():
    # 1. Conectar a la base de datos local (SQLite)
    print("📂 Leyendo base de datos local...")
    conn_local = sqlite3.connect('portfolio.db')
    cursor_local = conn_local.cursor()

    # 2. Conectar a la base de datos nube (Supabase)
    print("☁️ Conectando a Supabase...")
    try:
        conn_nube = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASS, port=DB_PORT)
        cursor_nube = conn_nube.cursor()
    except Exception as e:
        print("❌ Error al conectar a Supabase. Revisa tus datos.")
        print(e)
        return

    # 3. Lista de tablas a migrar
    tablas = ['usuarios', 'operaciones', 'watchlist', 'finanzas_personales', 'categorias']

    for tabla in tablas:
        print(f"   --> Migrando tabla: {tabla}...")
        try:
            # Leer datos locales
            cursor_local.execute(f"SELECT * FROM {tabla}")
            filas = cursor_local.fetchall()

            if not filas:
                print(f"       (Tabla vacía, saltando)")
                continue

            # Obtener nombres de columnas
            nombres_columnas = [description[0] for description in cursor_local.description]
            cols_str = ', '.join(nombres_columnas)
            placeholders = ', '.join(['%s'] * len(nombres_columnas))

            # Insertar en nube
            query = f"INSERT INTO {tabla} ({cols_str}) VALUES ({placeholders})"
            
            # Ejecutar inserción masiva
            cursor_nube.executemany(query, filas)
            conn_nube.commit()
            print(f"       ✅ {len(filas)} registros copiados.")

        except Exception as e:
            print(f"       ❌ Error migrando {tabla}: {e}")
            conn_nube.rollback() # Deshacer si hay error en esta tabla

    print("\n✨ ¡Migración completada!")
    conn_local.close()
    conn_nube.close()

if __name__ == '__main__':
    migrar_datos()