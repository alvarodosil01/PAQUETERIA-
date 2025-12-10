# Servicio Ingestador

## Descripción
El servicio `ingestador` es el punto de entrada de datos del sistema. Su función principal es simular la recepción de albaranes de proveedores en el almacén central.

## Funcionalidades
1.  **Inicialización de Datos Maestros**: Al arrancar, verifica y puebla las tablas `catalogo` (productos) y `tiendas` en la base de datos PostgreSQL `almacen`.
2.  **Generación de Albaranes**: Genera periódicamente albaranes de entrada con productos aleatorios del catálogo.
3.  **Publicación en Kafka**: Publica los albaranes generados en el topic configurado (por defecto `almacen`) para que sean procesados por otros servicios.
4.  **Control de Capacidad**: Verifica la capacidad del almacén (Límite: 5000 unidades) y detiene la generación de pedidos si se alcanza este máximo, reanudándola solo cuando se libera espacio (ventas).

## Tecnologías
- **Lenguaje**: Python 3.12
- **Librerías**:
    - `kafka-python-ng`: Para la producción de mensajes Kafka.
    - `Faker`: Para la generación de datos aleatorios (nombres de productos, direcciones, etc.).
    - `polars`: Para la manipulación eficiente de datos y carga inicial.
    - `adbc-driver-postgresql`: Para la conexión rápida a PostgreSQL.

## Configuración
Las siguientes variables de entorno configuran el servicio (definidas en `.env` y `docker-compose.yml`):

| Variable | Descripción | Valor por Defecto |
|----------|-------------|-------------------|
| `KAFKA_BOOTSTRAP_SERVERS` | Dirección de los brokers de Kafka | `kafka:29092` |
| `INGESTOR_TOPIC` | Topic donde se publican los albaranes | `almacen` |
| `INGESTOR_FREQ_MIN` | Frecuencia mínima de generación (segundos) | `1.0` |
| `INGESTOR_FREQ_MAX` | Frecuencia máxima de generación (segundos) | `5.0` |
| `NUM_TIENDAS` | Número de tiendas a generar en la inicialización | `800` |
| `ALMACEN_DB` | Nombre de la base de datos del almacén | `almacen` |
