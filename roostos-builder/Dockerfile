FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV CONTAINERD_ADDRESS=/run/containerd/containerd.sock
ENV CONTAINERD_NAMESPACE=roostos

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    git \
    tar \
    && rm -rf /var/lib/apt/lists/*

# Install nerdctl for direct containerd socket image building
ARG NERDCTL_VERSION=1.7.6
RUN curl -fsSL https://github.com/containerd/nerdctl/releases/download/v${NERDCTL_VERSION}/nerdctl-${NERDCTL_VERSION}-linux-amd64.tar.gz \
    | tar -xz -C /usr/local/bin nerdctl || true

# Install buildctl (BuildKit client)
ARG BUILDKIT_VERSION=0.13.2
RUN curl -fsSL https://github.com/moby/buildkit/releases/download/v${BUILDKIT_VERSION}/buildkit-v${BUILDKIT_VERSION}.linux-amd64.tar.gz \
    | tar -xz -C /usr/local/bin --strip-components=1 bin/buildctl || true

COPY roostos-builder-entrypoint.sh /usr/local/bin/roostos-builder-entrypoint.sh
RUN chmod +x /usr/local/bin/roostos-builder-entrypoint.sh

WORKDIR /workspace
ENTRYPOINT ["/usr/local/bin/roostos-builder-entrypoint.sh"]
