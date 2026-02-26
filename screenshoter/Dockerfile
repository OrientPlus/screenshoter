FROM python:3.13-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    # Chromium runtime deps
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app


FROM base AS deps

COPY screenshoter/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt


FROM deps AS browsers

RUN playwright install chromium \
    && playwright install-deps chromium

FROM browsers AS final

COPY screenshoter/ ./screenshoter/
COPY rabbit/broker.py rabbit/models.py ./rabbit/
COPY common/ common/

RUN mkdir -p /runtime

CMD ["python", "-m", "screenshoter.main"]