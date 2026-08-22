#!/bin/bash

# ================================================================
# Sol Home Server - Master Automated Backup Script
# ================================================================
# Targets: Cloud Backup via Rclone (OneDrive:Sol)
# Features:
#   1. Automated live PostgreSQL dumps (Authentik & Paperless)
#   2. Intelligent filtering (Excludes bulk media, caches, rolling logs)
#   3. Dual execution mode (Native host Rclone with Docker fallback)
#   4. Detailed timestamped logging
# ================================================================

set -euo pipefail

# Navigate to Sol root directory
cd "$(dirname "$0")/.."

# Initialize required directories
mkdir -p ./logs ./data/backups

LOG_FILE="./logs/backup_$(date +%Y-%m-%d_%H-%M-%S).log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

log "================================================================"
log " Starting Sol Server Backup Pipeline"
log "================================================================"

# ----------------------------------------------------------------
# Step 1: Pre-Backup Database Dumps
# ----------------------------------------------------------------
log "--- [1/3] Executing live database backups ---"

# Authentik PostgreSQL Dump
if docker ps --format '{{.Names}}' | grep -q "^authentik-postgresql$"; then
    log "Dumping Authentik PostgreSQL database..."
    if docker exec authentik-postgresql pg_dump -U "${PG_USER:-authentik}" "${PG_DB:-authentik}" | gzip > ./data/backups/authentik_db.sql.gz; then
        log " Authentik DB successfully dumped to data/backups/authentik_db.sql.gz"
    else
        log "⚠ Warning: Authentik DB dump failed, continuing with file backup."
    fi
else
    log "ℹ authentik-postgresql container is not running; skipping live DB dump."
fi

# Paperless PostgreSQL Dump
if docker ps --format '{{.Names}}' | grep -q "^paperless-db$"; then
    log "Dumping Paperless PostgreSQL database..."
    if docker exec paperless-db pg_dump -U "${PAPERLESS_DB_USER:-paperless}" "${PAPERLESS_DB_NAME:-paperless}" | gzip > ./data/backups/paperless_db.sql.gz; then
        log " Paperless DB successfully dumped to data/backups/paperless_db.sql.gz"
    else
        log "⚠ Warning: Paperless DB dump failed, continuing with file backup."
    fi
else
    log "ℹ paperless-db container is not running; skipping live DB dump."
fi

# ----------------------------------------------------------------
# Step 2: Rclone Cloud Synchronization
# ----------------------------------------------------------------
log "--- [2/3] Synchronizing Sol state to OneDrive:Sol ---"

RCLONE_CONF="./config/rclone/rclone.conf"
FILTER_FILE="./config/rclone/filter.txt"

if command -v rclone &> /dev/null && [ -f "$RCLONE_CONF" ]; then
    log "Using native host rclone CLI ($(rclone --version | head -n 1))..."
    rclone sync . "OneDrive:Sol" \
        --config "$RCLONE_CONF" \
        --filter-from "$FILTER_FILE" \
        --links \
        -v \
        --stats 30s \
        --stats-one-line \
        --log-file="$LOG_FILE" \
        2>&1 | tee -a "$LOG_FILE" || true
else
    log "Using containerized rclone via Docker Compose..."
    docker compose run --rm rclone sync \
        /source \
        OneDrive:Sol \
        --filter-from /config/rclone/filter.txt \
        -v \
        --log-file=/logs/rclone_container.log \
        2>&1 | tee -a "$LOG_FILE" || true

    if [ -f "./logs/rclone_container.log" ]; then
        cat ./logs/rclone_container.log >> "$LOG_FILE"
        rm -f ./logs/rclone_container.log
    fi
fi

# ----------------------------------------------------------------
# Step 3: Cleanup & Summary
# ----------------------------------------------------------------
log "--- [3/3] Finalizing backup report ---"

# Prune old local log files older than 30 days
find ./logs -name "backup_*.log" -type f -mtime +30 -delete 2>/dev/null || true

log " Sol Server Backup completed successfully."
log " Log file saved to: $LOG_FILE"
log "================================================================"
