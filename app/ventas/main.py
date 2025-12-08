
import os
import time
import random
import psycopg2
from prometheus_client import start_http_server, Gauge, Counter

# --- Configuración ---
DB_HOST = os.getenv("POSTGRES_HOST", "db")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("TIENDA_DB", "tienda")
DB_USER = os.getenv("TIENDA_USER", "tienda")
DB_PASS = os.getenv("TIENDA_PASSWORD", "tienda123")
SALES_FREQ_MIN = float(os.getenv("SALES_FREQ_MIN", "0.5"))
SALES_FREQ_MAX = float(os.getenv("SALES_FREQ_MAX", "2.0"))

# --- Métricas Prometheus ---
TOTAL_SALES = Counter('ventas_total_count', 'Total de ventas realizadas')
SALES_REVENUE = Counter('ventas_revenue_euro', 'Ingresos totales (simulado)') # Futuro uso

# --- Conexión a BD ---
def get_db_connection():
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS
        )
        return conn
    except Exception as e:
        print(f"[ERROR] Conexión fallida: {e}")
        return None

# --- Lógica de Ventas ---
def simular_venta():
    conn = get_db_connection()
    if not conn:
        return

    try:
        cur = conn.cursor()
        
        # 1. Elegir una tienda aleatoria
        cur.execute("SELECT store_id FROM tiendas ORDER BY RANDOM() LIMIT 1")
        tienda = cur.fetchone()
        
        if not tienda:
             print("[INFO] No hay tiendas registradas.")
             return

        store_id = tienda[0]

        # 2. Buscar productos con stock disponible EN ESA TIENDA (Simplificación: Asumimos inventario global visualizado localmente o inventario por tienda real)
        # Nota: El esquema original tenía 'inventario_tienda' sin store_id, asumiendo una sola tienda o stock agregado.
        # Para hacerlo realista con el mapa, deberíamos tener inventario POR tienda.
        # Dado que el usuario pidió mapa de VENTAS, vamos a simular que la venta ocurre en esa tienda, aunque descontemos del stock "agregado" por ahora 
        # (para no refactorizar TODO el modelo de inventario ahora mismo, lo cual rompería 'recepcion_tienda' etc).
        
        cur.execute("SELECT product_id, cantidad FROM inventario_tienda WHERE cantidad > 0")
        productos = cur.fetchall()

        if not productos:
            # print("[INFO] No hay stock global para vender...")
            return

        # 3. Elegir producto aleatorio
        producto = random.choice(productos)
        prod_id = producto[0]
        stock_actual = producto[1]
        
        # 4. Determinar cantidad a vender
        cantidad_venta = random.randint(1, min(5, stock_actual))

        # 5. Actualizar inventario (Restar stock global)
        cur.execute(
            "UPDATE inventario_tienda SET cantidad = cantidad - %s WHERE product_id = %s",
            (cantidad_venta, prod_id)
        )

        # 6. Registrar venta en historial CON store_id
        cur.execute(
            """
            INSERT INTO historial_ventas (id_articulo, store_id, cantidad, lugar)
            VALUES (%s, %s, %s, 'Tienda ' || %s)
            """,
            (str(prod_id), store_id, cantidad_venta, str(store_id))
        )

        conn.commit()
        
        # 7. Actualizar Métricas
        TOTAL_SALES.inc(cantidad_venta)
        # print(f"[VENTA] Tienda {store_id} | Art {prod_id} | Qty {cantidad_venta}")

    except Exception as e:
        print(f"[ERROR] Fallo en venta: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

# --- Main Loop ---
if __name__ == "__main__":
    print("Iniciando servicio de VENTAS (Crazy Mode)...")
    start_http_server(8004) 
    
    while True:
        simular_venta()
        # Espera aleatoria entre ventas
        time.sleep(random.uniform(SALES_FREQ_MIN, SALES_FREQ_MAX))
