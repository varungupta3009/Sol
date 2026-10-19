#!/usr/bin/env bash
# ================================================================
# Sol - Unified Identity Helper (lldap -> users.json -> Every App)
# ================================================================
# Authoritative user database: lldap (https://ldap.vrg.rocks, data/lldap/users.db).
# Add, edit, or remove users in the lldap Web UI at https://ldap.vrg.rocks.
# The com.vrg.sol.identity-sync launchd watcher automatically runs a one-way
# sync (lldap -> config/auth/users.json -> Tinyauth, OIDC apps, Jellyfin, Seerr, Copyparty).
#
# Usage:
#   ./scripts/allowlist_user.sh list             (show exported users.json snapshot)
#   ./scripts/allowlist_user.sh sync [--apply]   (run one-way lldap -> users.json -> apps sync)
# ================================================================
set -euo pipefail
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USERS_JSON="${BASE_DIR}/config/auth/users.json"
SYNC="${BASE_DIR}/scripts/identity_sync.py"
ACTION="${1:-list}"

case "${ACTION}" in
  list)
    python3 - "${USERS_JSON}" <<'PY'
import json, sys
for u in json.load(open(sys.argv[1]))["users"]:
    print(f"{u['uid']:10} {u['display']:10} {u['role']:6} jf={u.get('jellyfin_id')} seerr={u.get('seerr_id')}  {', '.join(u['emails'])}")
PY
    ;;
  sync|from-lldap)
    shift; python3 "${SYNC}" "$@"
    ;;
  add|remove)
    echo "lldap (https://ldap.vrg.rocks) is the single authoritative user database." >&2
    echo "Add, edit, or delete users in https://ldap.vrg.rocks; com.vrg.sol.identity-sync syncs lldap -> users.json automatically." >&2
    exit 1
    ;;
  *)
    echo "Usage: $0 {list|sync [--apply]}" >&2
    exit 1
    ;;
esac
