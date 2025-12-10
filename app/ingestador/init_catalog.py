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

def get_price_for_product(name):
    # Base prices loosely based on product type
    if 'Taladro' in name or 'Sierra' in name:
        return random.uniform(50.0, 150.0) # Expensive tools
    elif 'Martillo' in name or 'Llave' in name or 'Destornillador' in name:
        return random.uniform(10.0, 30.0) # Medium tools
    else:
        # Consumables (Tornillos, Tuercas, etc.)
        return random.uniform(0.10, 2.0)

def create_catalog_dataset(num_products=500):
    print(f"Generating {num_products} products...")
    data = []
    # Use a set of product types to generate somewhat related names
    product_types = ['Tornillo', 'Tuerca', 'Arandela', 'Clavo', 'Perno', 'Destornillador', 'Martillo', 'Llave', 'Sierra', 'Taladro']
    
    for i in range(num_products):
        p_type = random.choice(product_types)
        description = f"{p_type} {fake.word()} {fake.random_int(min=1, max=100)}mm"
        
        # Economics logic
        price = round(get_price_for_product(description), 2)
        # Cost is random 50-80% of price (50-70% margin)
        cost = round(price * random.uniform(0.3, 0.5), 2)
        
        data.append({
            "product_id": i + 1000, # Start IDs from 1000
            "descripcion": description,
            "peso": round(random.uniform(0.01, 5.0), 3),
            "precio": price,
            "coste": cost
        })
    
    df = pl.DataFrame(data)
    return df.with_columns([
        pl.col("product_id").cast(pl.Int32),
        pl.col("descripcion").cast(pl.Utf8),
        pl.col("peso").cast(pl.Float64),
        pl.col("precio").cast(pl.Float64),
        pl.col("coste").cast(pl.Float64)
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
        # Use sqlalchemy engine which is safer than adbc inside docker per experience
        df.write_database(
            table_name="tiendas",
            connection=DATABASE_URL,
            if_table_exists="append",
            engine="sqlalchemy"
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
                engine="sqlalchemy"
            )
            print("Stores replicated successfully to Tienda DB.")
        except Exception as e:
            print(f"Warning: Failed to replicate stores to Tienda DB: {e}")

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
            print(f"Table 'catalogo' already has {count} rows.")
            
            # --- MIGRATION CHECK ---
            try:
                # Check if 'precio' column exists
                columns_query = text("SELECT column_name FROM information_schema.columns WHERE table_name = 'catalogo'")
                with engine.connect() as conn:
                    existing_columns = [row[0] for row in conn.execute(columns_query)]
                
                if 'precio' not in existing_columns:
                    print("Missing columns 'precio'/'coste'. Applying migration...")
                    # 1. Add Columns
                    with engine.begin() as conn:
                        conn.execute(text("ALTER TABLE catalogo ADD COLUMN IF NOT EXISTS precio DECIMAL(10, 2)"))
                        conn.execute(text("ALTER TABLE catalogo ADD COLUMN IF NOT EXISTS coste DECIMAL(10, 2)"))
                    
                    print("Backfilling prices for existing products...")
                    # 2. Update Data
                    # We iterate and update. Using raw SQL for safety in migration.
                    with engine.connect() as conn:
                        products = conn.execute(text("SELECT product_id, descripcion FROM catalogo")).fetchall()
                        with conn.begin():
                            for pid, desc in products:
                                price = round(get_price_for_product(desc), 2)
                                cost = round(price * random.uniform(0.5, 0.8), 2)
                                conn.execute(
                                    text("UPDATE catalogo SET precio = :p, coste = :c WHERE product_id = :id"),
                                    {"p": price, "c": cost, "id": pid}
                                )
                    print("Migration complete. Prices updated.")
                else:
                    print("Schema is up to date.")
            except Exception as e:
                print(f"⚠️ MIGRATION ERROR: {e}")
                print("Continuing... the app might work but prices will be missing.")
            
            # --- REPLICATE EXISTING DATA TO TIENDA DB ---
            print("Syncing existing catalog to Tienda DB...")
            try:
                # Read from Almacen using Polars
                df = pl.read_database_uri("SELECT * FROM catalogo", DATABASE_URL, engine="connectorx")
                # Write to Tienda
                df.write_database(
                    table_name="catalogo",
                    connection=TIENDA_DATABASE_URL,
                    if_table_exists="replace",
                    engine="sqlalchemy"
                )
                print("Catalog synced to Tienda DB.")
            except Exception as e:
                # Fallback if connectorx missing, use sqlalchemy read
                 try:
                    df = pl.read_database("SELECT * FROM catalogo", connection=engine)
                    df.write_database(
                        table_name="catalogo",
                        connection=TIENDA_DATABASE_URL,
                        if_table_exists="replace",
                        engine="sqlalchemy"
                    )
                    print("Catalog synced to Tienda DB (fallback method).")
                 except Exception as ex:
                    print(f"Warning: Failed to sync catalog to Tienda DB: {ex}")

        else:
            print("Table 'catalogo' is empty. Creating dataset...")
            df = create_catalog_dataset()
            
            print("Writing to database...")
            df.write_database(
                table_name="catalogo",
                connection=DATABASE_URL,
                if_table_exists="append",
                engine="sqlalchemy"
            )
            print("Catalog initialized successfully in Almacen.")

            # --- REPLICATE TO TIENDA DB ---
            print("Replicating Catalog to Tienda database...")
            try:
                df.write_database(
                    table_name="catalogo",
                    connection=TIENDA_DATABASE_URL,
                    if_table_exists="replace", # We sync catalog to match Almacen
                    engine="sqlalchemy"
                )
                print("Catalog replicated successfully to Tienda DB.")
            except Exception as e:
                print(f"Warning: Failed to replicate catalog to Tienda DB: {e}")
            
        # Initialize Stores as well
        init_stores()

    except Exception as e:
        print(f"Error initializing catalog/stores: {e}")
        raise e

if __name__ == "__main__":
    init_catalog()
