# Servicio de Monitorización (Prometheus)

## Descripción
Prometheus es el sistema de monitorización y alertas utilizado para recolectar métricas de los diferentes microservicios.

## Funcionalidades
1.  **Scraping de Métricas**: Recolecta periódicamente métricas expuestas por los servicios en el endpoint `/metrics` (puerto 8000).
2.  **Almacenamiento**: Guarda las series temporales de datos.

## Configuración
La configuración se encuentra en `infraestructura/prometheus/prometheus.yml`.

### Targets Configurados
| Job Name | Target | Descripción |
|----------|--------|-------------|
| `ingestador` | `ingestador:8000` | Métricas de producción de mensajes |
| `recepcion` | `recepcion:8000` | Métricas de consumo y actualización de inventario |
| `envio_tienda` | `envio_tienda:8000` | Métricas de generación de envíos |
| `recepcion_tienda` | `recepcion_tienda:8000` | Métricas de recepción en tienda |

## Métricas Clave
- `ingestador_messages_produced_total`: Total de mensajes generados.
- `recepcion_messages_consumed_total`: Total de mensajes procesados por recepción.
- `envio_tienda_shipments_generated_total`: Total de envíos creados.
- `recepcion_tienda_shipments_processed_total`: Total de envíos recibidos en tienda.

## Acceso
- **URL**: `http://localhost:9090`
