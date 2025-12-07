#!/usr/bin/env bash
set -euo pipefail

# Para que use lo binarios de PostgreSQL
export PATH="/usr/lib/postgresql/15/bin:/usr/local/bin:${PATH}"

# Se leen las variables de entorno
: "${PGDATA:=/data/postgres}"
: "${POSTGRES_HOST:=127.0.0.1}"
: "${POSTGRES_PORT:=5432}"
: "${POSTGRES_USER:?Falta POSTGRES_USER}"
: "${POSTGRES_PASSWORD:?Falta POSTGRES_PASSWORD}"

: "${ALMACEN_DB:?Falta ALMACEN_DB}"
: "${ALMACEN_USER:?Falta ALMACEN_USER}"
: "${ALMACEN_PASSWORD:?Falta ALMACEN_PASSWORD}"

: "${TIENDA_DB:?Falta TIENDA_DB}"
: "${TIENDA_USER:?Falta TIENDA_USER}"
: "${TIENDA_PASSWORD:?Falta TIENDA_PASSWORD}"

: "${LOGS_DB:=logsdb}"
: "${LOGS_USER:=logs}"
: "${LOGS_PASSWORD:=logs123}"


LOCKFILE="/tmp/.pginit.done"

echo "[PG INIT] ======================================="
echo "[PG INIT] Configurando base de datos postgresql"
echo "[PG INIT] ======================================="

# Evita doble ejecución 
if [ -f "$LOCKFILE" ]; then
  echo "[PG INIT] Ya ejecutado anteriormente. Saliendo."
  exit 0
fi

echo "[PG INIT] Esperando a PostgreSQL en ${POSTGRES_HOST}:${POSTGRES_PORT}..."
ready=0
for i in {1..120}; do
  # Usar socket local sin -h para evitar problemas de autenticación TCP
  if pg_isready -p "$POSTGRES_PORT" >/dev/null 2>&1; then
    echo "[PG INIT] PostgreSQL está listo."
    ready=1
    break
  fi
  echo "[PG INIT] Intento $i: PostgreSQL no listo aún, esperando 1s..."
  sleep 1
done
if [ "$ready" -ne 1 ]; then
  echo "[PG INIT][ERROR] PostgreSQL no respondió a tiempo." >&2
  exit 1
fi

# Esperar adicional para asegurar que está completamente listo
sleep 2

PGDATA_DIR="${PGDATA}"
echo "[PG INIT] Carpeta de trabajo para postgresql: ${PGDATA_DIR}"

# 1) Asegurar password del superusuario usando SOCKET LOCAL (sin -h)
echo "[PG INIT] Asegurando contraseña del superusuario '${POSTGRES_USER}' vía socket local..."
psql -d postgres -v ON_ERROR_STOP=1 <<-EOSQL
DO \$\$
BEGIN
  EXECUTE format('ALTER USER %I WITH PASSWORD %L', '${POSTGRES_USER}', '${POSTGRES_PASSWORD}');
END
\$\$;
EOSQL
echo "[PG INIT] Fijada contraseña del superusuario '${POSTGRES_USER}'"

# Resuelve la ruta real de pg_hba.conf preguntando al servidor 
echo "[PG_INIT] Carpeta de datos ${PGDATA_DIR}"
HBA_FILE=$(psql -Atd postgres -c "SHOW hba_file;" || echo "${PGDATA_DIR}/pg_hba.conf")

# Socket local no requiere contraseña

create_role_and_db () {
  local db_name="$1" role_name="$2" role_pass="$3"

  echo "[PG INIT] Creando rol '${role_name}' (si no existe) ..."
  psql -d postgres -v ON_ERROR_STOP=1 <<-EOSQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '${role_name}') THEN
    EXECUTE format('CREATE ROLE %I LOGIN PASSWORD %L', '${role_name}', '${role_pass}');
  END IF;
END
\$\$;
EOSQL

  echo "[PG INIT] Creando base de datos '${db_name}' con owner '${role_name}' (si no existe)..."
  # 1) ¿Existe la BD?
  if ! psql -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='${db_name}'" | grep -q 1; then
    # 2) Si no existe, se crea fuera de transacción
    psql -d postgres -v ON_ERROR_STOP=1 \
      -c "CREATE DATABASE \"${db_name}\" OWNER \"${role_name}\""
  else
    # 3) Si existe, se asegura el owner
    current_owner=$(psql -d postgres -tAc \
      "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname='${db_name}'")
    if [ "$current_owner" != "${role_name}" ]; then
      # Cierra conexiones y cambia owner
      psql -d postgres -v ON_ERROR_STOP=1 \
        -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='${db_name}' AND pid <> pg_backend_pid()"
      psql -d postgres -v ON_ERROR_STOP=1 \
        -c "ALTER DATABASE \"${db_name}\" OWNER TO \"${role_name}\""
    fi
  fi
}

# Crea esquema propio para cada base de datos, fija search_path y bloquea creación en public
configure_db_schema () {
  local db_name="$1" schema_name="$2" db_user="$3"

  echo "[PG INIT] Configurando esquema '${schema_name}' en BD '${db_name}' para usuario '${db_user}'..."

  # 1) Crear esquema (si no existe) y asignar propietario
  psql -d "${db_name}" -v ON_ERROR_STOP=1 \
    -c "CREATE SCHEMA IF NOT EXISTS \"${schema_name}\" AUTHORIZATION \"${db_user}\";"

  # 2) Evitar creación en 'public' (idempotente)
  psql -d "${db_name}" -v ON_ERROR_STOP=1 \
    -c "REVOKE CREATE ON SCHEMA public FROM PUBLIC;"

  # 3) Fijar search_path del usuario en esa BD
  psql -d "${db_name}" -v ON_ERROR_STOP=1 \
    -c "ALTER ROLE \"${db_user}\" IN DATABASE \"${db_name}\" SET search_path = \"${schema_name}\", public, pg_temp;"

  # 4) Default privileges para que el propio usuario tenga permisos en lo que cree
  psql -d "${db_name}" -v ON_ERROR_STOP=1 \
    -c "ALTER DEFAULT PRIVILEGES FOR ROLE \"${db_user}\" IN SCHEMA \"${schema_name}\" GRANT USAGE ON SEQUENCES TO \"${db_user}\";"
  psql -d "${db_name}" -v ON_ERROR_STOP=1 \
    -c "ALTER DEFAULT PRIVILEGES FOR ROLE \"${db_user}\" IN SCHEMA \"${schema_name}\" GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO \"${db_user}\";"
}

# Base de datos de tienda
create_role_and_db "${TIENDA_DB}"   "${TIENDA_USER}"   "${TIENDA_PASSWORD}" 
# Base de datos de almacén
create_role_and_db "${ALMACEN_DB}"   "${ALMACEN_USER}"   "${ALMACEN_PASSWORD}"
# Tracking logs jobs
create_role_and_db "${LOGS_DB}"   "${LOGS_DB_USER}"   "${LOGS_DB_PASSWORD}"

echo "[PG INIT] ======================================="
echo "[PG INIT] Configurando esquemas y permisos"
echo "[PG INIT] ======================================="

# Cambiamos el esquema por defecto en las bases de datos del Lakehouse
configure_db_schema "${ALMACEN_DB}"   "${ALMACEN_USER}"   "${ALMACEN_USER}"
configure_db_schema "${TIENDA_DB}"   "${TIENDA_USER}"   "${TIENDA_USER}"
configure_db_schema "${LOGS_DB}"   "${LOGS_DB_USER}"   "${LOGS_DB_USER}"

touch "$LOCKFILE"
echo "[PG INIT] ======================================="
echo "[PG INIT] ✓ Inicialización completada"
echo "[PG INIT] ======================================="
echo "[PG INIT] Bases de datos creadas:"
echo "[PG INIT]   LAKEHOUSE:"
echo "[PG INIT]     • ${TIENDA_DB} (usuario: ${TIENDA_USER})"
echo "[PG INIT]     • ${ALMACEN_DB} (usuario: ${ALMACEN_USER})"
echo "[PG INIT]     • ${LOGS_DB} (usuario: ${LOGS_DB_USER})"
echo "[PG INIT] ======================================="