# Servicio de Recepción

## Descripción
El servicio `recepcion` es responsable de procesar los albaranes de entrada generados por el ingestador y actualizar el inventario del almacén central.

## Funcionalidades
1.  **Consumo de Mensajes**: Escucha el topic de Kafka (`almacen`) donde se publican los nuevos albaranes.
2.  **Actualización de Inventario**: Para cada línea del albarán, actualiza la tabla `inventario` en la base de datos PostgreSQL `almacen`.
    - Si el producto ya existe, incrementa la cantidad (Upsert).
    - Si no existe, crea el registro.

## Tecnologías
- **Lenguaje**: Python 3.12
- **Librerías**:
    - `kafka-python-ng`: Para el consumo de mensajes Kafka.
    - `psycopg2-binary`: Para la conexión y ejecución de consultas en PostgreSQL.

## Configuración
| Variable | Descripción | Valor por Defecto |
|----------|-------------|-------------------|
| `KAFKA_BOOTSTRAP_SERVERS` | Dirección de los brokers de Kafka | `kafka:29092` |
| `INGESTOR_TOPIC` | Topic a escuchar | `almacen` |
| `ALMACEN_DB` | Base de datos del almacén | `almacen` |
