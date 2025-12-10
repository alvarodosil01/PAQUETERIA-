#!/usr/bin/env bash
set -euo pipefail

# Obtener el directorio base del script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Cambiar al directorio de infraestructura para que docker compose encuentre el .env
cd "$SCRIPT_DIR/infraestructura"

# Archivo de composición por defecto (rutas relativas desde infraestructura/)
COMPOSE_FILE="docker-compose.yml"
ENV_FILE=".env"

# Función para mostrar ayuda
mostrar_ayuda() {
    echo "Uso: $0 {start|stop|restart|logs|ps|clean|list|start-service|stop-service|restart-service|logs-service|rebuild-service|health}"
    echo ""
    echo "Comandos generales:"
    echo "  start         : Arranca toda la infraestructura (sin build, sólo up -d)"
    echo "  start-build   : Arranca toda la infraestructura (con build, up -d --build)"
    echo "  stop          : Detiene toda la infraestructura"
    echo "  restart       : Reinicia toda la infraestructura"
    echo "  logs          : Muestra los registros (logs) de todos los servicios"
    echo "  ps            : Muestra el estado de todos los contenedores"
    echo "  health        : Muestra el estado de salud (healthcheck) de los contenedores"
    echo "  clean         : Borra contenedores, imágenes y volúmenes del proyecto (peligroso)"
    echo "  clean-volumes  : Borra sólo los volúmenes persistentes del proyecto (más seguro)"
    echo "  list          : Lista los servicios en el orden de arranque definido en el YAML"
    echo ""
    echo "Comandos para servicios individuales:"
    echo "  start-service <nombre>   : Arranca un servicio específico"
    echo "  stop-service <nombre>    : Detiene un servicio específico"
    echo "  restart-service <nombre> : Reinicia un servicio específico"
    echo "  logs-service <nombre>    : Muestra los logs de un servicio específico"
    echo "  rebuild-service <nombre>   : Fuerza build y arranque de un servicio específico"
    echo ""
    echo "Ejemplos:"
    echo "  $0 start-service superset"
    echo "  $0 logs-service kafka"
    echo "  $0 restart-service flink-processor"
}

# ==========================================
# Funciones de Limpieza (limpia_todo.sh)
# ==========================================

leer_proyectos_desde_env() {
  local env_file="$ENV_FILE"
  local -a projs=()
  if [[ -f "$env_file" ]]; then
    # Extrae valores de la forma PROJECT_NAME=valor (ignora comentados)
    # Quita comillas y CRLF si los hubiera
    mapfile -t projs < <(
      awk -F= '/^[[:space:]]*PROJECT_NAME[[:space:]]*=/{print $2}' "$env_file" \
      | tr -d '"' | tr -d "'" | sed 's/\r$//' | awk 'NF' | sort -u
    )
  fi
  if [[ ${#projs[@]} -gt 0 ]]; then
    printf '%s\0' "${projs[@]}"
  fi
}

# Busca imágenes locales cuyo repositorio empiece por cualquiera de los prefijos dados
# Imprime IDs (separados por nulos)
recolectar_ids_por_prefijo() {
  local -a prefixes=("$@")
  [[ ${#prefixes[@]} -gt 0 ]] || return 0
  # Recorre todas las imágenes locales: repo tag id
  while IFS=' ' read -r repo tag id; do
    for p in "${prefixes[@]}"; do
      if [[ -n "$p" && "$repo" == "$p"* ]]; then
        printf '%s\0' "$id"
        break
      fi
    done
  done < <(docker images --format '{{.Repository}} {{.Tag}} {{.ID}}')
}

# Busca volúmenes locales cuyo nombre empiece por cualquiera de los prefijos dados
# Imprime nombres de volúmenes (separados por nulos)
recolectar_volumenes_por_prefijo() {
  local -a prefixes=("$@")
  [[ ${#prefixes[@]} -gt 0 ]] || return 0
  # Recorre todos los volúmenes locales
  while IFS=' ' read -r nombre; do
    for p in "${prefixes[@]}"; do
      if [[ -n "$p" && "$nombre" == "$p"* ]]; then
        printf '%s\0' "$nombre"
        break
      fi
    done
  done < <(docker volume ls -q)
}

ejecutar_limpieza() {
  if ! command -v docker >/dev/null 2>&1; then
    echo "ERROR: docker no está instalado o no está en el PATH." >&2
    exit 1
  fi

  # Comprobar si hay contenedores corriendo
  if [ -n "$(docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps -q)" ]; then
    echo "ERROR: Hay servicios en ejecución. Por favor, detenlos primero usando '$0 stop'." >&2
    exit 1
  fi

  echo "Eliminando contenedores y volúmenes..."
  # down --volumes elimina contenedores, redes y volúmenes definidos en el compose
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" down --volumes

  # 1) Intento principal: usar docker compose images --quiet
  if docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" images --quiet >/dev/null 2>&1; then
    printf 'Obteniendo imágenes con: docker compose -f "%s" --env-file "%s" images --quiet\n' "$COMPOSE_FILE" "$ENV_FILE"

    mapfile -t IDS < <(docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" images --quiet | awk 'NF' | sort -u)

    if [[ ${#IDS[@]} -gt 0 ]]; then
      echo "Encontradas ${#IDS[@]} imagen(es) asociadas a los servicios."
      for id in "${IDS[@]}"; do
        if docker image inspect "$id" >/dev/null 2>&1; then
          echo "Eliminando imagen: $id"
          docker rmi -f "$id" || true
        else
          echo "La imagen $id no existe localmente. Omitiendo."
        fi
      done
    else
      echo "No se listaron imágenes vía docker compose images. Probando análisis básico del YAML..."
    fi
  else
    echo "Aviso: docker compose images no está disponible o falló. Probando análisis básico del YAML..."
  fi

  # 2) Fallback: extraer nombres definidos en 'image:' del YAML
  echo "Buscando líneas 'image:' en $COMPOSE_FILE..."
  IMAGES=$(grep -E '^[[:space:]]*image:[[:space:]]+' "$COMPOSE_FILE" \
            | sed -E 's/^[[:space:]]*image:[[:space:]]+//g' \
            | tr -d '"' | tr -d "'" \
            | awk 'NF' | sort -u || true)

  if [[ -n "${IMAGES:-}" ]]; then
      echo "Eliminando imágenes declaradas con image: en $COMPOSE_FILE"
      for img in $IMAGES; do
        if docker image inspect "$img" >/dev/null 2>&1; then
          echo "Eliminando imagen: $img"
          docker rmi -f "$img" || true
        else
          echo "La imagen $img no existe localmente. Omitiendo."
        fi
      done
  fi

  # 3) Usamos el nombre del proyecto (definido en .env) para eliminar también imágenes
  mapfile -d '' -t PROJECTS < <(leer_proyectos_desde_env || true)
  printf 'Eliminando imágenes del proyecto: %s\n' "${PROJECTS[*]:-<no definido>}"
  if [[ ${#PROJECTS[@]} -gt 0 ]]; then
    mapfile -d '' -t ids_by_prefix < <(recolectar_ids_por_prefijo "${PROJECTS[@]}" || true)
    for id in "${ids_by_prefix[@]}"; do
      printf 'Eliminando imagen: %s\n' "${id}"
      docker rmi -f "$id" || true
    done
  fi

  # 4) Borrado de volúmenes asociados al proyecto
  printf 'Eliminando volúmenes del proyecto: %s\n' "${PROJECTS[*]:-<no definido>}"
  if [[ ${#PROJECTS[@]} -gt 0 ]]; then
    mapfile -d '' -t ids_by_prefix < <(recolectar_volumenes_por_prefijo "${PROJECTS[@]}" || true)
    for id in "${ids_by_prefix[@]}"; do
      printf 'Eliminando volumen: %s\n' "${id}"
      docker volume rm -f "$id" || true
    done
  fi
  
  printf 'Vamos a hacer un purgado de volúmenes no usados (dangling)...\n'
  docker volume prune -f || true

  printf 'Vamos a hacer un purgado de imágenes no usadas (dangling)...\n'
  docker image prune -f || true

  echo "Limpieza completada."
}

# ==========================================
# Funciones de Listado (lista_servicios_ordenados.sh)
# ==========================================

# Devuelve la lista de servicios (un nombre por línea)
obtener_servicios() {
    local f="$COMPOSE_FILE"
    if [[ ! -f "$f" ]]; then
        return 1
    fi

    # Se buscan el inicio y fin de la sección services:
    mapfile -t lineas < <(
        sed -nE '/^[^[:space:]]/{=;p;}' "$f" | sed 'N;s/\n/: /' | sed -n '/: *services:$/ {p; n; p; q}' | awk '{l=split($0,datos,":");print datos[1]}'
    )

    if [[ ${#lineas[@]} -ge 2 ]]; then
        inicio=$(( lineas[0] + 1 ))
        fin=$(( lineas[1] - 1 ))
        sed -n "${inicio},${fin}p" "$f" | sed -nE 's/^  ([^[:space:]]+):[[:space:]]*$/\1/p'
    fi
}

ejecutar_listado() {
    local f="$COMPOSE_FILE"
    if [[ ! -f "$f" ]]; then
        echo "Error: No se encuentra el archivo $f"
        exit 1
    fi

    # Se obtienen los servicios usando la función auxiliar
    if mapfile -t servicios < <(obtener_servicios) && [[ ${#servicios[@]} -gt 0 ]]; then
         printf "Leyendo %s\n" "$f" >&2
         printf "##########################################################\n" >&2
         printf "%s\n" "${servicios[@]}"
    else
        echo "No se pudo determinar la sección 'services' en $f o está vacía."
    fi
}

validar_servicio() {
    local servicio="$1"
    mapfile -t servicios_validos < <(obtener_servicios)
    
    local encontrado="no"
    for s in "${servicios_validos[@]}"; do
        if [[ "$s" == "$servicio" ]]; then
            encontrado="si"
            break
        fi
    done

    if [[ "$encontrado" == "no" ]]; then
        echo "Error: El servicio '$servicio' no existe en $COMPOSE_FILE."
        echo "Servicios disponibles:"
        printf "  - %s\n" "${servicios_validos[@]}"
        exit 1
    fi
}

# ==========================================
# Función Health Check
# ==========================================

ejecutar_health_check() {
    echo "=========================================="
    echo "Estado de Salud de los Contenedores"
    echo "=========================================="
    
    # Obtener lista de contenedores
    mapfile -t containers < <(docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps --quiet)
    
    if [[ ${#containers[@]} -eq 0 ]]; then
        echo "No hay contenedores en ejecución."
        return 0
    fi
    
    for container_id in "${containers[@]}"; do
        # Obtener nombre del contenedor
        container_name=$(docker inspect --format='{{.Name}}' "$container_id" | sed 's/^\/\(.*\)$/\1/')
        
        # Obtener estado general
        state=$(docker inspect --format='{{.State.Status}}' "$container_id")
        
        # Obtener estado de healthcheck si existe
        health=$(docker inspect --format='{{.State.Health.Status}}' "$container_id" 2>/dev/null || echo "no healthcheck")
        
        # Colorear salida según estado
        if [[ "$state" == "running" ]]; then
            echo "✓ $container_name: CORRIENDO (Health: $health)"
        else
            echo "✗ $container_name: $state (Health: $health)"
        fi
        
        # Mostrar detalles del healthcheck si existe
        if [[ "$health" != "no healthcheck" && "$health" != "" ]]; then
            failure_count=$(docker inspect --format='{{.State.Health.FailingStreak}}' "$container_id" 2>/dev/null || echo "0")
            log=$(docker inspect --format='{{json .State.Health.Log}}' "$container_id" 2>/dev/null)
            
            if [[ $failure_count -gt 0 ]]; then
                echo "  ⚠ Fallos consecutivos: $failure_count"
            fi
        fi
    done
    
    echo "=========================================="
}


# ==========================================
# Lógica Principal
# ==========================================

if [ $# -eq 0 ]; then
    mostrar_ayuda
    exit 1
fi

case "$1" in
    rebuild-service)
      if [ $# -lt 2 ]; then
        echo "Error: Debes especificar el nombre del servicio"
        echo "Uso: $0 rebuild-service <nombre_servicio>"
        echo ""
        echo "Servicios disponibles:"
        ejecutar_listado
        exit 1
      fi
      SERVICE_NAME="$2"
      validar_servicio "$SERVICE_NAME"
      echo "Forzando build y arranque de servicio: $SERVICE_NAME..."
      docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --build --force-recreate --no-deps "$SERVICE_NAME"
      echo "Servicio $SERVICE_NAME reconstruido y arrancado."
      ;;
  start)
    echo "Arrancando infraestructura..."
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d
    echo "Infraestructura arrancada."
    ;;
  start-build)
    echo "Arrancando infraestructura con build..."
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --build
    echo "Infraestructura arrancada con build."
    ;;
  stop)
    echo "Deteniendo infraestructura..."
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" down
    echo "Infraestructura detenida."
    ;;
  restart)
    echo "Reiniciando infraestructura..."
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" down
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --build
    echo "Infraestructura reiniciada."
    ;;
  logs)
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" logs -f
    ;;
  ps)
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps
    ;;
  health)
    ejecutar_health_check
    ;;
  clean)
    ejecutar_limpieza
    ;;
  clean-volumes)
    # Sólo borra volúmenes persistentes asociados al proyecto/compose
    if [ -n "$(docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps -q)" ]; then
      echo "ERROR: Hay servicios en ejecución. Por favor, detenlos primero usando '$0 stop'." >&2
      exit 1
    fi
    echo "Eliminando sólo volúmenes persistentes del proyecto..."
    mapfile -d '' -t PROJECTS < <(leer_proyectos_desde_env || true)
    printf 'Eliminando volúmenes del proyecto: %s\n' "${PROJECTS[*]:-<no definido>}"
    if [[ ${#PROJECTS[@]} -gt 0 ]]; then
      mapfile -d '' -t ids_by_prefix < <(recolectar_volumenes_por_prefijo "${PROJECTS[@]}" || true)
      for id in "${ids_by_prefix[@]}"; do
        printf 'Eliminando volumen: %s\n' "${id}"
        docker volume rm -f "$id" || true
      done
    fi
    printf 'Vamos a hacer un purgado de volúmenes no usados (dangling)...\n'
    docker volume prune -f || true
    echo "Limpieza de volúmenes completada."
    ;;
  list)
    ejecutar_listado
    ;;
  start-service)
    if [ $# -lt 2 ]; then
      echo "Error: Debes especificar el nombre del servicio"
      echo "Uso: $0 start-service <nombre_servicio>"
      echo ""
      echo "Servicios disponibles:"
      ejecutar_listado
      exit 1
    fi
    SERVICE_NAME="$2"
    validar_servicio "$SERVICE_NAME"
    echo "Arrancando servicio: $SERVICE_NAME..."
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --build "$SERVICE_NAME"
    echo "Servicio $SERVICE_NAME arrancado."
    ;;
  stop-service)
    if [ $# -lt 2 ]; then
      echo "Error: Debes especificar el nombre del servicio"
      echo "Uso: $0 stop-service <nombre_servicio>"
      echo ""
      echo "Servicios disponibles:"
      ejecutar_listado
      exit 1
    fi
    SERVICE_NAME="$2"
    validar_servicio "$SERVICE_NAME"
    echo "Deteniendo servicio: $SERVICE_NAME..."
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" stop "$SERVICE_NAME"
    echo "Servicio $SERVICE_NAME detenido."
    ;;
  restart-service)
    if [ $# -lt 2 ]; then
      echo "Error: Debes especificar el nombre del servicio"
      echo "Uso: $0 restart-service <nombre_servicio>"
      echo ""
      echo "Servicios disponibles:"
      ejecutar_listado
      exit 1
    fi
    SERVICE_NAME="$2"
    validar_servicio "$SERVICE_NAME"
    echo "Reiniciando servicio: $SERVICE_NAME..."
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" restart "$SERVICE_NAME"
    echo "Servicio $SERVICE_NAME reiniciado."
    ;;
  logs-service)
    if [ $# -lt 2 ]; then
      echo "Error: Debes especificar el nombre del servicio"
      echo "Uso: $0 logs-service <nombre_servicio>"
      echo ""
      echo "Servicios disponibles:"
      ejecutar_listado
      exit 1
    fi
    SERVICE_NAME="$2"
    validar_servicio "$SERVICE_NAME"
    echo "Mostrando logs de: $SERVICE_NAME..."
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" logs -f "$SERVICE_NAME"
    ;;
  *)
    mostrar_ayuda
    exit 1
    ;;
esac
