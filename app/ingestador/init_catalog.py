import os
import polars as pl
from sqlalchemy import create_engine, inspect, text
from faker import Faker
import random

# Configuration
DB_USER = os.getenv('ALMACEN_USER', 'almacen')
DB_PASSWORD = os.getenv('ALMACEN_PASSWORD', 'almacen123')
DB_HOST = os.getenv('POSTGRES_HOST', 'db')
DB_PORT = os.getenv('POSTGRES_PORT', '5432')
DB_NAME = os.getenv('ALMACEN_DB', 'almacen')

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

fake = Faker('es_ES')

def get_db_engine():
    return create_engine(DATABASE_URL)

def check_catalog_exists(engine):
    inspector = inspect(engine)
    return inspector.has_table("catalogo")

def create_catalog_dataset(num_products=500):
    print(f"Generating {num_products} products...")
    data = []
    # Use a set of product types to generate somewhat related names
    product_types = ['Tornillo', 'Tuerca', 'Arandela', 'Clavo', 'Perno', 'Destornillador', 'Martillo', 'Llave', 'Sierra', 'Taladro']
    
    for i in range(num_products):
        p_type = random.choice(product_types)
        description = f"{p_type} {fake.word()} {fake.random_int(min=1, max=100)}mm"
        
        data.append({
            "product_id": i + 1000, # Start IDs from 1000
            "descripcion": description,
            "peso": round(random.uniform(0.01, 5.0), 3)
        })
    
    df = pl.DataFrame(data)
    return df.with_columns([
        pl.col("product_id").cast(pl.Int32),
        pl.col("descripcion").cast(pl.Utf8),
        pl.col("peso").cast(pl.Float64)
    ])

def create_stores_dataset(num_stores=800):
    print(f"Generating {num_stores} stores...")
    data = []
    for i in range(num_stores):
        data.append({
            "store_id": i + 1,
            "nombre": f"Tienda {fake.city()}",
            "direccion": fake.address(),
            "ciudad": fake.city()
        })
    df = pl.DataFrame(data)
    return df.with_columns([
        pl.col("store_id").cast(pl.Int32),
        pl.col("nombre").cast(pl.Utf8),
        pl.col("direccion").cast(pl.Utf8),
        pl.col("ciudad").cast(pl.Utf8)
    ])

def init_stores():
    print("Initializing stores...")
    try:
        engine = get_db_engine()
        
        # Check if stores table has data
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM tiendas"))
            count = result.scalar()
            
        if count > 0:
            print(f"Table 'tiendas' already has {count} rows. Skipping initialization.")
            return

        print("Table 'tiendas' is empty. Creating dataset...")
        num_stores = int(os.getenv('NUM_TIENDAS', '800'))
        df = create_stores_dataset(num_stores)
        
        print("Writing to database...")
        df.write_database(
            table_name="tiendas",
            connection=DATABASE_URL,
            if_table_exists="append",
            engine="adbc"
        )
        print("Stores initialized successfully.")

    except Exception as e:
        print(f"Error initializing stores: {e}")
        raise e

def init_catalog():
    print("Initializing catalog...")
    try:
        engine = get_db_engine()
        
        # Check if catalog table has data
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM catalogo"))
            count = result.scalar()
            
        if count > 0:
            print(f"Table 'catalogo' already has {count} rows. Skipping initialization.")
        else:
            print("Table 'catalogo' is empty. Creating dataset...")
            df = create_catalog_dataset()
            
            print("Writing to database...")
            df.write_database(
                table_name="catalogo",
                connection=DATABASE_URL,
                if_table_exists="append",
                engine="adbc"
            )
            print("Catalog initialized successfully.")
            
        # Initialize Stores as well
        init_stores()

    except Exception as e:
        print(f"Error initializing catalog/stores: {e}")
        raise e

if __name__ == "__main__":
    init_catalog()
