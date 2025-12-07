import os
import json
import time
import psycopg2
from kafka import KafkaConsumer
from prometheus_client import start_http_server, Counter

# Configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:29092')
TOPIC_NAME = os.getenv('INGESTOR_TOPIC', 'almacen')
DB_USER = os.getenv('ALMACEN_USER', 'almacen')
DB_PASSWORD = os.getenv('ALMACEN_PASSWORD', 'almacen123')
DB_HOST = os.getenv('POSTGRES_HOST', 'db')
DB_PORT = os.getenv('POSTGRES_PORT', '5432')
DB_NAME = os.getenv('ALMACEN_DB', 'almacen')

# Prometheus Metrics
MESSAGES_CONSUMED = Counter('recepcion_messages_consumed_total', 'Total number of messages consumed')
INVENTORY_UPDATES = Counter('recepcion_inventory_updates_total', 'Total number of inventory updates')
ERRORS_TOTAL = Counter('recepcion_errors_total', 'Total number of errors')

def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        dbname=DB_NAME,
        port=DB_PORT
    )

def process_message(message):
    print(f"Processing albaran: {message.get('id_albaran')}")
    lineas = message.get('lineas', [])
    
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        for linea in lineas:
            product_id = linea['product_id']
            cantidad = linea['cantidad']
            
            # Upsert logic
            # Insert si no existe, actualiza si existe
            upsert_query = """
            INSERT INTO inventario (product_id, cantidad, last_updated)
            VALUES (%s, %s, NOW())
            ON CONFLICT (product_id) 
            DO UPDATE SET 
                cantidad = inventario.cantidad + EXCLUDED.cantidad,
                last_updated = NOW();
            """
            cur.execute(upsert_query, (product_id, cantidad))
            INVENTORY_UPDATES.inc()
        
        conn.commit()
        cur.close()
        print(f"Updated inventory for {len(lineas)} items.")
        MESSAGES_CONSUMED.inc()

    except Exception as e:
        print(f"Error processing message: {e}")
        ERRORS_TOTAL.inc()
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

def main():
    print("Starting Reception Service...")
    
    # Start Prometheus HTTP server
    start_http_server(8000)
    print("Prometheus metrics exposed on port 8000")

    # Wait for DB to be ready
    while True:
        try:
            # Check connection only
            conn = get_db_connection()
            conn.close()
            print("DB Connection successful.")
            break
        except Exception as e:
            print(f"Waiting for DB... ({e})")
            time.sleep(5)

    # Wait for Kafka
    consumer = None
    while not consumer:
        try:
            consumer = KafkaConsumer(
                TOPIC_NAME,
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                auto_offset_reset='earliest',
                enable_auto_commit=True,
                group_id='recepcion-group',
                value_deserializer=lambda x: json.loads(x.decode('utf-8'))
            )
            print("Connected to Kafka!")
        except Exception as e:
            print(f"Waiting for Kafka... ({e})")
            time.sleep(5)

    print(f"Listening on topic: {TOPIC_NAME}")
    
    for message in consumer:
        try:
            process_message(message.value)
        except Exception as e:
            print(f"Error consuming message: {e}")
            ERRORS_TOTAL.inc()

if __name__ == "__main__":
    main()
