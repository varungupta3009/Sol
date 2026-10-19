#!/usr/bin/env bash
# ================================================================
# Sol Home Server - User Email Allowlist & OIDC Consent Manager
# ================================================================
# Usage:
#   ./scripts/allowlist_user.sh list
#   ./scripts/allowlist_user.sh add <email>
#   ./scripts/allowlist_user.sh remove <email>
#
# What 'add <email>' does:
#   1. Appends <email> to data/tinyauth/whitelist.txt (if not already present)
#   2. Updates TINYAUTH_OAUTH_WHITELIST in .env so both sources stay in sync
#   3. Stops tinyauth briefly, pre-seeds 0-click OIDC consent rows into
#      data/tinyauth/tinyauth.db for all 7 OIDC clients so the user never
#      even has to click an "Authorize" consent button on first visit,
#      and starts tinyauth back up (~1 second).
# ================================================================
set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WHITELIST_FILE="${BASE_DIR}/data/tinyauth/whitelist.txt"
ENV_FILE="${BASE_DIR}/.env"
DB_FILE="${BASE_DIR}/data/tinyauth/tinyauth.db"

mkdir -p "$(dirname "${WHITELIST_FILE}")"
touch "${WHITELIST_FILE}"

ACTION="${1:-list}"
EMAIL="${2:-}"

sync_env_and_consents() {
  local csv
  csv="$(grep -v '^[[:space:]]*$' "${WHITELIST_FILE}" | paste -sd, -)"
  if [[ -f "${ENV_FILE}" ]]; then
    python3 - "${ENV_FILE}" "${csv}" <<'PY'
import sys, pathlib, re
env_path = pathlib.Path(sys.argv[1])
csv_val = sys.argv[2]
text = env_path.read_text()
if re.search(r'^TINYAUTH_OAUTH_WHITELIST=', text, flags=re.M):
    text = re.sub(r'^TINYAUTH_OAUTH_WHITELIST=.*$', f'TINYAUTH_OAUTH_WHITELIST={csv_val}', text, flags=re.M)
else:
    text += f'\nTINYAUTH_OAUTH_WHITELIST={csv_val}\n'
env_path.write_text(text)
PY
  fi

  echo "Restarting tinyauth and pre-seeding 0-click OIDC consents..."
  cd "${BASE_DIR}"
  docker stop tinyauth >/dev/null 2>&1 || true

  if [[ -f "${DB_FILE}" && -f "${ENV_FILE}" ]]; then
    python3 - "${DB_FILE}" "${WHITELIST_FILE}" "${ENV_FILE}" <<'PY'
import sqlite3, sys, pathlib, re, time

db_path, wl_path, env_path = sys.argv[1], sys.argv[2], sys.argv[3]
emails = [line.strip() for line in pathlib.Path(wl_path).read_text().splitlines() if line.strip() and not line.startswith('#')]
env_text = pathlib.Path(env_path).read_text()
client_ids = re.findall(r'^TINYAUTH_OIDC_[A-Z0-9_]+_CLIENT_ID=(.+)$', env_text, flags=re.M)

conn = sqlite3.connect(db_path)
cur = conn.cursor()
now = int(time.time())
for email in emails:
    # Tinyauth derives username from Google email by replacing first '@' with '_'
    uname = email.replace('@', '_', 1)
    for cid in client_ids:
        cid = cid.strip().strip('"').strip("'")
        cur.execute(
            "INSERT INTO oidc_consents (username, client_id, scope, created_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(username, client_id) DO UPDATE SET scope = excluded.scope",
            (uname, cid, "openid profile email groups", now),
        )
conn.commit()
conn.close()
PY
  fi

  docker compose up -d tinyauth
  echo "Done. Active allowlisted emails:"
  cat "${WHITELIST_FILE}"
}

case "${ACTION}" in
  list)
    echo "=== Allowlisted Emails (${WHITELIST_FILE}) ==="
    cat "${WHITELIST_FILE}"
    ;;
  add)
    if [[ -z "${EMAIL}" ]]; then
      echo "Usage: $0 add <email>" >&2
      exit 1
    fi
    if grep -Fxq "${EMAIL}" "${WHITELIST_FILE}"; then
      echo "${EMAIL} is already in ${WHITELIST_FILE}."
    else
      echo "${EMAIL}" >> "${WHITELIST_FILE}"
      echo "Added ${EMAIL} to ${WHITELIST_FILE}."
    fi
    sync_env_and_consents
    ;;
  remove)
    if [[ -z "${EMAIL}" ]]; then
      echo "Usage: $0 remove <email>" >&2
      exit 1
    fi
    grep -Fxv "${EMAIL}" "${WHITELIST_FILE}" > "${WHITELIST_FILE}.tmp" || true
    mv "${WHITELIST_FILE}.tmp" "${WHITELIST_FILE}"
    echo "Removed ${EMAIL} from ${WHITELIST_FILE}."
    sync_env_and_consents
    ;;
  *)
    echo "Usage: $0 {list|add <email>|remove <email>}" >&2
    exit 1
    ;;
esac
