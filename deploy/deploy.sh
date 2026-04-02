#!/usr/bin/env bash
# BlogPilot — Build & Deploy
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/opt/blogpilot}"
COMPOSE_FILE="docker/docker-compose.oracle.yml"
cd "$PROJECT_DIR"

case "${1:-deploy}" in
    deploy)
        [ ! -f docker/.env ] && { echo "ERROR: docker/.env not found. Copy docker/.env.example and fill in secrets."; exit 1; }

        echo "[1/5] Building frontend..."
        cd ui && npm ci --prefer-offline && npm run build && cd ..
        echo "      → ui/dist built"

        echo "[2/5] Installing nginx site config..."
        cp deploy/nginx.conf /etc/nginx/sites-available/blogpilot
        ln -sf /etc/nginx/sites-available/blogpilot /etc/nginx/sites-enabled/blogpilot
        rm -f /etc/nginx/sites-enabled/default
        nginx -t && systemctl reload nginx
        echo "      → nginx reloaded"

        echo "[3/5] Building platform image..."
        docker compose -f "$COMPOSE_FILE" build --no-cache platform-api

        echo "[4/5] Starting services..."
        docker compose -f "$COMPOSE_FILE" up -d

        echo "[5/5] Checking health..."
        sleep 10
        curl -sf http://localhost:9000/health && echo " Platform API: HEALTHY" || echo " Platform API: not yet healthy (check: docker compose -f $COMPOSE_FILE logs platform-api)"
        docker compose -f "$COMPOSE_FILE" ps
        ;;

    frontend)
        echo "Building and deploying frontend only..."
        cd ui && npm ci --prefer-offline && npm run build && cd ..
        nginx -t && systemctl reload nginx
        echo "Frontend deployed."
        ;;

    restart)
        docker compose -f "$COMPOSE_FILE" restart
        systemctl reload nginx
        ;;

    stop)
        docker compose -f "$COMPOSE_FILE" down
        ;;

    logs)
        docker compose -f "$COMPOSE_FILE" logs -f --tail=100
        ;;

    status)
        docker compose -f "$COMPOSE_FILE" ps
        echo ""
        echo "--- nginx ---"
        systemctl status nginx --no-pager -l | head -20
        echo ""
        docker stats --no-stream
        ;;

    update)
        git pull origin main
        bash "$PROJECT_DIR/deploy/deploy.sh" deploy
        ;;

    *)
        echo "Usage: deploy.sh [deploy|frontend|restart|stop|logs|status|update]"
        ;;
esac
