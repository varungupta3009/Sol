#!/bin/bash

# ================================================================
# Sol Home Server - Master Automated Backup Script (Restic + Backrest)
# ================================================================
# Targets:
#   1. Local Encrypted Restic Repo: /Volumes/PANOPTICON/backups/sol-restic
#   2. Cloud Encrypted Restic Repo: rclone:OneDrive:Sol-Restic
#   3. Optional Legacy Rclone Sync: OneDrive:Sol (--legacy-rclone)
#
# Usage:
#   ./scripts/backup.sh [--local-only] [--cloud-only] [--legacy-rclone]
# ================================================================

set -euo pipefail

cd "$(dirname "$0")/.."

# Prevent non-interactive SSH / launchd docker calls from hanging on locked macOS Keychain
mkdir -p /tmp/sol_no_keychain
printf '#!/bin/sh\necho "{}"\n' > /tmp/sol_no_keychain/docker-credential-osxkeychain
chmod +x /tmp/sol_no_keychain/docker-credential-osxkeychain
export PATH="/tmp/sol_no_keychain:/usr/local/bin:/opt/homebrew/bin:$PATH"

LOCAL_ONLY=false
CLOUD_ONLY=false
LEGACY_RCLONE=false

for arg in "$@"; do
    case "$arg" in
        --local-only) LOCAL_ONLY=true ;;
        --cloud-only) CLOUD_ONLY=true ;;
        --legacy-rclone) LEGACY_RCLONE=true ;;
        *) echo "Unknown option: $arg"; exit 1 ;;
    esac
done

load_env() {
    local env_file="$1"
    [ -f "$env_file" ] || return 0
    while IFS= read -r line || [ -n "$line" ]; do
        line="${line#"${line%%[![:space:]]*}"}"
        [[ -z "$line" || "$line" == \#* || "$line" != *=* ]] && continue
        local key="${line%%=*}"
        local val="${line#*=}"
        if [[ "$val" != \"* && "$val" != \'* ]]; then
            val="${val%%[[:space:]]#*}"
        fi
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

mkdir -p ./logs ./data/backups ./data/backups/sqlite ./config/backrest

if [ ! -f "./config/backrest/excludes.txt" ] && [ -f "./config/backrest/excludes.txt.example" ]; then
    cp ./config/backrest/excludes.txt.example ./config/backrest/excludes.txt
fi

TIMESTAMP="$(date +%Y-%m-%d_%H-%M-%S)"
LOG_FILE="./logs/backup_${TIMESTAMP}.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

log "================================================================"
log " Starting Sol Server Backup Pipeline (Restic + Backrest)"
log "================================================================"

# ----------------------------------------------------------------
# Step 1: Stage Databases, SQLite Snapshots & Symlink Manifest
# ----------------------------------------------------------------
log "--- [1/3] Staging live databases, SQLite snapshots & symlink manifest ---"
./scripts/stage_db_backups.sh 2>&1 | tee -a "$LOG_FILE"

# ----------------------------------------------------------------
# Step 2: Encrypted Restic Snapshots (via Backrest Container)
# ----------------------------------------------------------------
log "--- [2/3] Running encrypted deduplicated Restic snapshots ---"

export RESTIC_PASSWORD="${RESTIC_PASSWORD:-${CORE_PASSWORD:-}}"
if [ -z "$RESTIC_PASSWORD" ]; then
    log "❌ Error: Neither RESTIC_PASSWORD nor CORE_PASSWORD is set in .env."
    exit 1
fi

if ! docker ps --format '{{.Names}}' | grep -q "^backrest$"; then
    log "Starting backrest container..."
    docker compose up -d backrest
    sleep 2
fi

run_restic_repo() {
    local repo_label="$1"
    local repo_uri="$2"

    log "Checking Restic repository [${repo_label}]: ${repo_uri}"
    if ! docker exec -e RESTIC_PASSWORD="$RESTIC_PASSWORD" backrest restic -r "$repo_uri" snapshots >/dev/null 2>&1; then
        log "Initializing new Restic repository at ${repo_uri}..."
        docker exec -e RESTIC_PASSWORD="$RESTIC_PASSWORD" backrest restic -r "$repo_uri" init 2>&1 | tee -a "$LOG_FILE"
    fi

    log "Creating Restic snapshot in [${repo_label}]..."
    docker exec -e RESTIC_PASSWORD="$RESTIC_PASSWORD" backrest restic -r "$repo_uri" backup /userdata/sol \
        --exclude-file /config/excludes.txt \
        --tag "sol-automated" \
        --host "sol" \
        2>&1 | tee -a "$LOG_FILE"

    log "Applying retention policy on [${repo_label}] (7 daily, 4 weekly, 6 monthly)..."
    docker exec -e RESTIC_PASSWORD="$RESTIC_PASSWORD" backrest restic -r "$repo_uri" forget \
        --keep-daily 7 \
        --keep-weekly 4 \
        --keep-monthly 6 \
        --prune \
        2>&1 | tee -a "$LOG_FILE"

    log "✓ Completed Restic snapshot & prune for [${repo_label}]."
}

# 2a. Local External Drive Restic Repo (/Volumes/PANOPTICON/backups/sol-restic)
if [ "$CLOUD_ONLY" = false ]; then
    EXT_DRIVE="${EXTERNAL_DRIVE_00:-/Volumes/PANOPTICON}"
    if [ -d "$EXT_DRIVE" ]; then
        mkdir -p "${EXT_DRIVE}/backups/sol-restic"
        run_restic_repo "Local-PANOPTICON" "/repos/local-panopticon"
    else
        log "⚠ External drive ${EXT_DRIVE} not mounted; skipping local Restic snapshot."
    fi
fi

# 2b. Cloud OneDrive Restic Repo (rclone:OneDrive:Sol-Restic)
if [ "$LOCAL_ONLY" = false ]; then
    if [ -f "./config/rclone/rclone.conf" ]; then
        run_restic_repo "Cloud-OneDrive" "rclone:OneDrive:Sol-Restic"
    else
        log "⚠ ./config/rclone/rclone.conf not found; skipping OneDrive cloud Restic snapshot."
    fi
fi

# 2c. Optional Legacy Rclone Raw File Sync
if [ "$LEGACY_RCLONE" = true ]; then
    log "Running optional legacy rclone sync to OneDrive:Sol..."
    RCLONE_CONF="./config/rclone/rclone.conf"
    FILTER_FILE="./config/rclone/filter.txt"
    [ ! -f "$FILTER_FILE" ] && FILTER_FILE="./config/rclone/filter.txt.example"
    ARCHIVE_DIR="OneDrive:Sol-archive/${TIMESTAMP}"
    rclone sync . "OneDrive:Sol" \
        --config "$RCLONE_CONF" \
        --filter-from "$FILTER_FILE" \
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
find ./logs -name "backup_*.log" -type f -mtime +30 -delete 2>/dev/null || true

log "✓ Sol Server Restic Backup completed."
log "✓ Log file saved to: $LOG_FILE"
log "================================================================"
