import sqlite3
import psycopg2

# --- TUS DATOS DE SUPABASE ---
DB_HOST = "aws-0-us-west-2.pooler.supabase.com"
DB_NAME = "postgres"
DB_USER = "postgres.kjbhhnmkjiyhwbgkznih"
DB_PORT = "6543"
DB_PASS = "tomihgt12" # <--- CONFIRMA QUE ESTA SEA TU CONTRASEÑA

def reparar_usuarios():
    print("🔧 Reparando migración de usuarios...")
    
    # 1. Conectar Local
    conn_local = sqlite3.connect('portfolio.db')
    cursor_local = conn_local.cursor()
    
    # 2. Conectar Nube
    try:
        conn_nube = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASS, port=DB_PORT)
        cursor_nube = conn_nube.cursor()
    except Exception as e:
        print("❌ Error de conexión:", e)
        return

    # 3. Leer usuarios locales
    cursor_local.execute("SELECT id, username, password, is_admin FROM usuarios")
    usuarios_locales = cursor_local.fetchall()

    print(f"   Encontrados {len(usuarios_locales)} usuarios para migrar.")

    # 4. Insertar en nube convirtiendo el 1/0 a True/False
    for u in usuarios_locales:
        u_id, u_name, u_pass, u_admin_int = u
        
        # Conversión manual de Entero a Booleano
        u_admin_bool = True if u_admin_int == 1 else False
        
        try:
            cursor_nube.execute(
                "INSERT INTO usuarios (id, username, password, is_admin) VALUES (%s, %s, %s, %s)",
                (u_id, u_name, u_pass, u_admin_bool)
            )
            print(f"   ✅ Usuario {u_name} migrado.")
        except Exception as e:
            print(f"   ⚠️ El usuario {u_name} ya existía o hubo un error: {e}")
            conn_nube.rollback()
    
    conn_nube.commit()
    print("\n✨ ¡Reparación de usuarios terminada!")
    conn_local.close()
    conn_nube.close()

if __name__ == '__main__':
    reparar_usuarios()