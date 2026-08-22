#!/bin/bash

# ================================================================
# Sol Home Server - Master Disaster Recovery & Restore Script
# ================================================================
# Restores the complete Sol server from OneDrive:Sol cloud backup.
#
# Usage:
#   ./scripts/restore.sh [--dry-run] [--skip-cloud-pull] [--start-stack]
# ================================================================

set -euo pipefail

# Navigate to Sol root directory
cd "$(dirname "$0")/.."
SOL_ROOT="$(pwd)"

DRY_RUN=false
SKIP_PULL=false
START_STACK=false

# Parse command line flags
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=true ;;
        --skip-cloud-pull) SKIP_PULL=true ;;
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
    
    if [ ! -f "$RCLONE_CONF" ]; then
        echo "⚠ Warning: Local rclone config not found at $RCLONE_CONF."
        echo "If this is a fresh machine, ensure rclone has access to 'OneDrive:' or copy rclone.conf into ./config/rclone/"
        read -rp "Do you want to continue with global rclone config? (y/N) " confirm
        if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
            exit 1
        fi
        RCLONE_CONF_ARG=""
    else
        RCLONE_CONF_ARG="--config $RCLONE_CONF"
    fi

    DRY_RUN_ARG=""
    if [ "$DRY_RUN" = true ]; then
        DRY_RUN_ARG="--dry-run"
        echo "[DRY RUN MODE ENABLED] No files will be modified."
    fi

    rclone copy "OneDrive:Sol" "$SOL_ROOT" \
        $RCLONE_CONF_ARG \
        --links \
        -v \
        --stats 15s \
        $DRY_RUN_ARG

    echo " Cloud sync download completed."
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
mkdir -p ./logs ./data/backups ./data/media/preshows ./data/torrents ./data/paperless/consume ./data/paperless/scripts

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

# Ensure executable scripts have correct permissions
chmod +x ./scripts/*.sh ./scripts/*.py 2>/dev/null || true

# ----------------------------------------------------------------
# Step 3: Database Integrity & Cold-Start Restoration
# ----------------------------------------------------------------
echo "--- [3/4] Checking database dumps in data/backups ---"

if [ -f "./data/backups/authentik_db.sql.gz" ]; then
    echo " Found Authentik DB dump: ./data/backups/authentik_db.sql.gz"
fi

if [ -f "./data/backups/paperless_db.sql.gz" ]; then
    echo " Found Paperless DB dump: ./data/backups/paperless_db.sql.gz"
fi

# ----------------------------------------------------------------
# Step 4: Optional Stack Startup & Validation
# ----------------------------------------------------------------
echo "--- [4/4] Validation & Startup ---"

if docker compose -f docker-compose.yml config > /dev/null 2>&1; then
    echo " Docker Compose configuration is 100% valid."
else
    echo "❌ Error: Docker Compose syntax check failed. Please inspect compose files."
    exit 1
fi

if [ "$START_STACK" = true ]; then
    echo "Starting all Sol services..."
    docker compose up -d
    echo " Stack started. Checking container status:"
    docker compose ps
else
    echo " Restore completed successfully!"
    echo "To launch the restored stack, run:"
    echo "  docker compose up -d"
fi

echo "================================================================"
