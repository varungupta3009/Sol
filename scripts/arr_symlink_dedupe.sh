#!/bin/sh
# ==============================================================================
# Sol Servarr Zero-Copy ExFAT Deduplication Hook
# Replaces physical copies created by Radarr/Sonarr on /external with relative symlinks
# ==============================================================================

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
[ ! -f "$DEST" ] || [ ! -f "$SRC" ] && exit 0

# Check if the destination is on the external media directory and source is in torrents
case "$DEST" in
  /external/media/*)
    case "$SRC" in
      /external/torrents/*)
        DIR="$(dirname "$DEST")"
        REL_TARGET="$(realpath -m --relative-to="$DIR" "$SRC")"
        # Only replace if destination is a regular file (not already a link)
        if [ ! -L "$DEST" ] && [ -n "$REL_TARGET" ]; then
          rm -f "$DEST"
          ln -s "$REL_TARGET" "$DEST"
          echo "Replaced physical copy with symlink: $DEST -> $REL_TARGET"
        fi
        ;;
    esac
    ;;
esac

exit 0
