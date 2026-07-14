#!/usr/bin/env bash
# RoostOS debos chroot setup script
# Executes inside the target bootstrap rootfs during compilation.

set -e

echo "Starting RoostOS chroot customization..."

# 1. Setup default system environment parameters
echo "roost-router" > /etc/hostname
echo "127.0.0.1 localhost roost-router" > /etc/hosts

# Enable systemd-networkd and systemd-resolved
systemctl enable systemd-networkd
systemctl enable systemd-resolved
systemctl enable cockpit.socket

# 2. Build and install local python packages inside an isolated virtual environment
if [ -d "/tmp/src/roostos" ]; then
    echo "Creating isolated virtual environment in /opt/roostos/venv..."
    python3 -m venv /opt/roostos/venv
    
    echo "Installing RoostOS packages into virtual environment..."
    /opt/roostos/venv/bin/pip install --upgrade pip
    /opt/roostos/venv/bin/pip install \
        /tmp/src/roostos/roostos-sdk \
        /tmp/src/roostos/roostos-engine \
        /tmp/src/roostos/roostos-dns-technitium

    # Create symlinks to /usr/local/bin so they are globally accessible
    ln -sf /opt/roostos/venv/bin/roostd /usr/local/bin/roostd
    ln -sf /opt/roostos/venv/bin/roostctl /usr/local/bin/roostctl

    # Deploy Cockpit Custom UI
    echo "Deploying Cockpit custom dashboard pages..."
    mkdir -p /usr/share/cockpit/roostos
    cp -r /tmp/src/roostos/roostos-ui/* /usr/share/cockpit/roostos/

    # Clean up temporary sources
    rm -rf /tmp/src/roostos
else
    echo "Warning: RoostOS source directory not found in /tmp/src/roostos. Skipping package compilation." >&2
fi

# 3. Setup default configs directory
mkdir -p /etc/roostos
mkdir -p /var/lib/roostos

# Enable core daemon systemd service
if [ -f "/etc/systemd/system/roostd.service" ]; then
    systemctl enable roostd.service
    echo "roostd systemd service enabled."
else
    echo "Warning: roostd.service file missing in chroot /etc/systemd/system/" >&2
fi

# Enable SSH root login for headless router installs (optional, secure by default)
if [ -f "/etc/ssh/sshd_config" ]; then
    sed -i 's/#PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config
fi

echo "RoostOS chroot customization completed successfully!"
exit 0
