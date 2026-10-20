#!/bin/bash

# ================================================================
# Sol Home Server - Pre-Backup Database & State Staging Script
# ================================================================
# Prepares atomic, crash-consistent snapshots in ./data/backups/
# prior to Restic/Backrest or Rclone backup runs:
#   1. Live PostgreSQL dumps (paperless_db.sql.gz, airtrail_db.sql.gz,
#      and coder_db.sql.gz)
#   2. Online WAL-complete SQLite snapshots in data/backups/sqlite/*
#      (copies .db + -wal to a private temp dir, runs .backup, and
#      switches snapshot journal_mode=DELETE so zero -wal/-shm sidecars
#      remain in data/backups/sqlite/)
#   3. Complete media & cross-seed symlink manifest (symlinks_manifest.tsv)
#   4. Persistent Coder workspace home volume archive (coder_home.tar.gz
#      and coder_volume_name.txt)
# ================================================================

set -euo pipefail

cd "$(dirname "$0")/.."

# Prevent non-interactive SSH / launchd docker calls from hanging on locked macOS Keychain
mkdir -p /tmp/sol_no_keychain
printf '#!/bin/sh\necho "{}"\n' > /tmp/sol_no_keychain/docker-credential-osxkeychain
chmod +x /tmp/sol_no_keychain/docker-credential-osxkeychain
export PATH="/tmp/sol_no_keychain:/usr/local/bin:/opt/homebrew/bin:$PATH"

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

mkdir -p ./data/backups ./data/backups/sqlite

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

# 1. Paperless & AirTrail PostgreSQL Dumps
if docker ps --format '{{.Names}}' | grep -q "^paperless-db$"; then
    log "Dumping Paperless PostgreSQL database..."
    if docker exec paperless-db pg_dump --clean --if-exists -U "${PAPERLESS_DB_USER:-paperless}" "${PAPERLESS_DB_NAME:-paperless}" | gzip > ./data/backups/paperless_db.sql.gz.tmp; then
        mv ./data/backups/paperless_db.sql.gz.tmp ./data/backups/paperless_db.sql.gz
        log "✓ Paperless DB dumped to data/backups/paperless_db.sql.gz"
    else
        rm -f ./data/backups/paperless_db.sql.gz.tmp
        log "⚠ Warning: Paperless DB dump failed."
    fi

    log "Dumping AirTrail PostgreSQL database..."
    if docker exec paperless-db pg_dump --clean --if-exists -U "${PAPERLESS_DB_USER:-paperless}" "airtrail" | gzip > ./data/backups/airtrail_db.sql.gz.tmp; then
        mv ./data/backups/airtrail_db.sql.gz.tmp ./data/backups/airtrail_db.sql.gz
        log "✓ AirTrail DB dumped to data/backups/airtrail_db.sql.gz"
    else
        rm -f ./data/backups/airtrail_db.sql.gz.tmp
        log "⚠ Warning: AirTrail DB dump failed."
    fi
else
    log "ℹ paperless-db is not running; skipping live dump."
fi

# 2. Coder Embedded PostgreSQL Dump
if docker ps --format '{{.Names}}' | grep -q "^coder$" && [ -f "./config/coder/coderv2/postgres/port" ]; then
    log "Dumping Coder embedded PostgreSQL database..."
    CODER_PG_PORT="$(cat ./config/coder/coderv2/postgres/port 2>/dev/null || echo 43235)"
    CODER_PG_PASS="$(cat ./config/coder/coderv2/postgres/password 2>/dev/null || echo "")"
    if docker run --rm --network container:coder -e PGPASSWORD="$CODER_PG_PASS" postgres:17-alpine \
        pg_dump -h ::1 -p "$CODER_PG_PORT" -U coder -d coder --clean --if-exists 2>/dev/null \
        | grep -v '^SET transaction_timeout' | gzip > ./data/backups/coder_db.sql.gz.tmp; then
        mv ./data/backups/coder_db.sql.gz.tmp ./data/backups/coder_db.sql.gz
        log "✓ Coder DB dumped to data/backups/coder_db.sql.gz"
    else
        rm -f ./data/backups/coder_db.sql.gz.tmp
        log "⚠ Warning: Coder DB dump failed."
    fi
fi

# 3. Online WAL-Complete SQLite Snapshots (VirtioFS-safe temp copy + .backup)
if command -v sqlite3 &> /dev/null; then
    log "Creating WAL-complete SQLite snapshots in data/backups/sqlite/..."
    rm -rf ./data/backups/sqlite/*
    SQLITE_TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/sol_sqlite_snap.XXXXXX")"
    trap 'rm -rf "$SQLITE_TMP_DIR"' EXIT

    SQLITE_CANDIDATE_DIRS=(
        ./config/prowlarr
        ./config/radarr
        ./config/sonarr
        ./config/lidarr
        ./config/bazarr
        ./config/jellyfin
        ./config/seerr
        ./config/qui
        ./config/wizarr
        ./config/vaultwarden
        ./data/lldap
        ./data/tinyauth
        ./data/ntfy
        ./data/beszel
        ./data/arcane
        ./data/pocketbase
        ./data/homebox
        ./data/readeck
        ./data/enclosed
        ./data/ignis
        ./data/paperless/data
        ./data/backrest/data
        ./data/leafwiki
        ./data/kavita
    )
    SQLITE_SEARCH_DIRS=()
    for d in "${SQLITE_CANDIDATE_DIRS[@]}"; do
        [ -d "$d" ] && SQLITE_SEARCH_DIRS+=("$d")
    done

    if [ "${#SQLITE_SEARCH_DIRS[@]}" -gt 0 ]; then
        while IFS= read -r -d '' db_file; do
            rel_path="${db_file#./}"
            safe_name="${rel_path//\//__}"
            if ! head -c 15 "$db_file" 2>/dev/null | grep -q "SQLite format 3"; then
                continue
            fi
            rm -f "${SQLITE_TMP_DIR}/work.db" "${SQLITE_TMP_DIR}/work.db-wal" "${SQLITE_TMP_DIR}/work.db-shm"
            cp "$db_file" "${SQLITE_TMP_DIR}/work.db" 2>/dev/null || continue
            if [ -f "${db_file}-wal" ]; then
                cp "${db_file}-wal" "${SQLITE_TMP_DIR}/work.db-wal" 2>/dev/null || true
            fi
            if sqlite3 "${SQLITE_TMP_DIR}/work.db" ".backup './data/backups/sqlite/${safe_name}'" 2>/dev/null; then
                sqlite3 "./data/backups/sqlite/${safe_name}" "PRAGMA journal_mode=DELETE;" >/dev/null 2>&1 || true
                rm -f "./data/backups/sqlite/${safe_name}-wal" "./data/backups/sqlite/${safe_name}-shm"
                log "  ✓ Snapshot: ${rel_path} -> data/backups/sqlite/${safe_name}"
            else
                rm -f "./data/backups/sqlite/${safe_name}" "./data/backups/sqlite/${safe_name}-wal" "./data/backups/sqlite/${safe_name}-shm"
                log "  ⚠ Skipped locked or non-SQLite file: ${rel_path}"
            fi
        done < <(find "${SQLITE_SEARCH_DIRS[@]}" -maxdepth 4 \
            \( -name "*.db" -o -name "*.sqlite" -o -name "*.sqlite3" \) \
            ! -name "logs.db" \
            ! -name "cache.db" \
            ! -name "auxiliary.db" \
            ! -name "up2k.db" \
            ! -name "MediaCover*" \
            -type f -print0 2>/dev/null || true)
    fi
    rm -rf "$SQLITE_TMP_DIR"
    trap - EXIT
fi

# 4. Media & Cross-Seed Symlink Manifest (Run via OrbStack container so launchd never blocks on macOS Removable Volume TCC)
log "Capturing media & cross-seed symlink manifest..."
MANIFEST_TMP="./data/backups/symlinks_manifest.tsv.tmp"
EXT_DRV="${EXTERNAL_DRIVE_00:-/Volumes/PANOPTICON}"
if docker run --rm \
    -v "$(pwd)/data:/sol_data:ro" \
    -v "${EXT_DRV}:/panopticon:ro" \
    -e EXT_DRV="${EXT_DRV}" \
    redis:8-alpine sh -c '
        for p in /sol_data/media /sol_data/torrents/cross-seed-links /sol_data/torrents/qui-links /panopticon/media /panopticon/torrents/cross-seed-links /panopticon/torrents/qui-links; do
            [ -d "$p" ] && find "$p" -type l
        done | while IFS= read -r link_path; do
            target_path="$(readlink "$link_path" || true)"
            [ -z "$target_path" ] && continue
            case "$link_path" in
                /sol_data/*) host_path="./data/${link_path#/sol_data/}" ;;
                /panopticon/*) host_path="${EXT_DRV}/${link_path#/panopticon/}" ;;
                *) host_path="$link_path" ;;
            esac
            printf "%s\t%s\n" "$host_path" "$target_path"
        done
    ' > "$MANIFEST_TMP"; then
    mv "$MANIFEST_TMP" ./data/backups/symlinks_manifest.tsv
    LINK_COUNT="$(wc -l < ./data/backups/symlinks_manifest.tsv | tr -d ' ')"
    log "✓ Recorded ${LINK_COUNT} symlinks in data/backups/symlinks_manifest.tsv"
else
    rm -f "$MANIFEST_TMP"
    log "⚠ Warning: Failed to capture symlink manifest."
fi

# 5. Persistent Coder Home Volume Snapshot (if volume exists)
CODER_VOL="$(docker volume ls --format '{{.Name}}' | grep '^coder-.*-home$' | head -n 1 || true)"
if [ -n "$CODER_VOL" ]; then
    log "Archiving persistent Coder workspace volume (${CODER_VOL})..."
    echo "${CODER_VOL}" > ./data/backups/coder_volume_name.txt
    if docker run --rm -v "${CODER_VOL}:/coder_home:ro" -v "$(pwd)/data/backups:/backups" redis:8-alpine \
        tar -czf /backups/coder_home.tar.gz.tmp \
        --exclude='./.cache' \
        --exclude='./.local/share/code-server' \
        --exclude='./.vscode-server' \
        --exclude='./.cargo' \
        --exclude='./.rustup' \
        --exclude='./.bun' \
        --exclude='./.npm' \
        --exclude='node_modules' \
        -C /coder_home . 2>/dev/null; then
        mv ./data/backups/coder_home.tar.gz.tmp ./data/backups/coder_home.tar.gz
        log "✓ Archived Coder home volume (${CODER_VOL}) to data/backups/coder_home.tar.gz"
    else
        rm -f ./data/backups/coder_home.tar.gz.tmp
        log "⚠ Warning: Failed to archive Coder home volume."
    fi
fi
