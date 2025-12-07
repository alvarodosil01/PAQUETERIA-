# Servicio de Envíos a Tienda

## Descripción
El servicio `envio_tienda` simula la preparación y envío de mercancía desde el almacén central hacia las tiendas.

## Funcionalidades
1.  **Selección de Tienda**: Selecciona una tienda destino. Puede priorizar una tienda específica (`TARGET_STORE_ID`) para demostraciones.
2.  **Selección de Productos**: Consulta el `inventario` en PostgreSQL para seleccionar productos con stock disponible.
3.  **Decremento de Stock**: Realiza una transacción en PostgreSQL para decrementar el stock de los productos seleccionados, asegurando que no haya stock negativo.
4.  **Generación de Documento**: Crea un documento JSON con los detalles del envío (ID, tienda, líneas, estado).
5.  **Persistencia en MongoDB**: Guarda el documento del envío en la colección `envios` de MongoDB con estado `PREPARADO`.
6.  **Notificación**: Publica un evento en el topic `tienda` de Kafka para notificar que el envío está listo.

## Tecnologías
- **Lenguaje**: Python 3.12
- **Librerías**:
    - `psycopg2-binary`: Interacción con PostgreSQL.
    - `pymongo`: Interacción con MongoDB.
    - `kafka-python-ng`: Publicación de eventos.
    - `Faker`: Datos aleatorios.

## Configuración
| Variable | Descripción | Valor por Defecto |
|----------|-------------|-------------------|
| `ENVIO_TIENDA_FREQ_MIN` | Frecuencia mínima de envíos | `1.0` |
| `ENVIO_TIENDA_FREQ_MAX` | Frecuencia máxima de envíos | `5.0` |
| `TARGET_STORE_ID` | ID de tienda a priorizar (Demo) | `1` |
| `TIENDA_TOPIC` | Topic de notificación | `tienda` |
