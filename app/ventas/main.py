
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
        
        # 1. Buscar productos con stock disponible
        cur.execute("SELECT product_id, cantidad FROM inventario_tienda WHERE cantidad > 0")
        productos = cur.fetchall()

        if not productos:
            print("[INFO] No hay stock para vender. Esperando reposición...")
            return

        # 2. Elegir producto aleatorio
        producto = random.choice(productos)
        prod_id = producto[0]
        stock_actual = producto[1]
        
        # 3. Determinar cantidad a vender (1 a 5, o lo que quede)
        cantidad_venta = random.randint(1, min(5, stock_actual))

        # 4. Actualizar inventario (Restar stock)
        cur.execute(
            "UPDATE inventario_tienda SET cantidad = cantidad - %s WHERE product_id = %s",
            (cantidad_venta, prod_id)
        )

        # 5. Registrar venta en historial
        cur.execute(
            """
            INSERT INTO historial_ventas (id_articulo, cantidad, lugar)
            VALUES (%s, %s, 'Tienda Principal')
            """,
            (str(prod_id), cantidad_venta)
        )

        conn.commit()
        
        # 6. Actualizar Métricas
        TOTAL_SALES.inc(cantidad_venta)
        print(f"[VENTA] Artículo {prod_id} | Cantidad: {cantidad_venta} | Stock restante: {stock_actual - cantidad_venta}")

    except Exception as e:
        print(f"[ERROR] Fallo en venta: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

# --- Main Loop ---
if __name__ == "__main__":
    print("Iniciando servicio de VENTAS...")
    start_http_server(8004) # Exponer métricas en puerto 8004
    
    while True:
        simular_venta()
        # Espera aleatoria entre ventas (ej. 2 a 8 segundos)
        time.sleep(random.uniform(2, 8))
