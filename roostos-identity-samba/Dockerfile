FROM python:3.11-slim

WORKDIR /app

# Install system D-Bus and Samba/LDAP client utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    libdbus-1-dev \
    gcc \
    pkg-config \
    samba-client \
    && rm -rf /var/lib/apt/lists/*

# Copy SDK, bridge code, and root readme
COPY readme.md /app/readme.md
COPY roostos-sdk /app/roostos-sdk
COPY roostos-identity-samba /app/roostos-identity-samba

# Install packages
RUN pip install --no-cache-dir /app/roostos-sdk /app/roostos-identity-samba

# Run the bridge daemon
CMD ["python", "-m", "roostos_identity_samba.bridge"]
