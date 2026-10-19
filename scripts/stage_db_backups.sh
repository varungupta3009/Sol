#!/bin/bash

# ================================================================
# Sol Home Server - Pre-Backup Database & State Staging Script
# ================================================================
# Prepares atomic, crash-consistent snapshots in ./data/backups/
# prior to Restic/Backrest or Rclone backup runs:
#   1. Live PostgreSQL dumps (authentik_db.sql.gz & paperless_db.sql.gz)
#   2. Online WAL-complete SQLite snapshots in data/backups/sqlite/
#      (copies .db + -wal to a private temp dir and runs .backup so
#      host-side sqlite3 never mutates live VirtioFS -shm mmap files
#      while still capturing 100% of committed -wal frames)
#   3. Complete media & cross-seed symlink manifest (symlinks_manifest.tsv)
#   4. Persistent Coder workspace home volume archive (coder_home.tar.gz)
# ================================================================

set -euo pipefail

cd "$(dirname "$0")/.."

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

# 1. Authentik PostgreSQL Dump
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
    log "ℹ authentik-postgresql is not running; skipping live dump."
fi

# 2. Paperless & AirTrail PostgreSQL Dumps
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

# 3. Online WAL-Complete SQLite Snapshots (VirtioFS-safe temp copy + .backup)
if command -v sqlite3 &> /dev/null; then
    log "Creating WAL-complete SQLite snapshots in data/backups/sqlite/..."
    SQLITE_TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/sol_sqlite_snap.XXXXXX")"
    trap 'rm -rf "$SQLITE_TMP_DIR"' EXIT
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
            log "  ✓ Snapshot: ${rel_path} -> data/backups/sqlite/${safe_name}"
        else
            log "  ⚠ Skipped locked or non-SQLite file: ${rel_path}"
        fi
    done < <(find ./config ./data/arcane ./data/tinyauth ./data/readeck ./data/pocketbase ./data/enclosed ./data/ignis ./data/ntfy ./data/copyparty ./data/homebox ./data/beszel ./data/leafwiki -maxdepth 4 \( -name "*.db" -o -name "*.sqlite" -o -name "*.sqlite3" \) -type f -print0 2>/dev/null || true)
    rm -rf "$SQLITE_TMP_DIR"
    trap - EXIT
fi

# 4. Media & Cross-Seed Symlink Manifest (Allows 100% symlink tree recreation without backing up bulk media)
log "Capturing media & cross-seed symlink manifest..."
MANIFEST_TMP="./data/backups/symlinks_manifest.tsv.tmp"
: > "$MANIFEST_TMP"
SEARCH_PATHS=()
for p in ./data/media ./data/torrents/cross-seed-links "${EXTERNAL_DRIVE_00:-/Volumes/PANOPTICON}/media" "${EXTERNAL_DRIVE_00:-/Volumes/PANOPTICON}/torrents/cross-seed-links"; do
    [ -d "$p" ] && SEARCH_PATHS+=("$p")
done
if [ "${#SEARCH_PATHS[@]}" -gt 0 ]; then
    while IFS= read -r -d '' link_path; do
        target_path="$(readlink "$link_path" || true)"
        if [ -n "$target_path" ]; then
            printf "%s\t%s\n" "$link_path" "$target_path" >> "$MANIFEST_TMP"
        fi
    done < <(find "${SEARCH_PATHS[@]}" -type l -print0 2>/dev/null || true)
fi
mv "$MANIFEST_TMP" ./data/backups/symlinks_manifest.tsv
LINK_COUNT="$(wc -l < ./data/backups/symlinks_manifest.tsv | tr -d ' ')"
log "✓ Recorded ${LINK_COUNT} symlinks in data/backups/symlinks_manifest.tsv"

# 5. Persistent Coder Home Volume Snapshot (if volume exists)
CODER_VOL="$(docker volume ls --format '{{.Name}}' | grep '^coder-.*-home$' | head -n 1 || true)"
if [ -n "$CODER_VOL" ]; then
    log "Archiving persistent Coder workspace volume (${CODER_VOL})..."
    if docker run --rm -v "${CODER_VOL}:/coder_home:ro" -v "$(pwd)/data/backups:/backups" redis:8-alpine \
        tar -czf /backups/coder_home.tar.gz.tmp \
        --exclude='./.cache' \
        --exclude='./.local/share/code-server/CachedExtensionVSIXs' \
        --exclude='./.cargo/registry' \
        --exclude='./.rustup/toolchains' \
        -C /coder_home . 2>/dev/null; then
        mv ./data/backups/coder_home.tar.gz.tmp ./data/backups/coder_home.tar.gz
        log "✓ Archived Coder home volume to data/backups/coder_home.tar.gz"
    else
        rm -f ./data/backups/coder_home.tar.gz.tmp
        log "⚠ Warning: Failed to archive Coder home volume."
    fi
fi
