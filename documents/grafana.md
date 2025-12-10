# Servicio de Visualización (Grafana)

## Descripción
Grafana se utiliza para visualizar las métricas recolectadas por Prometheus a través de dashboards interactivos.

## Funcionalidades
1.  **Visualización**: Muestra gráficos y estadísticas en tiempo real.
2.  **Provisionamiento Automático**:
    - **Datasources**: Configura automáticamente Prometheus como fuente de datos (`infraestructura/grafana/provisioning/datasources`).
    - **Dashboards**: Carga automáticamente los dashboards definidos en `infraestructura/grafana/dashboards`.

## Dashboards

### Inventario Almacén
Dashboard estratégico para la gestión del inventario central.

#### Métricas Clave
1.  **⚠️ Nivel de Ocupación del Almacén (Gauge)**
    - **Propósito**: Visualizar la saturación del almacén respecto a su capacidad máxima (5000u).
    - **Utilidad**: Explica por qué se detiene la ingestión de nuevos productos (Zona Roja >= 4900u).

2.  **💎 Top 15 Productos con Mayor Valor Total**
    - **Propósito**: Ranking de productos basado en su valoración económica (`Cantidad * Coste`).
    - **Utilidad**: Permite priorizar la gestión de los activos más valiosos de la compañía.

3.  **📦 Stock por Categoría**
    - **Propósito**: Agregación de inventario por familias de productos (ej. Herramientas, Tornillería).
    - **Utilidad**: Ofrece una visión macro de la composición del stock.

## Acceso
- **URL**: `http://localhost:3001`
- **Usuario**: `admin`
- **Contraseña**: `admin`
