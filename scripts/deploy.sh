#!/bin/bash
# BlogPilot Production Deploy Script
# Run on Hostinger VPS: bash scripts/deploy.sh
# Safe for first-time setup AND updates — preserves all user data.

set -e

APP_DIR="/opt/blogpilot"
REPO="https://github.com/smitchandarana/LinkedINAuto.git"

echo "============================================"
echo "  BlogPilot Deploy — $(date)"
echo "============================================"

# ── First-time setup ──────────────────────────────────────────
if [ ! -d "$APP_DIR" ]; then
    echo ">>> First-time install..."
    sudo mkdir -p "$APP_DIR"
    sudo chown "$(whoami)":"$(whoami)" "$APP_DIR"
    git clone "$REPO" "$APP_DIR"
    cd "$APP_DIR"

    # Create .env from template
    if [ ! -f docker/.env ]; then
        echo ">>> Creating docker/.env — EDIT THIS with real secrets!"
        cp docker/.env.example docker/.env
        echo ""
        echo "!!! IMPORTANT: Edit docker/.env with real passwords before continuing !!!"
        echo "    nano $APP_DIR/docker/.env"
        echo ""
        exit 1
    fi
else
    echo ">>> Updating existing install..."
    cd "$APP_DIR"
    git pull origin main
fi

# ── Install Docker if missing ─────────────────────────────────
if ! command -v docker &> /dev/null; then
    echo ">>> Installing Docker..."
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker "$(whoami)"
    echo ">>> Docker installed. Log out and back in, then re-run this script."
    exit 0
fi

# ── Build images ──────────────────────────────────────────────
echo ">>> Building BlogPilot backend image..."
docker build -f docker/Dockerfile.blogpilot -t blogpilot-backend:latest .

echo ">>> Building Platform API image..."
docker build -f docker/Dockerfile.platform -t blogpilot-platform:latest .

# ── Create Docker network if missing ──────────────────────────
docker network create blogpilot-net 2>/dev/null || true

# ── Start/update infrastructure ───────────────────────────────
cd docker
echo ">>> Starting infrastructure (postgres, traefik, docker-proxy)..."
docker compose up -d postgres docker-proxy traefik

echo ">>> Waiting for PostgreSQL..."
until docker compose exec -T postgres pg_isready -U blogpilot; do
    sleep 2
done

echo ">>> Starting/updating Platform API..."
docker compose up -d --no-deps --build platform-api

# ── Rolling update of user containers ─────────────────────────
echo ">>> Checking for running user containers..."
CONTAINERS=$(docker ps --filter "name=blogpilot-" --filter "status=running" --format "{{.Names}}" | grep -v "platform\|traefik\|postgres\|docker-proxy" || true)

if [ -n "$CONTAINERS" ]; then
    echo ">>> Found user containers to update:"
    echo "$CONTAINERS"
    echo ""

    for CONTAINER in $CONTAINERS; do
        echo "  Updating $CONTAINER..."
        # Graceful stop (30s for engine to drain)
        docker stop "$CONTAINER" --time 30 || true
        docker rm "$CONTAINER" || true
        echo "  $CONTAINER removed. Will be recreated with new image on next start."
    done

    echo ""
    echo ">>> User containers stopped. They will start with new image when users"
    echo "    click 'Start' in dashboard or via admin panel restart."
else
    echo ">>> No user containers running."
fi

# ── Health check ──────────────────────────────────────────────
echo ""
echo ">>> Verifying deployment..."
sleep 5

HEALTH=$(curl -sf http://localhost:9000/health 2>/dev/null || echo '{"status":"FAILED"}')
echo "Platform health: $HEALTH"

echo ""
echo "============================================"
echo "  Deploy complete!"
echo "  Platform API: http://localhost:9000"
echo "  Traefik:      http://localhost:80"
echo "============================================"
