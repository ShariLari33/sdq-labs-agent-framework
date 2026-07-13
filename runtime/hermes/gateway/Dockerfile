# syntax=docker/dockerfile:1.6
ARG HERMES_VERSION=0.18.2
FROM python:3.11-slim

ARG HERMES_VERSION

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    bash \
    ca-certificates \
    curl \
    git \
    jq \
    tini \
  && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --no-cache-dir --upgrade pip \
  && python -m pip install --no-cache-dir "hermes-agent==${HERMES_VERSION}" "aiohttp==3.13.4" \
  && python -c "import hermes_cli.main" \
  && command -v hermes >/dev/null

RUN useradd --create-home --shell /bin/bash --uid 10001 hermes \
  && mkdir -p /home/hermes/.hermes /home/hermes/workspace /home/hermes/.config /home/hermes/.cache /home/hermes/.local/share \
  && chown -R hermes:hermes /home/hermes

COPY runtime/hermes/gateway/entrypoint.sh /usr/local/bin/hermes-gateway-entrypoint
RUN chmod 0755 /usr/local/bin/hermes-gateway-entrypoint

USER hermes
WORKDIR /home/hermes/workspace

ENV HOME=/home/hermes \
  HERMES_HOME=/home/hermes/.hermes \
  XDG_CONFIG_HOME=/home/hermes/.config \
  XDG_CACHE_HOME=/home/hermes/.cache \
  XDG_DATA_HOME=/home/hermes/.local/share \
  API_SERVER_ENABLED=true \
  API_SERVER_HOST=0.0.0.0 \
  API_SERVER_PORT=8642 \
  NO_COLOR=1

EXPOSE 8642

ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/hermes-gateway-entrypoint"]
