FROM confluentinc/cp-kafka:7.4.0

# Instalar netcat para verificación de puertos
USER root
RUN microdnf install -y nc && microdnf clean all

# Copiar scripts personalizados
COPY docker-entrypoint.sh /docker-entrypoint.sh
COPY create_kafka_topics.sh /usr/bin/create_kafka_topics

# Dar permisos de ejecución
RUN chmod +x /docker-entrypoint.sh /usr/bin/create_kafka_topics

# Volver al usuario original de Kafka
USER appuser

# Configurar entrypoint personalizado
ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["/etc/confluent/docker/run"]