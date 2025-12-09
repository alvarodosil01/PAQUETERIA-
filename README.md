# Sistema de Logística y Transporte

Este proyecto implementa una simulación de un sistema de logística distribuido utilizando una arquitectura de microservicios basada en eventos.

## Arquitectura

El sistema consta de los siguientes componentes principales:

1.  **Ingestador**: Simula la entrada de mercancía al almacén central.
2.  **Recepción**: Actualiza el inventario central.
3.  **Envío a Tienda**: Genera envíos desde el almacén a las tiendas.
4.  **Recepción en Tienda**: Simula la recepción de mercancía en una tienda.

### Flujo de Datos
1.  `Ingestador` -> Kafka (`almacen`)
2.  Kafka (`almacen`) -> `Recepción` -> PostgreSQL (`inventario`)
3.  PostgreSQL (`inventario`) -> `Envío a Tienda` -> MongoDB (`envios`) + Kafka (`tienda`)
4.  Kafka (`tienda`) -> `Recepción en Tienda` -> PostgreSQL (`tienda`) + MongoDB (Update Status)

## Tecnologías

- **Contenedores**: Docker, Docker Compose
- **Mensajería**: Apache Kafka (KRaft mode)
- **Bases de Datos**:
    - PostgreSQL (Almacén y Tienda)
    - MongoDB (Documentos de envío)
- **Lenguaje**: Python 3.12

## Documentación de Servicios

| Servicio | Documentación |
|----------|---------------|
| Ingestador | [Ver Documentación](documents/ingestador.md) |
| Recepción | [Ver Documentación](documents/recepcion.md) |
| Envío a Tienda | [Ver Documentación](documents/envio_tienda.md) |
| Recepción en Tienda | [Ver Documentación](documents/recepcion_tienda.md) |
| Prometheus | [Ver Documentación](documents/prometheus.md) |
| Grafana | [Ver Documentación](documents/grafana.md) |

## Inicio Rápido

### Prerrequisitos
- Docker
- Docker Compose

### Ejecución
Para construir y arrancar todos los servicios (la configuración ya está incluida):

```bash
# Estando en la carpeta infraestructura
docker-compose up -d --build
```

### Verificación
- **Kafka UI**: Disponible en `http://localhost:8080`.
- **MongoDB**: Conexión en `mongodb://admin:admin123@localhost:27017`.
- **PostgreSQL**: Puerto `5432`.
- **Grafana**: Disponible en `http://localhost:3001`.

## Credenciales y Accesos

Para la demostración, se han configurado las siguientes credenciales por defecto:

| Servicio | URL / Host | Usuario | Contraseña | Notas |
|----------|------------|---------|------------|-------|
| **Grafana** | `http://localhost:3001` | `admin` | `admin` | Dashboard de monitorización |
| **Kafka UI** | `http://localhost:8080` | - | - | Visualización de topics y mensajes |
| **MongoDB** | `localhost:27017` | `admin` | `admin123` | Base de datos de envíos |
| **PostgreSQL** | `localhost:5432` | `almacen` | `almacen123` | DB Almacén (Base de datos: `almacen`) |
| **PostgreSQL** | `localhost:5432` | `tienda` | `tienda123` | DB Tienda (Base de datos: `tienda`) |

