FROM python:3.11-slim

WORKDIR /app

# Install system D-Bus libraries needed by dbus-next/python
RUN apt-get update && apt-get install -y --no-install-recommends \
    libdbus-1-dev \
    gcc \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copy SDK, bridge, and readme (required by hatchling)
COPY readme.md /app/readme.md
COPY roostos-sdk /app/roostos-sdk
COPY roostos-dns-technitium /app/roostos-dns-technitium

# Install packages
RUN pip install --no-cache-dir /app/roostos-sdk /app/roostos-dns-technitium

# Run the bridge
CMD ["python", "-m", "roostos_dns_technitium.bridge"]
