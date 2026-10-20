#!/bin/sh
# ==============================================================================
# Sol Servarr Zero-Copy ExFAT Deduplication Hook
# Replaces physical copies created by Radarr/Sonarr on /external with relative symlinks
# ==============================================================================

set -eu

EVENT="${radarr_eventtype:-${sonarr_eventtype:-}}"

# If this is a test event from Servarr UI/API, succeed immediately
if [ "$EVENT" = "Test" ]; then
  echo "Servarr deduplication hook test successful."
  exit 0
fi

DEST="${radarr_moviefile_path:-${sonarr_episodefile_path:-}}"
SRC="${radarr_moviefile_sourcepath:-${sonarr_episodefile_sourcepath:-}}"

# Exit early if not a valid download/upgrade event with both paths
[ -z "$DEST" ] || [ -z "$SRC" ] && exit 0
[ ! -e "$DEST" ] || [ ! -e "$SRC" ] && exit 0

# Only operate when destination is on the external ExFAT media directory
# and source is in the external torrents directory
case "$DEST" in
  /external/media/*)
    case "$SRC" in
      /external/torrents/*)
        # If destination is already a symlink or resolves to the exact same physical file, do nothing
        if [ -L "$DEST" ]; then
          exit 0
        fi
        REAL_SRC="$(realpath "$SRC")"
        REAL_DEST="$(realpath "$DEST")"
        if [ "$REAL_SRC" = "$REAL_DEST" ]; then
          echo "[SAFETY GUARD] DEST ($DEST) and SRC ($SRC) resolve to the same physical file ($REAL_SRC). Skipping."
          exit 0
        fi
        DIR="$(dirname "$DEST")"
        REL_TARGET="$(realpath -m --relative-to="$DIR" "$REAL_SRC")"
        if [ -n "$REL_TARGET" ]; then
          rm -f "$DEST"
          ln -s "$REL_TARGET" "$DEST"
          echo "Replaced physical copy with relative symlink: $DEST -> $REL_TARGET"
        fi
        ;;
    esac
    ;;
esac

exit 0
