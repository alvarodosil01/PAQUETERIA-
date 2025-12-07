import os
import time
import random
import uuid
import json
from datetime import datetime, timezone
import psycopg2
from pymongo import MongoClient
from faker import Faker
from kafka import KafkaProducer
from prometheus_client import start_http_server, Counter

# Configuration
DB_USER = os.getenv('ALMACEN_USER', 'almacen')
DB_PASSWORD = os.getenv('ALMACEN_PASSWORD', 'almacen123')
DB_HOST = os.getenv('POSTGRES_HOST', 'db')
DB_PORT = os.getenv('POSTGRES_PORT', '5432')
DB_NAME = os.getenv('ALMACEN_DB', 'almacen')

MONGO_USER = os.getenv('MONGO_INITDB_ROOT_USERNAME', 'admin')
MONGO_PASSWORD = os.getenv('MONGO_INITDB_ROOT_PASSWORD', 'admin123')
MONGO_HOST = os.getenv('MONGO_HOST', 'mongo')
MONGO_PORT = os.getenv('MONGO_PORT', '27017')

KAFKA_BOOTSTRAP_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:29092')
TIENDA_TOPIC = os.getenv('TIENDA_TOPIC', 'tienda')

FREQ_MIN = float(os.getenv('ENVIO_TIENDA_FREQ_MIN', '1.0'))
FREQ_MAX = float(os.getenv('ENVIO_TIENDA_FREQ_MAX', '5.0'))

TARGET_STORE_ID = os.getenv('TARGET_STORE_ID')

# Prometheus Metrics
SHIPMENTS_GENERATED = Counter('envio_tienda_shipments_generated_total', 'Total number of shipments generated')
MESSAGES_PRODUCED = Counter('envio_tienda_kafka_messages_produced_total', 'Total number of Kafka messages produced')
ERRORS_TOTAL = Counter('envio_tienda_errors_total', 'Total number of errors')

fake = Faker('es_ES')

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

def get_kafka_producer():
    return KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )

def get_random_store(cur):
    # If TARGET_STORE_ID is set, we want to prioritize it.
    # Let's say 50% chance to pick target store if set.
    if TARGET_STORE_ID and random.random() < 0.5:
        cur.execute("SELECT store_id, nombre, direccion, ciudad FROM tiendas WHERE store_id = %s", (TARGET_STORE_ID,))
        store = cur.fetchone()
        if store:
            return store

    cur.execute("SELECT store_id, nombre, direccion, ciudad FROM tiendas ORDER BY RANDOM() LIMIT 1")
    return cur.fetchone()

def get_available_products(cur):
    cur.execute("SELECT product_id, cantidad FROM inventario WHERE cantidad > 0 ORDER BY RANDOM() LIMIT 10")
    return cur.fetchall()

def generate_shipment(producer):
    conn = None
    try:
        conn = get_pg_connection()
        cur = conn.cursor()
        
        # 1. Select Store
        store = get_random_store(cur)
        if not store:
            print("No stores found. Waiting...")
            return
        
        store_id, store_name, store_addr, store_city = store
        
        # 2. Select Products
        products = get_available_products(cur)
        if not products:
            print("No inventory available. Waiting...")
            return
        
        # 3. Determine items to ship
        lineas = []
        num_items = random.randint(1, len(products))
        selected_products = random.sample(products, num_items)
        
        for p_id, p_qty in selected_products:
            # Ship random quantity up to available
            ship_qty = random.randint(1, p_qty)
            
            # Decrement stock (Transactional check)
            cur.execute("UPDATE inventario SET cantidad = cantidad - %s WHERE product_id = %s AND cantidad >= %s", (ship_qty, p_id, ship_qty))
            
            if cur.rowcount > 0:
                lineas.append({
                    "product_id": p_id,
                    "cantidad": ship_qty
                })
        
        if not lineas:
            conn.rollback()
            return

        # 4. Create Document
        shipment_id = str(uuid.uuid4())
        shipment = {
            "id_envio": shipment_id,
            "fecha_salida": datetime.now(timezone.utc).isoformat(),
            "tienda": {
                "id": store_id,
                "nombre": store_name,
                "direccion": f"{store_addr}, {store_city}"
            },
            "lineas": lineas,
            "estado": "PREPARADO",
            "trazabilidad": [
                {
                    "estado": "PREPARADO",
                    "fecha": datetime.now(timezone.utc).isoformat()
                }
            ]
        }
        
        # 5. Insert into MongoDB
        mongo_col = get_mongo_collection()
        mongo_col.insert_one(shipment)
        
        # 6. Commit Postgres transaction
        conn.commit()
        print(f"Generated shipment {shipment_id} for {store_name} (ID: {store_id}) with {len(lineas)} items.")
        print(f"[ALBARAN_SALIDA] {shipment_id}")
        SHIPMENTS_GENERATED.inc()

        # 7. Publish to Kafka
        if producer:
            message = {
                "id_albaran": shipment_id,
                "tienda_id": store_id
            }
            producer.send(TIENDA_TOPIC, message)
            producer.flush()
            print(f"Published to Kafka: {message}")
            MESSAGES_PRODUCED.inc()

    except Exception as e:
        print(f"Error generating shipment: {e}")
        ERRORS_TOTAL.inc()
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

def wait_for_tables():
    print("Waiting for tables 'tiendas' and 'inventario'...")
    while True:
        conn = None
        try:
            conn = get_pg_connection()
            cur = conn.cursor()
            
            cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'tiendas');")
            tiendas_exists = cur.fetchone()[0]
            
            cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'inventario');")
            inventario_exists = cur.fetchone()[0]
            
            if tiendas_exists and inventario_exists:
                print("Tables ready.")
                break
            else:
                print(f"Tables not ready (Tiendas: {tiendas_exists}, Inventario: {inventario_exists}). Retrying...")
                time.sleep(5)
        except Exception as e:
            print(f"Error checking tables: {e}")
            time.sleep(5)
        finally:
            if conn:
                conn.close()

def main():
    print("Starting Store Shipping Service...")
    
    # Start Prometheus HTTP server
    start_http_server(8000)
    print("Prometheus metrics exposed on port 8000")

    wait_for_tables()
    
    producer = None
    while not producer:
        try:
            producer = get_kafka_producer()
            print("Connected to Kafka!")
        except Exception as e:
            print(f"Waiting for Kafka... ({e})")
            time.sleep(5)

    while True:
        try:
            generate_shipment(producer)
            sleep_time = random.uniform(FREQ_MIN, FREQ_MAX)
            time.sleep(sleep_time)
        except Exception as e:
            print(f"Main loop error: {e}")
            ERRORS_TOTAL.inc()
            time.sleep(5)

if __name__ == "__main__":
    main()
