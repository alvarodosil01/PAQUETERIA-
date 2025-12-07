# Servicio de Recepción en Tienda

## Descripción
El servicio `recepcion_tienda` simula la recepción de mercancía en una tienda específica.

## Funcionalidades
1.  **Inicialización**: Crea las tablas necesarias en la base de datos de la tienda (`tienda` en PostgreSQL) si no existen: `albaran`, `detalle_albaran`, `inventario_tienda`.
2.  **Escucha de Eventos**: Consume mensajes del topic `tienda` de Kafka.
3.  **Filtrado**: Procesa solo los mensajes destinados a su `STORE_ID`.
4.  **Procesamiento de Envío**:
    - Recupera el documento completo del envío desde MongoDB usando el ID recibido.
    - Inserta el albarán y sus líneas en la base de datos local de la tienda (PostgreSQL).
    - Actualiza el `inventario_tienda` incrementando el stock.
    - Actualiza el estado del documento en MongoDB a `ENTREGADO`.

## Tecnologías
- **Lenguaje**: Python 3.12
- **Librerías**:
    - `kafka-python-ng`: Consumo de eventos.
    - `pymongo`: Lectura y actualización en MongoDB.
    - `psycopg2-binary`: Gestión de base de datos local de tienda.

## Configuración
| Variable | Descripción | Valor por Defecto |
|----------|-------------|-------------------|
| `STORE_ID` | ID de la tienda que simula este servicio | `1` |
| `TIENDA_TOPIC` | Topic a escuchar | `tienda` |
| `TIENDA_DB` | Base de datos de la tienda | `tienda` |
