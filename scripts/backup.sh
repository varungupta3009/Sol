#!/bin/bash

# ================================================================
# Sol Home Server - Master Automated Backup Script
# ================================================================
# Targets: Cloud Backup via Rclone (OneDrive:Sol)
# Features:
#   1. Loads live .env credentials safely
#   2. Automated live PostgreSQL dumps (Authentik & Paperless)
#   3. Online atomic SQLite .backup snapshots (prevents WAL corruption)
#   4. Versioned OneDrive sync (--backup-dir) with strict exit checks
#   5. Dual execution mode (Native host Rclone with --profile ops fallback)
# ================================================================

set -euo pipefail

# Navigate to Sol root directory
cd "$(dirname "$0")/.."

# Safely load key=value pairs from .env (handles unquoted spaces/JSON in Docker Compose .env files)
load_env() {
    local env_file="$1"
    [ -f "$env_file" ] || return 0
    while IFS= read -r line || [ -n "$line" ]; do
        line="${line#"${line%%[![:space:]]*}"}"
        [[ -z "$line" || "$line" == \#* || "$line" != *=* ]] && continue
        local key="${line%%=*}"
        local val="${line#*=}"
        # Strip inline comments only on unquoted values
        if [[ "$val" != \"* && "$val" != \'* ]]; then
            val="${val%%[[:space:]]#*}"
        fi
        # Strip surrounding single or double quotes
        val="${val#\"}"
        val="${val%\"}"
        val="${val#\'}"
        val="${val%\'}"
        if [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
            export "$key=$val"
        fi
    done < "$env_file"
}

load_env "./.env"

# Initialize required directories
mkdir -p ./logs ./data/backups ./data/backups/sqlite

TIMESTAMP="$(date +%Y-%m-%d_%H-%M-%S)"
LOG_FILE="./logs/backup_${TIMESTAMP}.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

log "================================================================"
log " Starting Sol Server Backup Pipeline"
log "================================================================"

# ----------------------------------------------------------------
# Step 1: Pre-Backup Database Dumps (PostgreSQL & SQLite WAL)
# ----------------------------------------------------------------
log "--- [1/3] Executing live database backups ---"

# 1a. Authentik PostgreSQL Dump
if docker ps --format '{{.Names}}' | grep -q "^authentik-postgresql$"; then
    log "Dumping Authentik PostgreSQL database..."
    if docker exec authentik-postgresql pg_dump --clean --if-exists -U "${PG_USER:-authentik}" "${PG_DB:-authentik}" | gzip > ./data/backups/authentik_db.sql.gz.tmp; then
        mv ./data/backups/authentik_db.sql.gz.tmp ./data/backups/authentik_db.sql.gz
        log "✓ Authentik DB dumped to data/backups/authentik_db.sql.gz"
    else
        rm -f ./data/backups/authentik_db.sql.gz.tmp
        log "⚠ Warning: Authentik DB dump failed."
    fi
else
    log "ℹ authentik-postgresql container is not running; skipping live DB dump."
fi

# 1b. Paperless PostgreSQL Dump
if docker ps --format '{{.Names}}' | grep -q "^paperless-db$"; then
    log "Dumping Paperless PostgreSQL database..."
    if docker exec paperless-db pg_dump --clean --if-exists -U "${PAPERLESS_DB_USER:-paperless}" "${PAPERLESS_DB_NAME:-paperless}" | gzip > ./data/backups/paperless_db.sql.gz.tmp; then
        mv ./data/backups/paperless_db.sql.gz.tmp ./data/backups/paperless_db.sql.gz
        log "✓ Paperless DB dumped to data/backups/paperless_db.sql.gz"
    else
        rm -f ./data/backups/paperless_db.sql.gz.tmp
        log "⚠ Warning: Paperless DB dump failed."
    fi
else
    log "ℹ paperless-db container is not running; skipping live DB dump."
fi

# 1c. Online Atomic SQLite Snapshots (Prevents live WAL/SHM split-brain during rclone sync)
# Note: On macOS + OrbStack/VirtioFS, opening a live container's WAL-mode SQLite DB in read-write
# mode from the macOS host kernel can desynchronize the guest Linux VM's mmap-backed -shm index.
# Using URI `?immutable=1` (or running inside the Linux VM) avoids host-to-guest -shm writes.
if command -v sqlite3 &> /dev/null; then
    log "Creating atomic online SQLite snapshots in data/backups/sqlite/..."
    while IFS= read -r -d '' db_file; do
        rel_path="${db_file#./}"
        safe_name="${rel_path//\//__}"
        if ! head -c 15 "$db_file" 2>/dev/null | grep -q "SQLite format 3"; then
            continue
        fi
        if sqlite3 "file:${db_file}?immutable=1" ".backup './data/backups/sqlite/${safe_name}'" 2>/dev/null; then
            log "  ✓ Snapshot: ${rel_path} -> data/backups/sqlite/${safe_name}"
        else
            log "  ⚠ Skipped locked or non-SQLite file: ${rel_path}"
        fi
    done < <(find ./config ./data/arcane ./data/ignis ./data/ntfy ./data/copyparty ./data/homebox -maxdepth 4 \( -name "*.db" -o -name "*.sqlite" -o -name "*.sqlite3" \) -type f -print0 2>/dev/null || true)
else
    log "ℹ sqlite3 CLI not found on host; skipping online SQLite snapshot step."
fi

# ----------------------------------------------------------------
# Step 2: Rclone Cloud Synchronization
# ----------------------------------------------------------------
log "--- [2/3] Synchronizing Sol state to OneDrive:Sol ---"

RCLONE_CONF="./config/rclone/rclone.conf"
FILTER_FILE="./config/rclone/filter.txt"
if [ ! -f "$FILTER_FILE" ] && [ -f "./config/rclone/filter.txt.example" ]; then
    log "ℹ ./config/rclone/filter.txt not found; using tracked ./config/rclone/filter.txt.example"
    FILTER_FILE="./config/rclone/filter.txt.example"
fi

ARCHIVE_DIR="OneDrive:Sol-archive/${TIMESTAMP}"

if command -v rclone &> /dev/null && [ -f "$RCLONE_CONF" ]; then
    log "Using native host rclone CLI ($(rclone --version | head -n 1))..."
    rclone sync . "OneDrive:Sol" \
        --config "$RCLONE_CONF" \
        --filter-from "$FILTER_FILE" \
        --backup-dir "$ARCHIVE_DIR" \
        --links \
        -v \
        --stats 30s \
        --stats-one-line \
        2>&1 | tee -a "$LOG_FILE"
else
    log "Using containerized rclone via Docker Compose (--profile ops)..."
    CONTAINER_FILTER="/config/rclone/filter.txt"
    if [ "$FILTER_FILE" = "./config/rclone/filter.txt.example" ]; then
        CONTAINER_FILTER="/source/config/rclone/filter.txt.example"
    fi
    docker compose --profile ops run --rm rclone sync \
        /source \
        "OneDrive:Sol" \
        --filter-from "$CONTAINER_FILTER" \
        --backup-dir "$ARCHIVE_DIR" \
        --links \
        -v \
        --stats 30s \
        --stats-one-line \
        2>&1 | tee -a "$LOG_FILE"
fi

# ----------------------------------------------------------------
# Step 3: Cleanup & Summary
# ----------------------------------------------------------------
log "--- [3/3] Finalizing backup report ---"

# Prune old local log files older than 30 days
find ./logs -name "backup_*.log" -type f -mtime +30 -delete 2>/dev/null || true

log "✓ Sol Server Backup completed successfully."
log "✓ Point-in-time archive for modified/deleted files: $ARCHIVE_DIR"
log "✓ Log file saved to: $LOG_FILE"
log "================================================================"
