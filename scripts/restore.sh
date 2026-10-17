#!/bin/bash

# ================================================================
# Sol Home Server - Master Disaster Recovery & Restore Script
# ================================================================
# Restores the complete Sol server from OneDrive:Sol cloud backup.
#
# Usage:
#   ./scripts/restore.sh [--dry-run] [--skip-cloud-pull] [--restore-dbs] [--start-stack]
# ================================================================

set -euo pipefail

# Navigate to Sol root directory
cd "$(dirname "$0")/.."
SOL_ROOT="$(pwd)"

DRY_RUN=false
SKIP_PULL=false
RESTORE_DBS=false
START_STACK=false

# Parse command line flags
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=true ;;
        --skip-cloud-pull) SKIP_PULL=true ;;
        --restore-dbs) RESTORE_DBS=true ;;
        --start-stack) START_STACK=true ;;
        *) echo "Unknown option: $arg"; exit 1 ;;
    esac
done

echo "================================================================"
echo " Sol Server Disaster Recovery & Restore Utility"
echo " Working Directory: $SOL_ROOT"
echo "================================================================"

# ----------------------------------------------------------------
# Step 1: Pull from Cloud Backup
# ----------------------------------------------------------------
if [ "$SKIP_PULL" = false ]; then
    echo "--- [1/4] Pulling configurations from OneDrive:Sol ---"
    RCLONE_CONF="./config/rclone/rclone.conf"
    RCLONE_CONF_ARG=()

    if [ ! -f "$RCLONE_CONF" ]; then
        echo "⚠ Warning: Local rclone config not found at $RCLONE_CONF."
        echo "If this is a fresh machine, ensure rclone has access to 'OneDrive:' or copy rclone.conf into ./config/rclone/"
        read -rp "Do you want to continue with global rclone config? (y/N) " confirm
        if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
            exit 1
        fi
    else
        RCLONE_CONF_ARG=(--config "$RCLONE_CONF")
    fi

    DRY_RUN_ARG=()
    if [ "$DRY_RUN" = true ]; then
        DRY_RUN_ARG=(--dry-run)
        echo "[DRY RUN MODE ENABLED] No files will be modified."
    fi

    rclone copy "OneDrive:Sol" "$SOL_ROOT" \
        ${RCLONE_CONF_ARG[@]+"${RCLONE_CONF_ARG[@]}"} \
        --links \
        -v \
        --stats 15s \
        ${DRY_RUN_ARG[@]+"${DRY_RUN_ARG[@]}"}

    echo "✓ Cloud sync download completed."
else
    echo "--- [1/4] Skipping cloud pull (restoring from local state) ---"
fi

if [ "$DRY_RUN" = true ]; then
    echo "[DRY RUN COMPLETE] Exiting."
    exit 0
fi

# ----------------------------------------------------------------
# Step 2: Verify Essential System Files & Hierarchy
# ----------------------------------------------------------------
echo "--- [2/4] Verifying essential directory structure & secrets ---"

# Ensure all essential directories exist
mkdir -p ./logs ./data/backups ./data/backups/sqlite ./data/media/preshows ./data/torrents ./data/paperless/consume ./data/paperless/scripts ./config/rclone

if [ ! -f "./config/rclone/filter.txt" ] && [ -f "./config/rclone/filter.txt.example" ]; then
    cp ./config/rclone/filter.txt.example ./config/rclone/filter.txt
    echo "✓ Initialized ./config/rclone/filter.txt from filter.txt.example"
fi

if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo "⚠ Warning: .env file missing! Creating from .env.example..."
        cp .env.example .env
        echo "Please edit .env with your actual credentials before starting services."
    else
        echo "❌ Error: Neither .env nor .env.example found!"
        exit 1
    fi
fi

# Safely load key=value pairs from .env (handles unquoted spaces/JSON in Docker Compose .env files)
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

# Ensure executable scripts have correct permissions
chmod +x ./scripts/*.sh ./scripts/*.py 2>/dev/null || true

# ----------------------------------------------------------------
# Step 3: Database Integrity & Cold-Start Restoration
# ----------------------------------------------------------------
echo "--- [3/4] Checking database dumps & SQLite snapshots in data/backups ---"

# Restore atomic SQLite snapshots if destination database files are missing
if [ -d "./data/backups/sqlite" ]; then
    for snap in ./data/backups/sqlite/*; do
        [ -e "$snap" ] || continue
        snap_base="$(basename "$snap")"
        orig_rel="${snap_base//__/\/}"
        if [ ! -f "./${orig_rel}" ]; then
            mkdir -p "$(dirname "./${orig_rel}")"
            cp "$snap" "./${orig_rel}"
            echo "✓ Restored missing SQLite database: ./${orig_rel}"
        fi
    done
fi

# Determine whether PostgreSQL dumps should be imported
NEED_AUTHENTIK_IMPORT=false
NEED_PAPERLESS_IMPORT=false

if [ "$RESTORE_DBS" = true ]; then
    NEED_AUTHENTIK_IMPORT=true
    NEED_PAPERLESS_IMPORT=true
elif [ "$START_STACK" = true ]; then
    if [ ! -f "./data/authentik/PG_VERSION" ] && [ -f "./data/backups/authentik_db.sql.gz" ]; then
        NEED_AUTHENTIK_IMPORT=true
    fi
    if [ ! -f "./data/paperless/db/PG_VERSION" ] && [ -f "./data/backups/paperless_db.sql.gz" ]; then
        NEED_PAPERLESS_IMPORT=true
    fi
fi

if [ -f "./data/backups/authentik_db.sql.gz" ]; then
    echo "Found Authentik DB dump: ./data/backups/authentik_db.sql.gz"
    if [ "$NEED_AUTHENTIK_IMPORT" = true ]; then
        echo "Starting authentik-postgresql container for dump import..."
        docker compose up -d authentik-postgresql
        for _ in {1..30}; do
            if docker exec authentik-postgresql pg_isready -U "${PG_USER:-authentik}" -d "${PG_DB:-authentik}" >/dev/null 2>&1; then
                break
            fi
            sleep 1
        done
        echo "Importing Authentik database dump..."
        gunzip -c ./data/backups/authentik_db.sql.gz | docker exec -i authentik-postgresql psql -U "${PG_USER:-authentik}" -d "${PG_DB:-authentik}"
        echo "✓ Authentik PostgreSQL dump imported."
    else
        echo "ℹ Skipping Authentik SQL import (cluster already exists; pass --restore-dbs to force import)."
    fi
fi

if [ -f "./data/backups/paperless_db.sql.gz" ]; then
    echo "Found Paperless DB dump: ./data/backups/paperless_db.sql.gz"
    if [ "$NEED_PAPERLESS_IMPORT" = true ]; then
        echo "Starting paperless-db container for dump import..."
        docker compose up -d paperless-db
        for _ in {1..30}; do
            if docker exec paperless-db pg_isready -U "${PAPERLESS_DB_USER:-paperless}" -d "${PAPERLESS_DB_NAME:-paperless}" >/dev/null 2>&1; then
                break
            fi
            sleep 1
        done
        echo "Importing Paperless database dump..."
        gunzip -c ./data/backups/paperless_db.sql.gz | docker exec -i paperless-db psql -U "${PAPERLESS_DB_USER:-paperless}" -d "${PAPERLESS_DB_NAME:-paperless}"
        echo "✓ Paperless PostgreSQL dump imported."
    else
        echo "ℹ Skipping Paperless SQL import (cluster already exists; pass --restore-dbs to force import)."
    fi
fi

# ----------------------------------------------------------------
# Step 4: Optional Stack Startup & Validation
# ----------------------------------------------------------------
echo "--- [4/4] Validation & Startup ---"

if docker compose -f docker-compose.yml config > /dev/null 2>&1; then
    echo "✓ Docker Compose configuration is valid."
else
    echo "❌ Error: Docker Compose syntax check failed. Please inspect compose files."
    exit 1
fi

if [ "$START_STACK" = true ]; then
    echo "Starting all active Sol services..."
    docker compose up -d
    echo "✓ Stack started. Checking container status:"
    docker compose ps
else
    echo "✓ Restore preparation completed."
    echo "To launch the restored stack (or force DB import), run:"
    echo "  ./scripts/restore.sh --skip-cloud-pull --restore-dbs --start-stack"
    echo "  docker compose up -d"
fi

echo "================================================================"
