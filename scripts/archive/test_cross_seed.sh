#!/bin/bash

# ================================================================
# Sol Home Server - Cross-Seed Permission & Hardlink Diagnostic
# ================================================================
# Verifies write permissions and APFS/ExFAT hardlink behavior inside
# the cross-seed container using the actual unprivileged PUID:PGID
# (501:20) rather than root.
# ================================================================

set -euo pipefail

cd "$(dirname "$0")/.."

# Safely load PUID/PGID from .env (handles unquoted spaces/JSON in Docker Compose .env files)
if [ -f "./.env" ]; then
    while IFS= read -r line || [ -n "$line" ]; do
        line="${line#"${line%%[![:space:]]*}"}"
        [[ -z "$line" || "$line" == \#* || "$line" != *=* ]] && continue
        key="${line%%=*}"
        val="${line#*=}"
        val="${val#\"}"
        val="${val%\"}"
        val="${val#\'}"
        val="${val%\'}"
        if [[ "$key" == "PUID" || "$key" == "PGID" ]]; then
            export "$key=$val"
        fi
    done < "./.env"
fi

TARGET_UID="${PUID:-501}"
TARGET_GID="${PGID:-20}"

echo "--- 1. Checking Container Status ---"
if ! docker ps --format '{{.Names}}' | grep -q "^cross-seed$"; then
    echo "Error: cross-seed container is not running."
    echo "Please start it first: docker compose up -d cross-seed"
    exit 1
fi

echo "--- 2. Executing Permission & Hardlink Tests as UID:GID ${TARGET_UID}:${TARGET_GID} ---"
docker exec -u "${TARGET_UID}:${TARGET_GID}" cross-seed /bin/sh -c '
    echo ">> Effective container identity: $(id)"
    echo ">> Checking mounted directories..."

    # 1. Verify /external mount
    if [ ! -d "/external" ]; then
        echo "CRITICAL: /external is NOT mounted inside the container."
        exit 1
    fi

    # 2. Ensure link directories exist with unprivileged ownership
    if [ ! -d "/external/cross-seed-links" ]; then
        echo ">> Creating missing directory: /external/cross-seed-links"
        mkdir -p /external/cross-seed-links
    fi

    if [ ! -d "/downloads/cross-seed-links" ]; then
        echo ">> Creating missing directory: /downloads/cross-seed-links"
        mkdir -p /downloads/cross-seed-links
    fi

    echo ">> Testing Write Permissions & Hardlink Support..."

    # --- TEST EXTERNAL DRIVE ---
    echo "---------------------------------------------------"
    echo "TESTING EXTERNAL DRIVE (/external)"

    if touch /external/cross-seed-links/write_test.tmp 2>/dev/null; then
        echo "  [PASS] Write permission OK as unprivileged user."
        rm -f /external/cross-seed-links/write_test.tmp
    else
        echo "  [FAIL] Cannot write to /external/cross-seed-links. Check PUID/PGID ownership (expected 501:20)."
    fi

    if touch /external/source_test.tmp 2>/dev/null; then
        if ln /external/source_test.tmp /external/cross-seed-links/link_test.tmp 2>/dev/null; then
            echo "  [PASS] Hardlinks are SUPPORTED on /external."
            rm -f /external/source_test.tmp /external/cross-seed-links/link_test.tmp
        else
            echo "  [INFO] Hardlinks are NOT SUPPORTED on /external (ExFAT volume; use symlink mode for external paths)."
            rm -f /external/source_test.tmp
        fi
    fi

    # --- TEST INTERNAL DOWNLOADS (/downloads) ---
    echo "---------------------------------------------------"
    echo "TESTING INTERNAL DOWNLOADS (/downloads)"

    if touch /downloads/source_test.tmp 2>/dev/null; then
        if ln /downloads/source_test.tmp /downloads/cross-seed-links/link_test.tmp 2>/dev/null; then
            echo "  [PASS] Hardlinks are SUPPORTED on /downloads (APFS)."
            rm -f /downloads/source_test.tmp /downloads/cross-seed-links/link_test.tmp
        else
            echo "  [FAIL] Hardlinks failed on /downloads."
            rm -f /downloads/source_test.tmp
        fi
    else
        echo "  [FAIL] Cannot write to /downloads as unprivileged user."
    fi

    # --- TEST UNIFIED DATA MOUNT (/data) ---
    if [ -d "/data/torrents" ] && [ -d "/data/media" ]; then
        echo "---------------------------------------------------"
        echo "TESTING UNIFIED APFS MOUNT (/data/torrents <-> /data/media)"
        if touch /data/torrents/unified_test.tmp 2>/dev/null; then
            if ln /data/torrents/unified_test.tmp /data/media/unified_link_test.tmp 2>/dev/null; then
                echo "  [PASS] Cross-directory APFS hardlinks (/data/torrents <-> /data/media) are SUPPORTED."
                rm -f /data/torrents/unified_test.tmp /data/media/unified_link_test.tmp
            else
                echo "  [FAIL] Cross-directory hardlink between /data/torrents and /data/media failed."
                rm -f /data/torrents/unified_test.tmp
            fi
        fi
    fi
    echo "---------------------------------------------------"
'
