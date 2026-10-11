FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    dpkg-dev \
    git \
    file \
    python3 \
    && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | sh

RUN git config --global --add safe.directory '*'

ENV PATH="/root/.local/bin:$PATH"

WORKDIR /workspace
