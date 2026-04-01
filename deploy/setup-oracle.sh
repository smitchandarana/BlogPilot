#!/usr/bin/env bash
# BlogPilot — Oracle ARM VM Setup (Ubuntu)
set -euo pipefail

echo "=== BlogPilot — Oracle ARM VM Setup ==="

# 1. System update
echo "[1/5] System update..."
apt-get update && apt-get upgrade -y
apt-get install -y ca-certificates curl gnupg lsb-release git unzip jq htop

# 2. Swap (4GB)
echo "[2/5] Creating 4GB swap..."
if [ ! -f /swapfile ]; then
    fallocate -l 4G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
    sysctl vm.swappiness=10
    echo 'vm.swappiness=10' >> /etc/sysctl.conf
fi

# 3. Docker
echo "[3/5] Installing Docker..."
if ! command -v docker &> /dev/null; then
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
        https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
        > /etc/apt/sources.list.d/docker.list
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    systemctl enable docker
    systemctl start docker
fi
usermod -aG docker ubuntu 2>/dev/null || true

# 4. Cloudflare Tunnel
echo "[4/5] Installing cloudflared..."
if ! command -v cloudflared &> /dev/null; then
    curl -fsSL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64.deb \
        -o /tmp/cloudflared.deb
    dpkg -i /tmp/cloudflared.deb
    rm /tmp/cloudflared.deb
fi

# 5. Docker log rotation
echo "[5/5] Configuring Docker..."
cat > /etc/docker/daemon.json << 'EOF'
{
    "log-driver": "json-file",
    "log-opts": { "max-size": "10m", "max-file": "3" }
}
EOF
systemctl restart docker

# Project dir
mkdir -p /opt/blogpilot
chown ubuntu:ubuntu /opt/blogpilot

echo ""
echo "=== Setup complete ==="
