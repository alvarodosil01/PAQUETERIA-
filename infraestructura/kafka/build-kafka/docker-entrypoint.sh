#!/bin/bash
set -e

KAFKA_DATA_DIR="/var/lib/kafka/data"
META_PROPERTIES="${KAFKA_DATA_DIR}/meta.properties"

echo "==> [$(date '+%d/%m/%y %h:%m:%s')]  Iniciando verificación de Kafka..."

clean_all_data() {
    echo "==> [$(date '+%d/%m/%y %h:%m:%s')]  Limpiando TODOS los datos de Kafka..."
    rm -rf "${KAFKA_DATA_DIR:?}/"*
    rm -rf /tmp/kafka-logs/*
    echo "==> [$(date '+%d/%m/%y %h:%m:%s')]  Limpieza completa terminada"
}

mkdir -p "$KAFKA_DATA_DIR"

if [ "$KAFKA_FORCE_CLEAN_META" = "true" ]; then
    clean_all_data
elif [ ! -f "$META_PROPERTIES" ]; then
    echo "==> [$(date '+%d/%m/%y %h:%m:%s')]  No se encontró meta.properties (nuevo arranque o datos borrados)"
else
    echo "==> [$(date '+%d/%m/%y %h:%m:%s')]  meta.properties detectado, conservando datos"
fi

echo "==> [$(date '+%d/%m/%y %h:%m:%s')]  Iniciando Kafka server..."
"$@" &
PID=$!

echo "==> [$(date '+%d/%m/%y %h:%m:%s')]  Kafka server iniciado con PID $PID"

echo "==> [$(date '+%d/%m/%y %h:%m:%s')]  Se lanza la script de creación de topics..."

create_kafka_topics

wait $PID

