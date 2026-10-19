#!/usr/bin/env bash
# ================================================================
# Sol - Unified Identity Front Door (One Email -> Every Interface)
# ================================================================
# Usage:
#   ./scripts/allowlist_user.sh list
#   ./scripts/allowlist_user.sh add <email> <uid> [Display] [admin|user]
#        new uid  -> new person (lldap user, Jellyfin + Seerr account, OIDC consents, Copyparty mapping)
#        old uid  -> extra email (alias) for that person
#   ./scripts/allowlist_user.sh remove <email>
#   ./scripts/allowlist_user.sh sync [--apply]      (dry-run without --apply)
#
# Source of truth: config/auth/users.json. All writes go through
# scripts/identity_sync.py, which syncs Tinyauth, lldap, Jellyfin, Seerr, and Copyparty.
# Compatible with macOS /bin/bash 3.2 (no associative arrays, no ${arr[@]} under -u).
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
  add)
    EMAIL="${2:?email required}"; USERID="${3:-}"; DISPLAY="${4:-}"; ROLE="${5:-user}"
    if [[ -z "${USERID}" ]]; then
      USERID="$(echo "${EMAIL%%@*}" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9_.-')"
    fi
    python3 - "${USERS_JSON}" "${EMAIL}" "${USERID}" "${DISPLAY}" "${ROLE}" <<'PY'
import json, sys
path, email, uid, display, role = sys.argv[1], sys.argv[2].strip().lower(), sys.argv[3].strip().lower(), sys.argv[4], sys.argv[5]
d = json.load(open(path))
if any(email in u["emails"] for u in d["users"]):
    sys.exit(f"{email} already belongs to a user")
for u in d["users"]:
    if u["uid"] == uid:
        u["emails"].append(email); print(f"added alias {email} to {uid}"); break
else:
    d["users"].append({"uid": uid, "display": display or uid.upper(), "emails": [email], "role": role,
                       "jellyfin_id": None, "seerr_id": None})
    print(f"added new user {uid} <{email}>")
open(path, "w").write(json.dumps(d, indent=2) + "\n")
PY
    python3 "${SYNC}" --apply
    ;;
  remove)
    EMAIL="${2:?email required}"
    python3 - "${USERS_JSON}" "${EMAIL}" <<'PY'
import json, sys
path, email = sys.argv[1], sys.argv[2].strip().lower()
d = json.load(open(path))
for u in d["users"]:
    if email in u["emails"]:
        if len(u["emails"]) == 1:
            sys.exit(f"{email} is the only email of {u['uid']}. Remove the user by editing users.json "
                     "(Jellyfin/Seerr/lldap accounts are never deleted automatically).")
        u["emails"].remove(email); print(f"removed alias {email} from {u['uid']}"); break
else:
    sys.exit(f"{email} not found")
open(path, "w").write(json.dumps(d, indent=2) + "\n")
PY
    python3 "${SYNC}" --apply
    ;;
  sync)
    shift; python3 "${SYNC}" "$@"
    ;;
  *)
    echo "Usage: $0 {list|add <email> [uid] [Display] [admin|user]|remove <email>|sync [--apply]}" >&2
    exit 1
    ;;
esac
