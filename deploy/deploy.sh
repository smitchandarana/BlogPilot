#!/usr/bin/env bash
# BlogPilot — Build & Deploy
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/opt/blogpilot}"
COMPOSE_FILE="docker/docker-compose.oracle.yml"
cd "$PROJECT_DIR"

case "${1:-deploy}" in
    deploy)
        [ ! -f docker/.env ] && { echo "ERROR: docker/.env not found"; exit 1; }
        echo "[1/3] Building images..."
        docker build -f docker/Dockerfile.blogpilot -t blogpilot-backend:latest .
        docker build -f docker/Dockerfile.platform -t blogpilot-platform:latest .
        echo "[2/3] Starting services..."
        docker compose -f "$COMPOSE_FILE" up -d
        echo "[3/3] Checking health..."
        sleep 10
        curl -sf http://localhost:80/health && echo " Platform API: HEALTHY" || echo " Waiting..."
        docker compose -f "$COMPOSE_FILE" ps
        ;;
    restart) docker compose -f "$COMPOSE_FILE" restart ;;
    stop)    docker compose -f "$COMPOSE_FILE" down ;;
    logs)    docker compose -f "$COMPOSE_FILE" logs -f --tail=100 ;;
    status)  docker compose -f "$COMPOSE_FILE" ps && echo "" && docker stats --no-stream ;;
    update)  git pull && bash deploy/deploy.sh deploy ;;
    *)       echo "Usage: deploy.sh [deploy|restart|stop|logs|status|update]" ;;
esac
