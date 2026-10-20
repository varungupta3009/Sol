#!/bin/bash

# ================================================================
# Sol Home Server - Master Bare-Metal Disaster Recovery & Restore Script
# ================================================================
# Restores the complete Sol server after a macOS reset from either:
#   - Local Restic Repo (/Volumes/PANOPTICON/backups/sol-restic) [Fastest]
#   - Cloud Restic Repo (rclone:OneDrive:Sol-Restic)
#   - Legacy Rclone Mirror (OneDrive:Sol) via --legacy-rclone
#
# Also recreates all media/cross-seed symlinks from symlinks_manifest.tsv,
# restores atomic SQLite snapshots, imports Paperless, AirTrail & Coder
# PostgreSQL dumps, restores the persistent Coder workspace volume, and
# installs macOS LaunchAgents.
#
# Usage:
#   ./scripts/restore.sh [--from-local] [--from-cloud] [--snapshot <id>]
#                        [--dry-run] [--skip-cloud-pull] [--restore-dbs]
#                        [--restore-symlinks] [--start-stack] [--legacy-rclone]
# ================================================================

set -euo pipefail

cd "$(dirname "$0")/.."
SOL_ROOT="$(pwd)"

# Prevent non-interactive SSH / launchd docker calls from hanging on locked macOS Keychain
mkdir -p /tmp/sol_no_keychain
printf '#!/bin/sh\necho "{}"\n' > /tmp/sol_no_keychain/docker-credential-osxkeychain
chmod +x /tmp/sol_no_keychain/docker-credential-osxkeychain
export PATH="/tmp/sol_no_keychain:/usr/local/bin:/opt/homebrew/bin:$PATH"

DRY_RUN=false
SKIP_PULL=false
RESTORE_DBS=false
RESTORE_SYMLINKS=true
START_STACK=false
FROM_LOCAL=false
FROM_CLOUD=false
LEGACY_RCLONE=false
SNAPSHOT_ID="latest"

while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run) DRY_RUN=true ;;
        --skip-cloud-pull) SKIP_PULL=true ;;
        --restore-dbs) RESTORE_DBS=true ;;
        --restore-symlinks) RESTORE_SYMLINKS=true ;;
        --no-symlinks) RESTORE_SYMLINKS=false ;;
        --start-stack) START_STACK=true ;;
        --from-local) FROM_LOCAL=true ;;
        --from-cloud) FROM_CLOUD=true ;;
        --legacy-rclone) LEGACY_RCLONE=true ;;
        --snapshot)
            shift
            SNAPSHOT_ID="${1:-latest}"
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
    shift
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

echo "================================================================"
echo " Sol Server Disaster Recovery & Bare-Metal Restore Utility"
echo " Working Directory: $SOL_ROOT"
echo "================================================================"

# ----------------------------------------------------------------
# Step 1: Pull Server State from Restic (or Legacy Rclone)
# ----------------------------------------------------------------
if [ "$SKIP_PULL" = false ]; then
    if [ "$LEGACY_RCLONE" = true ]; then
        echo "--- [1/5] Pulling state from legacy OneDrive:Sol via rclone ---"
        RCLONE_CONF="./config/rclone/rclone.conf"
        RCLONE_CONF_ARG=()
        [ -f "$RCLONE_CONF" ] && RCLONE_CONF_ARG=(--config "$RCLONE_CONF")
        DRY_RUN_ARG=()
        [ "$DRY_RUN" = true ] && DRY_RUN_ARG=(--dry-run)
        rclone copy "OneDrive:Sol" "$SOL_ROOT" \
            ${RCLONE_CONF_ARG[@]+"${RCLONE_CONF_ARG[@]}"} \
            --links \
            -v \
            --stats 15s \
            ${DRY_RUN_ARG[@]+"${DRY_RUN_ARG[@]}"}
    else
        echo "--- [1/5] Restoring snapshot (${SNAPSHOT_ID}) from Restic ---"
        export RESTIC_PASSWORD="${RESTIC_PASSWORD:-${CORE_PASSWORD:-}}"
        if [ -z "$RESTIC_PASSWORD" ]; then
            read -rsp "Enter Restic Repository Password (CORE_PASSWORD): " RESTIC_PASSWORD
            echo ""
            export RESTIC_PASSWORD
        fi

        EXT_REPO="${EXTERNAL_DRIVE_00:-/Volumes/PANOPTICON}/backups/sol-restic"
        RESTIC_VOL_ARGS=(-v "${SOL_ROOT}:/userdata/sol")
        if [ -d "${SOL_ROOT}/config/rclone" ]; then
            RESTIC_VOL_ARGS+=(-v "${SOL_ROOT}/config/rclone:/root/.config/rclone:ro")
        fi
        if [ "$FROM_LOCAL" = true ] || { [ "$FROM_CLOUD" = false ] && [ -d "${EXT_REPO}/data" ]; }; then
            REPO_URI="/repos/local-panopticon"
            RESTIC_VOL_ARGS+=(-v "${EXT_REPO}:/repos/local-panopticon")
            echo "Selected Local Restic Repository: ${EXT_REPO}"
        else
            REPO_URI="rclone:OneDrive:Sol-Restic"
            echo "Selected Cloud Restic Repository: ${REPO_URI}"
        fi

        if [ "$DRY_RUN" = true ]; then
            echo "[DRY RUN] Listing snapshots in ${REPO_URI}:"
            docker run --rm "${RESTIC_VOL_ARGS[@]}" -e RESTIC_PASSWORD="$RESTIC_PASSWORD" \
                --entrypoint restic ghcr.io/garethgeorge/backrest:latest -r "$REPO_URI" snapshots
            exit 0
        fi

        docker run --rm "${RESTIC_VOL_ARGS[@]}" -e RESTIC_PASSWORD="$RESTIC_PASSWORD" \
            --entrypoint restic ghcr.io/garethgeorge/backrest:latest \
            -r "$REPO_URI" restore "$SNAPSHOT_ID" \
            --target /
        echo "✓ Restic snapshot (${SNAPSHOT_ID}) restored into ${SOL_ROOT}."
    fi
else
    echo "--- [1/5] Skipping snapshot pull (restoring from local ./data/backups) ---"
fi

if [ "$DRY_RUN" = true ]; then
    echo "[DRY RUN COMPLETE] Exiting."
    exit 0
fi

# Reload .env after snapshot restore in case .env was restored from Restic
load_env "./.env"

# ----------------------------------------------------------------
# Step 2: Verify Essential Directories, Static Tools & LaunchAgents
# ----------------------------------------------------------------
echo "--- [2/5] Verifying essential directory structure, static tools & LaunchAgents ---"
mkdir -p ./logs ./data/backups ./data/backups/sqlite ./data/media/preshows ./data/media/home-videos ./data/torrents ./data/paperless/consume ./data/paperless/redis ./data/paperless/scripts ./data/tinyauth ./data/lldap ./data/readeck ./data/pocketbase ./data/enclosed ./data/airtrail ./config/rclone ./config/backrest

if [ ! -f "./config/rclone/filter.txt" ] && [ -f "./config/rclone/filter.txt.example" ]; then
    cp ./config/rclone/filter.txt.example ./config/rclone/filter.txt
fi
if [ ! -f "./config/backrest/excludes.txt" ] && [ -f "./config/backrest/excludes.txt.example" ]; then
    cp ./config/backrest/excludes.txt.example ./config/backrest/excludes.txt
fi
if [ ! -f "./config/backrest/config.json" ] && [ -f "./config/backrest/config.json.example" ]; then
    cp ./config/backrest/config.json.example ./config/backrest/config.json
fi

chmod +x ./scripts/*.sh ./scripts/*.py 2>/dev/null || true

if [ -x "./scripts/sync_static_tools.sh" ]; then
    ./scripts/sync_static_tools.sh || true
fi

if [ -d "./scripts/launchd" ] && [ -d "$HOME/Library/LaunchAgents" ]; then
    for plist in ./scripts/launchd/com.vrg.sol.*.plist; do
        [ -f "$plist" ] || continue
        plist_name="$(basename "$plist")"
        cp "$plist" "$HOME/Library/LaunchAgents/$plist_name"
        launchctl bootout "gui/$(id -u)/${plist_name%.plist}" 2>/dev/null || true
        launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/$plist_name" 2>/dev/null || true
        echo "✓ Installed & loaded LaunchAgent: ${plist_name}"
    done
fi

# ----------------------------------------------------------------
# Step 3: Recreate Media & Cross-Seed Symlinks
# ----------------------------------------------------------------
echo "--- [3/5] Restoring media & cross-seed symlinks from manifest ---"
if [ "$RESTORE_SYMLINKS" = true ] && [ -f "./data/backups/symlinks_manifest.tsv" ]; then
    RESTORED_LINKS=0
    while IFS=$'\t' read -r link_path target_path; do
        [[ -z "$link_path" || -z "$target_path" ]] && continue
        if [ ! -L "$link_path" ] && [ ! -e "$link_path" ]; then
            mkdir -p "$(dirname "$link_path")"
            ln -s "$target_path" "$link_path"
            RESTORED_LINKS=$((RESTORED_LINKS + 1))
        fi
    done < ./data/backups/symlinks_manifest.tsv
    echo "✓ Verified symlink tree (${RESTORED_LINKS} missing symlinks recreated)."
else
    echo "ℹ Skipping symlink manifest restoration."
fi

# ----------------------------------------------------------------
# Step 4: Database Integrity, SQLite Snapshots & PostgreSQL Import
# ----------------------------------------------------------------
echo "--- [4/5] Restoring SQLite snapshots, PostgreSQL dumps & Coder home ---"

if [ -d "./data/backups/sqlite" ]; then
    for snap in ./data/backups/sqlite/*; do
        [ -e "$snap" ] || continue
        case "$snap" in
            *-wal|*-shm|*-journal) continue ;;
        esac
        snap_base="$(basename "$snap")"
        orig_rel="${snap_base//__/\/}"
        if [ ! -f "./${orig_rel}" ] || [ "$RESTORE_DBS" = true ]; then
            mkdir -p "$(dirname "./${orig_rel}")"
            rm -f "./${orig_rel}-wal" "./${orig_rel}-shm"
            cp "$snap" "./${orig_rel}"
            echo "✓ Restored SQLite database: ./${orig_rel}"
        fi
    done
fi

NEED_PAPERLESS_IMPORT=false
if [ "$RESTORE_DBS" = true ]; then
    NEED_PAPERLESS_IMPORT=true
elif [ "$START_STACK" = true ]; then
    if [ ! -f "./data/paperless/db/PG_VERSION" ] && [ -f "./data/backups/paperless_db.sql.gz" ]; then
        NEED_PAPERLESS_IMPORT=true
    fi
fi

if [ -f "./data/backups/paperless_db.sql.gz" ] && [ "$NEED_PAPERLESS_IMPORT" = true ]; then
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
    if [ -f "./data/backups/airtrail_db.sql.gz" ]; then
        echo "Importing AirTrail database dump..."
        docker exec paperless-db psql -U "${PAPERLESS_DB_USER:-paperless}" -d postgres -c "CREATE DATABASE airtrail;" 2>/dev/null || true
        docker exec paperless-db psql -U "${PAPERLESS_DB_USER:-paperless}" -d airtrail -c 'CREATE EXTENSION IF NOT EXISTS "unaccent";' 2>/dev/null || true
        gunzip -c ./data/backups/airtrail_db.sql.gz | docker exec -i paperless-db psql -U "${PAPERLESS_DB_USER:-paperless}" -d airtrail
        echo "✓ AirTrail PostgreSQL dump imported."
    fi
    docker exec paperless-db vacuumdb -U "${PAPERLESS_DB_USER:-paperless}" --all --analyze-only >/dev/null 2>&1 || true
fi

NEED_CODER_IMPORT=false
if [ "$RESTORE_DBS" = true ]; then
    NEED_CODER_IMPORT=true
elif [ "$START_STACK" = true ]; then
    if [ ! -f "./config/coder/coderv2/postgres/data/PG_VERSION" ] && [ -f "./data/backups/coder_db.sql.gz" ]; then
        NEED_CODER_IMPORT=true
    fi
fi

if [ -f "./data/backups/coder_db.sql.gz" ] && [ "$NEED_CODER_IMPORT" = true ]; then
    echo "Starting coder container for embedded PostgreSQL dump import..."
    docker compose up -d coder
    for _ in {1..30}; do
        if [ -f "./config/coder/coderv2/postgres/port" ] && [ -f "./config/coder/coderv2/postgres/password" ]; then
            CODER_PG_PORT="$(cat ./config/coder/coderv2/postgres/port 2>/dev/null || echo 43235)"
            CODER_PG_PASS="$(cat ./config/coder/coderv2/postgres/password 2>/dev/null || echo "")"
            if docker run --rm --network container:coder -e PGPASSWORD="$CODER_PG_PASS" postgres:17-alpine \
                pg_isready -h ::1 -p "$CODER_PG_PORT" -U coder -d coder >/dev/null 2>&1; then
                break
            fi
        fi
        sleep 1
    done
    if [ -f "./config/coder/coderv2/postgres/port" ]; then
        CODER_PG_PORT="$(cat ./config/coder/coderv2/postgres/port 2>/dev/null || echo 43235)"
        CODER_PG_PASS="$(cat ./config/coder/coderv2/postgres/password 2>/dev/null || echo "")"
        echo "Importing Coder embedded PostgreSQL database dump..."
        gunzip -c ./data/backups/coder_db.sql.gz | grep -v '^SET transaction_timeout' \
            | docker run --rm -i --network container:coder -e PGPASSWORD="$CODER_PG_PASS" postgres:17-alpine \
                psql -h ::1 -p "$CODER_PG_PORT" -U coder -d coder
        docker compose restart coder
        echo "✓ Coder PostgreSQL dump imported."
    else
        echo "⚠ Warning: Coder embedded PostgreSQL did not initialize in time; skipping coder_db.sql.gz import."
    fi
fi

if [ -f "./data/backups/coder_home.tar.gz" ] && [ "$RESTORE_DBS" = true ]; then
    CODER_VOL="$(docker volume ls --format '{{.Name}}' | grep '^coder-.*-home$' | head -n 1 || true)"
    if [ -z "$CODER_VOL" ] && [ -f "./data/backups/coder_volume_name.txt" ]; then
        CODER_VOL="$(tr -d '[:space:]' < ./data/backups/coder_volume_name.txt)"
        if [ -n "$CODER_VOL" ]; then
            docker volume create "$CODER_VOL" >/dev/null
        fi
    fi
    if [ -n "$CODER_VOL" ]; then
        echo "Restoring Coder workspace volume (${CODER_VOL})..."
        docker run --rm -v "${CODER_VOL}:/coder_home" -v "$(pwd)/data/backups:/backups:ro" redis:8-alpine \
            tar -xzf /backups/coder_home.tar.gz --numeric-owner -C /coder_home
        echo "✓ Restored Coder workspace volume (${CODER_VOL})."
    fi
fi

# ----------------------------------------------------------------
# Step 5: Validation & Stack Startup
# ----------------------------------------------------------------
echo "--- [5/5] Validation & Stack Startup ---"

if docker compose -f docker-compose.yml config > /dev/null 2>&1; then
    echo "✓ Docker Compose configuration is valid."
else
    echo "❌ Error: Docker Compose syntax check failed."
    exit 1
fi

if [ "$START_STACK" = true ]; then
    echo "Starting all active Sol services..."
    docker compose up -d
    docker compose ps
else
    echo "✓ Restore completed. Run 'docker compose up -d' or pass '--start-stack' to launch."
fi

echo "================================================================"
