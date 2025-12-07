# Servicio de Visualización (Grafana)

## Descripción
Grafana se utiliza para visualizar las métricas recolectadas por Prometheus a través de dashboards interactivos.

## Funcionalidades
1.  **Visualización**: Muestra gráficos y estadísticas en tiempo real.
2.  **Provisionamiento Automático**:
    - **Datasources**: Configura automáticamente Prometheus como fuente de datos (`infraestructura/grafana/provisioning/datasources`).
    - **Dashboards**: Carga automáticamente los dashboards definidos en `infraestructura/grafana/dashboards`.

## Dashboards
El sistema incluye un dashboard principal llamado **"Transport System Dashboard"** que muestra:
- Tasas de ingestión vs recepción.
- Tasas de envío vs recepción en tienda.
- Contadores totales de mensajes y envíos.

## Acceso
- **URL**: `http://localhost:3000`
- **Usuario**: `admin`
- **Contraseña**: `admin`
