FROM blendergrid/blender:4.5.3

RUN ln -s /usr/local/blender/blender /usr/local/bin/blender \
    && chmod +x /usr/local/bin/blender

RUN set -eux; \
    printf 'Acquire::AllowInsecureRepositories "true";\nAcquire::AllowDowngradeToInsecureRepositories "true";\nAPT::Get::AllowUnauthenticated "true";\n' > /etc/apt/apt.conf.d/99insecure; \
    mkdir -p /tmp/apt-cache; \
    apt-get update -o Acquire::AllowInsecureRepositories=true -o Acquire::AllowDowngradeToInsecureRepositories=true; \
    apt-get -o Dir::Cache::archives=/tmp/apt-cache install -y --no-install-recommends --allow-unauthenticated ca-certificates gnupg apt wget; \
    rm -rf /tmp/apt-cache; \
    rm -f /etc/apt/apt.conf.d/99insecure

RUN set -eux; \
    mkdir -p /tmp/keys; \
    cd /tmp/keys; \
    wget -q https://deb.debian.org/debian/pool/main/d/debian-archive-keyring/debian-archive-keyring_2025.1_all.deb; \
    dpkg -i debian-archive-keyring_2025.1_all.deb; \
    rm -rf /tmp/keys

RUN sed -i 's|http://|https://|g' /etc/apt/sources.list.d/debian.sources

RUN apt-get update && apt-get install -y --no-install-recommends \
    unzip \
    curl \
    git \
    build-essential \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV BLENDERPY="/usr/local/blender/4.5/python/bin/python3.11"
ENV BLENDERPIP="/usr/local/blender/4.5/python/bin/pip"

RUN ${BLENDERPY} -m venv /app/venv

ENV PATH="/app/venv/bin:${PATH}"
ENV PYTHONPATH="/app/src"
ENV PYTHONUNBUFFERED=1

COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN /app/venv/bin/pip install --upgrade pip setuptools wheel \
    && /app/venv/bin/pip install --no-cache-dir -e .

RUN ${BLENDERPY} -m pip install --upgrade pip setuptools wheel \
    && ${BLENDERPY} -m pip install --no-cache-dir -e .

ENV APP_PORT=8000
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${APP_PORT}/v1/health || exit 1

ENTRYPOINT ["/bin/sh", "-c", "exec /app/venv/bin/uvicorn rigging_bridge.api:app --host 0.0.0.0 --port ${APP_PORT:-8000}"]
