import os
import time
import json
import random
import uuid
from datetime import datetime, timezone
from kafka import KafkaProducer
from faker import Faker
import polars as pl
import init_catalog
from init_catalog import DATABASE_URL
from prometheus_client import start_http_server, Counter

# Prometheus Metrics
MESSAGES_PRODUCED = Counter('ingestador_messages_produced_total', 'Total number of messages produced')
ERRORS_TOTAL = Counter('ingestador_errors_total', 'Total number of errors')

# Configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:29092')
TOPIC_NAME = os.getenv('INGESTOR_TOPIC', 'almacen')
FREQ_MIN = float(os.getenv('INGESTOR_FREQ_MIN', '0.5'))
FREQ_MAX = float(os.getenv('INGESTOR_FREQ_MAX', '2.0'))

# Initialize Faker
fake = Faker('es_ES')

def load_schema():
    with open('schema.json', 'r') as f:
        return json.load(f)

def load_products():
    print("Loading products from catalog...")
    try:
        query = "SELECT * FROM catalogo"
        df = pl.read_database_uri(query=query, uri=DATABASE_URL, engine="adbc")
        products = df.to_dicts()
        print(f"Loaded {len(products)} products.")
        return products
    except Exception as e:
        print(f"Error loading products: {e}")
        return []

def generate_message(schema, products):
    # Helper to generate random lines
    num_lines = random.randint(1, 5)
    lines = []
    
    if not products:
        # Fallback if no products loaded (shouldn't happen if init works)
        print("Warning: No products available, using fallback generation.")
        for _ in range(num_lines):
            lines.append({
                "product_id": fake.random_int(min=1000, max=9999),
                "descripcion": fake.sentence(nb_words=3).replace('.', ''),
                "cantidad": fake.random_int(min=1, max=100),
                "peso": round(random.uniform(0.1, 50.0), 2)
            })
    else:
        # Use products from catalog
        selected_products = random.sample(products, k=min(len(products), num_lines))
def get_producer():
    return KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )

def generate_message(products_df):
    # Select random products using Polars
    num_items = random.randint(1, 5)
    selected_products = products_df.sample(n=num_items, with_replacement=True)
    
    lineas = []
    for row in selected_products.iter_rows(named=True):
        lineas.append({
            "product_id": row['product_id'],
            "cantidad": random.randint(1, 100)
        })

    message = {
        "id_albaran": fake.uuid4(),
        "fecha": fake.date_time_this_year().isoformat(),
        "proveedor": fake.company(),
        "lineas": lineas
    }
    return message

def main():
    print("Starting Ingestor...")
    
    # Start Prometheus HTTP server
    start_http_server(8000)
    print("Prometheus metrics exposed on port 8000")

    # Initialize Catalog and Stores
    init_catalog.init_catalog()
    
    # Load products for generation
    # We need to connect to DB to get products. 
    # For simplicity, we can re-use the logic from init_catalog or just connect here.
    # Let's assume init_catalog populated the DB and we can query it.
    # Or better, let's just use a simple query here.
    
    db_uri = f"postgresql://{os.getenv('ALMACEN_USER')}:{os.getenv('ALMACEN_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('ALMACEN_DB')}"
    
    try:
        products_df = pl.read_database_uri("SELECT product_id FROM catalogo", db_uri, engine='adbc')
        print(f"Loaded {len(products_df)} products from catalog.")
    except Exception as e:
        print(f"Error loading products: {e}")
        ERRORS_TOTAL.inc()
        return

    producer = None
    while not producer:
        try:
            producer = get_producer()
            print("Connected to Kafka!")
        except Exception as e:
            print(f"Waiting for Kafka... ({e})")
            ERRORS_TOTAL.inc()
            time.sleep(5)

    while True:
        try:
            msg = generate_message(products_df)
            producer.send(TOPIC_NAME, msg)
            producer.flush()
            print(f"Sent: {msg['id_albaran']}")
            MESSAGES_PRODUCED.inc()
            
            sleep_time = random.uniform(FREQ_MIN, FREQ_MAX)
            time.sleep(sleep_time)
        except Exception as e:
            print(f"Error sending message: {e}")
            ERRORS_TOTAL.inc()
            time.sleep(5)

if __name__ == "__main__":
    main()
