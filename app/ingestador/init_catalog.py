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

# Tienda Config
TIENDA_USER = os.getenv('TIENDA_USER', 'tienda')
TIENDA_PASSWORD = os.getenv('TIENDA_PASSWORD', 'tienda123')
TIENDA_DB_NAME = os.getenv('TIENDA_DB', 'tienda')

TIENDA_DATABASE_URL = f"postgresql://{TIENDA_USER}:{TIENDA_PASSWORD}@{DB_HOST}:{DB_PORT}/{TIENDA_DB_NAME}"

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

# Ciudades de España con sus coordenadas aproximadas
SPANISH_CITIES = [
    {"name": "Madrid", "lat": 40.4168, "lon": -3.7038},
    {"name": "Barcelona", "lat": 41.3851, "lon": 2.1734},
    {"name": "Valencia", "lat": 39.4699, "lon": -0.3763},
    {"name": "Sevilla", "lat": 37.3891, "lon": -5.9845},
    {"name": "Zaragoza", "lat": 41.6488, "lon": -0.8891},
    {"name": "Málaga", "lat": 36.7212, "lon": -4.4214},
    {"name": "Murcia", "lat": 37.9922, "lon": -1.1307},
    {"name": "Palma de Mallorca", "lat": 39.5696, "lon": 2.6502},
    {"name": "Las Palmas G.C.", "lat": 28.1235, "lon": -15.4363},
    {"name": "Bilbao", "lat": 43.2630, "lon": -2.9350},
    {"name": "Alicante", "lat": 38.3452, "lon": -0.4810},
    {"name": "Córdoba", "lat": 37.8882, "lon": -4.7794},
    {"name": "Valladolid", "lat": 41.6523, "lon": -4.7245},
    {"name": "Vigo", "lat": 42.2406, "lon": -8.7207},
    {"name": "Gijón", "lat": 43.5322, "lon": -5.6611},
    {"name": "A Coruña", "lat": 43.3623, "lon": -8.4115},
    {"name": "Vitoria-Gasteiz", "lat": 42.8467, "lon": -2.6716},
    {"name": "Granada", "lat": 37.1773, "lon": -3.5986},
    {"name": "Elche", "lat": 38.2669, "lon": -0.6983},
    {"name": "Oviedo", "lat": 43.3619, "lon": -5.8494}
]

def create_stores_dataset(num_stores=800):
    print(f"Generating {num_stores} stores in Spain...")
    data = []
    for i in range(num_stores):
        city = random.choice(SPANISH_CITIES)
        
        # Add jitter to coordinates so stores in the same city are spread out
        # +/- 0.05 degrees is roughly +/- 5km
        lat_jitter = random.uniform(-0.05, 0.05)
        lon_jitter = random.uniform(-0.05, 0.05)
        
        real_lat = city["lat"] + lat_jitter
        real_lon = city["lon"] + lon_jitter

        data.append({
            "store_id": i + 1,
            "nombre": f"Tienda {city['name']} {i+1}",
            "direccion": fake.address(),
            "ciudad": city["name"],
            "lat": real_lat,
            "lon": real_lon
        })
    df = pl.DataFrame(data)
    return df.with_columns([
        pl.col("store_id").cast(pl.Int32),
        pl.col("nombre").cast(pl.Utf8),
        pl.col("direccion").cast(pl.Utf8),
        pl.col("ciudad").cast(pl.Utf8),
        pl.col("lat").cast(pl.Float64),
        pl.col("lon").cast(pl.Float64)
    ])

def init_stores():
    print("Initializing stores...")
    try:
        engine = get_db_engine()
        
        # Check if stores table has data (IN ALMACEN)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM tiendas"))
            count = result.scalar()
            
        if count > 0:
            print(f"Table 'tiendas' already has {count} rows in Almacen DB. Skipping initialization.")
            return

        print("Table 'tiendas' is empty. Creating dataset...")
        num_stores = int(os.getenv('NUM_TIENDAS', '800'))
        df = create_stores_dataset(num_stores)
        
        print("Writing to Almacen database...")
        df.write_database(
            table_name="tiendas",
            connection=DATABASE_URL,
            if_table_exists="append",
            engine="adbc"
        )
        print("Stores initialized successfully in Almacen.")

        # --- REPLICATE TO TIENDA DB ---
        print("Replicating to Tienda database...")
        try:
             # We write the same DF to the other DB
            df.write_database(
                table_name="tiendas",
                connection=TIENDA_DATABASE_URL,
                if_table_exists="append",
                engine="adbc"
            )
            print("Stores replicated successfully to Tienda DB.")
        except Exception as e:
            print(f"Warning: Failed to replicate stores to Tienda DB: {e}")
            # We don't raise here to avoid failing the whole init if only the second DB part fails (though it shouldn't)

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
