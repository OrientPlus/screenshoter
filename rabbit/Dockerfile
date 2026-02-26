FROM rabbitmq:3.13-management AS base

RUN rabbitmq-plugins enable --offline rabbitmq_management

COPY rabbit/rabbitmq.conf /etc/rabbitmq/rabbitmq.conf

EXPOSE 15672 15672

HEALTHCHECK --interval=10s --timeout=8s --start-period=20s --retries=5 \
    CMD rabbitmq-diagnostics -q ping || exit 1