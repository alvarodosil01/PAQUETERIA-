import os
import json
import time
from datetime import datetime, timezone
import psycopg2
from pymongo import MongoClient
from kafka import KafkaConsumer
from prometheus_client import start_http_server, Counter, Gauge

# Configuration
DB_USER = os.getenv('TIENDA_USER', 'tienda')
DB_PASSWORD = os.getenv('TIENDA_PASSWORD', 'tienda123')
DB_HOST = os.getenv('POSTGRES_HOST', 'db')
DB_PORT = os.getenv('POSTGRES_PORT', '5432')
DB_NAME = os.getenv('TIENDA_DB', 'tienda')

MONGO_USER = os.getenv('MONGO_INITDB_ROOT_USERNAME', 'admin')
MONGO_PASSWORD = os.getenv('MONGO_INITDB_ROOT_PASSWORD', 'admin123')
MONGO_HOST = os.getenv('MONGO_HOST', 'mongo')
MONGO_PORT = os.getenv('MONGO_PORT', '27017')

KAFKA_BOOTSTRAP_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:29092')
TIENDA_TOPIC = os.getenv('TIENDA_TOPIC', 'tienda')

STORE_ID = int(os.getenv('STORE_ID', '1'))

# Prometheus Metrics
MESSAGES_CONSUMED = Counter('recepcion_tienda_messages_consumed_total', 'Total number of messages consumed')
SHIPMENTS_PROCESSED = Counter('recepcion_tienda_shipments_processed_total', 'Total number of shipments processed')
ERRORS_TOTAL = Counter('recepcion_tienda_errors_total', 'Total number of errors')

def get_pg_connection():
    return psycopg2.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        dbname=DB_NAME,
        port=DB_PORT
    )

def get_mongo_collection():
    client = MongoClient(f"mongodb://{MONGO_USER}:{MONGO_PASSWORD}@{MONGO_HOST}:{MONGO_PORT}/")
    db = client['transporte']
    return db['envios']

from threading import Thread
import random

# ... (Configuration remains same)

# Prometheus Metrics (Updated)
STOCKS_IN_TRANSIT = Counter('recepcion_tienda_stock_in_transit_total', 'Total stock items currently in transit')
TRANSIT_STOCK = Gauge('recepcion_tienda_transit_stock_level', 'Current items in transit')
STORE_STOCK = Gauge('recepcion_tienda_store_stock_level', 'Current items in store')

def check_arrivals():
    """Background task to simulate truck arrival"""
    print("Starting background arrival checker... (v2 DEBUG)")
    while True:
        conn = None
        try:
            print("Checking for arrivals...") 
            conn = get_pg_connection()
            cur = conn.cursor()
            
            # Check delay
            cutoff_time = "NOW() - INTERVAL '30 seconds'"
            
            cur.execute(f"""
                SELECT count(*) FROM stock_en_camino 
                WHERE fecha_salida < {cutoff_time}
            """)
            count = cur.fetchone()[0]
            print(f"[DEBUG] Count query result: {count}")
            
            if count > 0:
                print(f"[DEBUG] Found {count} items ready to arrive.")

            cur.execute(f"""
                SELECT id, mongo_id_envio, product_id, cantidad 
                FROM stock_en_camino 
                WHERE fecha_salida < {cutoff_time}
                LIMIT 100 -- Process in batches
            """)
            arriving_items = cur.fetchall()
            
            promoted_shipments = set()
            
            for row in arriving_items:
                row_id, mongo_id, p_id, qty = row
                
                # Add to inventory
                cur.execute("""
                    INSERT INTO inventario_tienda (product_id, cantidad, last_updated)
                    VALUES (%s, %s, NOW())
                    ON CONFLICT (product_id) 
                    DO UPDATE SET 
                        cantidad = inventario_tienda.cantidad + EXCLUDED.cantidad,
                        last_updated = NOW();
                """, (p_id, qty))
                
                # Remove from path
                cur.execute("DELETE FROM stock_en_camino WHERE id = %s", (row_id,))
                
                promoted_shipments.add(mongo_id)
            
            if arriving_items:
                conn.commit()
                print(f"[DEBUG] Moved {len(arriving_items)} items to inventory.")
            
            # Update MongoDB status
            if promoted_shipments:
                mongo_col = get_mongo_collection()
                current_time = datetime.now(timezone.utc).isoformat()
                
                for s_id in promoted_shipments:
                    # Check remaining items
                    cur.execute("SELECT COUNT(*) FROM stock_en_camino WHERE mongo_id_envio = %s", (s_id,))
                    count_remaining = cur.fetchone()[0]
                    
                    if count_remaining == 0:
                        mongo_col.update_one(
                            {"id_envio": s_id},
                            {
                                "$set": {"estado": "RECEPCIONADO"},
                                "$push": {
                                    "trazabilidad": {
                                        "estado": "RECEPCIONADO",
                                        "fecha": current_time
                                    }
                                }
                            }
                        )
                        print(f"[DEBUG] Shipment {s_id} fully ARRIVED.")
        
            # Update Metrics
            cur.execute("SELECT COALESCE(SUM(cantidad), 0) FROM stock_en_camino")
            transit_total = cur.fetchone()[0]
            TRANSIT_STOCK.set(transit_total)

            cur.execute("SELECT COALESCE(SUM(cantidad), 0) FROM inventario_tienda")
            store_total = cur.fetchone()[0]
            STORE_STOCK.set(store_total)

        except Exception as e:
            import traceback
            print(f"[ERROR] Arrival checker failed: {e}")
            traceback.print_exc()
            if conn: conn.rollback()
        finally:
            if conn: conn.close()
        
        time.sleep(5) # Check every 5 seconds

def process_shipment(id_albaran):
    print(f"Processing shipment {id_albaran} (In Transit)...")
    conn = None
    try:
        # 1. Fetch from MongoDB
        mongo_col = get_mongo_collection()
        shipment = mongo_col.find_one({"id_envio": id_albaran})
        
        if not shipment:
            print(f"Shipment {id_albaran} not found in MongoDB.")
            return

        # Idempotency check modified: allow if EN_TRANSITO? No, duplicate kafka message protection.
        if shipment.get('estado') in ['RECEPCIONADO', 'EN_TRANSITO']:
             print(f"Shipment {id_albaran} already processed/in-transit.")
             return

        lineas = shipment.get('lineas', [])
        
        # 2. Update Postgres (Stock en camino)
        conn = get_pg_connection()
        cur = conn.cursor()
        
        # Insert Albaran (Initial state)
        cur.execute(
            "INSERT INTO albaran (mongo_id_envio, estado) VALUES (%s, %s) RETURNING id",
            (id_albaran, 'EN_TRANSITO')
        )
        albaran_id = cur.fetchone()[0]
        
        for linea in lineas:
            p_id = linea['product_id']
            qty = linea['cantidad']
            
            # Insert Detail
            cur.execute(
                "INSERT INTO detalle_albaran (albaran_id, product_id, cantidad) VALUES (%s, %s, %s)",
                (albaran_id, p_id, qty)
            )
            
            # Insert into STOCK EN CAMINO
            cur.execute("""
                INSERT INTO stock_en_camino (mongo_id_envio, product_id, cantidad)
                VALUES (%s, %s, %s)
            """, (id_albaran, p_id, qty))
            
        conn.commit()
        
        # 3. Update MongoDB
        current_time = datetime.now(timezone.utc).isoformat()
        mongo_col.update_one(
            {"id_envio": id_albaran},
            {
                "$set": {"estado": "EN_TRANSITO"},
                "$push": {
                    "trazabilidad": {
                        "estado": "EN_TRANSITO",
                        "fecha": current_time
                    }
                }
            }
        )
        
        print(f"Shipment {id_albaran} marked as IN TRANSIT.")
        SHIPMENTS_PROCESSED.inc() 

    except Exception as e:
        print(f"Error processing shipment: {e}")
        ERRORS_TOTAL.inc()
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

def main():
    print(f"Starting Store Reception Service for Store ID: {STORE_ID}...")
    
    # Start Background thread for arrivals
    arrival_thread = Thread(target=check_arrivals, daemon=True)
    arrival_thread.start()
    
    # Start Prometheus HTTP server
    start_http_server(8000)
    print("Prometheus metrics exposed on port 8000")
    
    # Wait for DB
    # (Simplified wait logic assumed existing or using previous blocks)
    
    # Wait for Kafka
    consumer = None
    while not consumer:
        try:
            consumer = KafkaConsumer(
                TIENDA_TOPIC,
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                auto_offset_reset='latest',
                enable_auto_commit=True,
                group_id=f'tienda-{STORE_ID}-group',
                value_deserializer=lambda x: json.loads(x.decode('utf-8'))
            )
            print("Connected to Kafka!")
        except Exception as e:
            print(f"Waiting for Kafka... ({e})")
            time.sleep(5)
            
    print(f"Listening on topic: {TIENDA_TOPIC}")
    
    for message in consumer:
        try:
            data = message.value
            tienda_id = data.get('tienda_id')
            id_albaran = data.get('id_albaran')
            
            MESSAGES_CONSUMED.inc()
            
            if tienda_id == STORE_ID:
                process_shipment(id_albaran)
            else:
                # Ignore shipments for other stores
                pass
                
        except Exception as e:
            print(f"Error consuming message: {e}")
            ERRORS_TOTAL.inc()

if __name__ == "__main__":
    main()
