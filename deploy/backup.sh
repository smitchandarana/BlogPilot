#!/usr/bin/env bash
# BlogPilot — Daily backup script
# Cron: 0 3 * * * /opt/blogpilot/deploy/backup.sh
#
# Backs up: Postgres DB + user volumes
# Keeps last 7 days of backups

set -euo pipefail

BACKUP_DIR="/opt/blogpilot/backups"
DATE=$(date +%Y-%m-%d_%H%M)
COMPOSE_FILE="/opt/blogpilot/docker/docker-compose.oracle.yml"

mkdir -p "$BACKUP_DIR"

echo "[$(date)] Starting backup..."

# 1. Postgres dump
echo "  Dumping Postgres..."
docker compose -f "$COMPOSE_FILE" exec -T postgres \
    pg_dump -U blogpilot blogpilot_platform \
    | gzip > "$BACKUP_DIR/postgres_${DATE}.sql.gz"

# 2. User volumes (config + data, not browser profiles — too large)
echo "  Backing up user volumes..."
tar czf "$BACKUP_DIR/volumes_${DATE}.tar.gz" \
    -C /opt/blogpilot/docker/volumes . \
    --exclude='*/browser_profile/*' \
    2>/dev/null || true

# 3. Cleanup old backups (keep 7 days)
find "$BACKUP_DIR" -name "*.gz" -mtime +7 -delete

echo "[$(date)] Backup complete:"
ls -lh "$BACKUP_DIR"/*_${DATE}* 2>/dev/null
