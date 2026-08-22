#!/bin/bash

# A script to diagnose cross-seed permission and filesystem issues inside the container.

echo "--- 1. Checking Container Status ---"
if ! docker ps | grep -q cross-seed; then
    echo "Error: cross-seed container is not running."
    echo "Please start it (even if it restarts/fails) so we can exec into it."
    exit 1
fi

echo "--- 2. Executing Tests Inside Container ---"
docker exec -u 0 cross-seed /bin/sh -c '
    echo ">> Checking directories..."
    
    # 1. Verify /external mount
    if [ ! -d "/external" ]; then
        echo "CRITICAL: /external is NOT mounted inside the container."
        exit 1
    fi

    # 2. Create the link directories if they are missing
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
    
    # Test Write
    if touch /external/cross-seed-links/write_test.tmp; then
        echo "  [PASS] Write permission OK."
        rm /external/cross-seed-links/write_test.tmp
    else
        echo "  [FAIL] Cannot write to /external/cross-seed-links. Check PUID/PGID permissions."
    fi

    # Test Hardlink
    touch /external/source_test.tmp
    if ln /external/source_test.tmp /external/cross-seed-links/link_test.tmp 2>/dev/null; then
        echo "  [PASS] Hardlinks are SUPPORTED."
        rm /external/source_test.tmp /external/cross-seed-links/link_test.tmp
    else
        echo "  [FAIL] Hardlinks are NOT SUPPORTED."
        echo "         Reason: Filesystem is likely exFAT or FAT32."
        rm /external/source_test.tmp
    fi

    # --- TEST DOWNLOADS DRIVE ---
    echo "---------------------------------------------------"
    echo "TESTING INTERNAL DOWNLOADS (/downloads)"
    
    # Test Hardlink
    touch /downloads/source_test.tmp
    if ln /downloads/source_test.tmp /downloads/cross-seed-links/link_test.tmp 2>/dev/null; then
        echo "  [PASS] Hardlinks are SUPPORTED."
        rm /downloads/source_test.tmp /downloads/cross-seed-links/link_test.tmp
    else
        echo "  [FAIL] Hardlinks are NOT SUPPORTED."
        rm /downloads/source_test.tmp
    fi
    echo "---------------------------------------------------"
'