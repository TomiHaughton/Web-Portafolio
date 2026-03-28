import sqlite3

def actualizar_finanzas_moneda():
    try:
        conexion = sqlite3.connect('portfolio.db')
        cursor = conexion.cursor()
        # Añadimos columna moneda, por defecto asumimos ARS para gastos cotidianos
        cursor.execute("ALTER TABLE finanzas_personales ADD COLUMN moneda TEXT DEFAULT 'ARS'")
        print("✅ Columna 'moneda' añadida a finanzas_personales.")
        conexion.commit()
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("⚠️ La columna 'moneda' ya existía.")
        else:
            print(f"❌ Error: {e}")
    finally:
        conexion.close()

if __name__ == '__main__':
    actualizar_finanzas_moneda()