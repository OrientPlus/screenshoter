FROM python:3.13-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

FROM base AS deps

COPY storage/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt


FROM deps AS final

COPY storage/ ./storage/
COPY rabbit/broker.py rabbit/models.py ./rabbit/

RUN mkdir -p /runtime

CMD ["python", "-m", "storage.main"]