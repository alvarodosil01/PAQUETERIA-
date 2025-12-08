-- Inicialización de tablas para la base de datos 'almacen'
\c almacen
SET ROLE almacen;

CREATE TABLE IF NOT EXISTS catalogo (
    product_id INTEGER PRIMARY KEY,
    descripcion TEXT,
    peso FLOAT,
    precio DECIMAL(10, 2),
    coste DECIMAL(10, 2)
);

CREATE TABLE IF NOT EXISTS tiendas (
    store_id INTEGER PRIMARY KEY,
    nombre TEXT,
    direccion TEXT,
    ciudad TEXT,
    lat FLOAT,
    lon FLOAT
);

CREATE TABLE IF NOT EXISTS inventario (
    product_id INTEGER PRIMARY KEY,
    cantidad INTEGER NOT NULL DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_catalogo FOREIGN KEY (product_id) REFERENCES catalogo (product_id)
);

CREATE TABLE IF NOT EXISTS historial_recepciones (
    id SERIAL PRIMARY KEY,
    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    product_id INTEGER,
    cantidad INTEGER,
    coste_unitario DECIMAL(10, 2),
    coste_total DECIMAL(10, 2)
);

-- Inicialización de tablas para la base de datos 'tienda'
\c tienda
SET ROLE tienda;

CREATE TABLE IF NOT EXISTS tiendas (
    store_id INTEGER PRIMARY KEY,
    nombre TEXT,
    direccion TEXT,
    ciudad TEXT,
    lat FLOAT,
    lon FLOAT
);

CREATE TABLE IF NOT EXISTS albaran (
    id SERIAL PRIMARY KEY,
    mongo_id_envio UUID NOT NULL,
    fecha_recepcion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    estado VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS detalle_albaran (
    id SERIAL PRIMARY KEY,
    albaran_id INTEGER REFERENCES albaran(id),
    product_id INTEGER NOT NULL,
    cantidad INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS inventario_tienda (
    product_id INTEGER PRIMARY KEY,
    cantidad INTEGER NOT NULL DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS stock_en_camino (
    id SERIAL PRIMARY KEY,
    mongo_id_envio UUID NOT NULL,
    product_id INTEGER,
    cantidad INTEGER,
    fecha_salida TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_estimada TIMESTAMP
);

CREATE TABLE IF NOT EXISTS historial_ventas (
    id SERIAL PRIMARY KEY,
    id_articulo VARCHAR(50),
    store_id INTEGER,
    cantidad INTEGER,
    fecha DATE DEFAULT CURRENT_DATE,
    hora TIME DEFAULT CURRENT_TIME,
    lugar VARCHAR(100) DEFAULT 'Tienda Principal',
    precio_unitario DECIMAL(10, 2),
    ingreso_total DECIMAL(10, 2),
    coste_unitario DECIMAL(10, 2)
);
