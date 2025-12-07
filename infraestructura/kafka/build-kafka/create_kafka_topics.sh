#!/bin/bash
set -e

BOOTSTRAP="${KAFKA_BOOTSTRAP_SERVERS:-localhost:9092}"

echo "==> [$(date '+%d/%m/%y %h:%m:%s')]  Esperando a que el puerto de Kafka esté abierto..."
host=$(echo "$BOOTSTRAP" | cut -d: -f1)
port=$(echo "$BOOTSTRAP" | cut -d: -f2)
until nc -z "$host" "$port"; do
    echo "   Puerto $port de Kafka no abierto aún, esperando 2s..."
    sleep 2
done

echo "==> [$(date '+%d/%m/%y %h:%m:%s')]  Puerto abierto. Esperando a que Kafka acepte comandos..."
MAX_WAIT=60
WAITED=0
until kafka-topics --bootstrap-server "$BOOTSTRAP" --list >/dev/null 2>&1; do
    if [ $WAITED -ge $MAX_WAIT ]; then
        echo "==> [$(date '+%d/%m/%y %h:%m:%s')]  [WARN] Timeout alcanzado, continuando..."
        break
    fi
    echo "==> [$(date '+%d/%m/%y %h:%m:%s')]  Kafka no accesible aún, esperando 5s..."
    sleep 5
    WAITED=$((WAITED+5))
done

echo "==> [$(date '+%d/%m/%y %h:%m:%s')] 1. Kafka está listo. Creando topics..."
echo "==> [$(date '+%d/%m/%y %h:%m:%s')]      - Crear topic _schemas primero (para Schema Registry)"
kafka-topics --create --if-not-exists --bootstrap-server "$BOOTSTRAP" \
    --partitions 1 --replication-factor 1 \
    --topic _schemas --config cleanup.policy=compact

echo "==> [$(date '+%d/%m/%y %h:%m:%s')]  2. Esperando a que el líder de _schemas esté disponible..."
until kafka-topics --bootstrap-server "$BOOTSTRAP" \
    --describe --topic _schemas | grep -q 'Leader: [0-9]'; do
    echo "==> [$(date '+%d/%m/%y %h:%m:%s')] Aún no hay líder, esperando 5s..."
    sleep 5
done
echo "==> [$(date '+%d/%m/%y %h:%m:%s')]  Líder asignado para _schemas"

echo "==> [$(date '+%d/%m/%y %h:%m:%s')]  3. Crear resto de topics necesarios..."
IFS=',' read -ra TOPICS <<< "$TOPICS_INICIALES"
for topic in "${TOPICS[@]}"; do
  echo "Creando topic: $topic"
  echo "==> [$(date '+%d/%m/%y %h:%m:%s')]      - Creando topic: ${topic}"
  kafka-topics --create --if-not-exists --bootstrap-server "$BOOTSTRAP" --partitions 3 --replication-factor 1 --topic "${topic}"
done

echo "==> [$(date '+%d/%m/%y %h:%m:%s')]  Topics disponibles:"
kafka-topics --list --bootstrap-server "$BOOTSTRAP"

echo "==> [$(date '+%d/%m/%y %h:%m:%s')]  Topics creados exitosamente"
