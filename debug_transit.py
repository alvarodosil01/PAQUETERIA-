import psycopg2
import os
from datetime import datetime

# Configuración para conectar desde TU host (localhost)
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "tienda"
DB_USER = "tienda"
DB_PASSWORD = "tienda123"

def debug_transit():
    print("--- Diagnosticando Stock En Tránsito ---")
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            dbname=DB_NAME,
            port=DB_PORT
        )
        cur = conn.cursor()
        
        # 1. Verificar Hora DB
        cur.execute("SELECT NOW()::timestamp;")
        db_time = cur.fetchone()[0]
        print(f"Hora Base de Datos: {db_time}")
        print(f"Hora Local Tuya:    {datetime.now()}")
        
        # 2. Verificar Filas Pendientes
        cur.execute("SELECT count(*) FROM stock_en_camino")
        total = cur.fetchone()[0]
        print(f"Total filas en camino: {total}")
        
        # 3. Listar TODO para depurar
        print(f"\n--- Listado Completo de la Tabla ({total} filas) ---")
        cur.execute("SELECT id, fecha_salida, NOW() - fecha_salida as antiguedad FROM stock_en_camino ORDER BY id ASC")
        rows = cur.fetchall()
        for r in rows:
            rid, fsalida, diff = r
            status = "✅ LISTO" if diff.total_seconds() > 30 else "⏳ ESPERANDO"
            print(f"ID: {rid} | Salida: {fsalida} | Antigüedad: {diff} | Estado: {status}")

        # 4. Procesar Elegibles
        cur.execute("""
            SELECT count(*) FROM stock_en_camino 
            WHERE fecha_salida < NOW() - INTERVAL '30 seconds'
        """)
        eligible = cur.fetchone()[0]
        print(f"\nResumen: {eligible} filas listas para mover.")
        
        if eligible > 0:
            print("\nIntentando mover filas manualmente...")
            cur.execute("""
                SELECT id, mongo_id_envio, product_id, cantidad 
                FROM stock_en_camino 
                WHERE fecha_salida < NOW() - INTERVAL '30 seconds'
            """)
            items = cur.fetchall()
            
            for row in items:
                r_id, m_id, p_id, q = row
                print(f" - Moviendo Item {r_id} (Envio {m_id})...", end="")
                
                # Insertar en inventario
                cur.execute("""
                    INSERT INTO inventario_tienda (product_id, cantidad, last_updated)
                    VALUES (%s, %s, NOW())
                    ON CONFLICT (product_id) 
                    DO UPDATE SET 
                        cantidad = inventario_tienda.cantidad + EXCLUDED.cantidad,
                        last_updated = NOW();
                """, (p_id, q))
                
                # Borrar de camino
                cur.execute("DELETE FROM stock_en_camino WHERE id = %s", (r_id,))
                print(" OK")
            
            conn.commit()
            print("\n¡Movimiento completado con éxito!")
        else:
            print("\nNo hay filas elegibles para mover (quizás la hora DB viaja al futuro?)")

        conn.close()

    except Exception as e:
        print(f"\n[ERROR CRÍTICO]: {e}")

if __name__ == "__main__":
    debug_transit()
