#!/usr/bin/env python3
"""Sol unified identity sync (strict one-way: lldap -> users.json -> Tinyauth, OIDC apps, Jellyfin, Seerr, Copyparty).

lldap (https://ldap.vrg.rocks, data/lldap/users.db) is the single authoritative user database.
Triggered automatically by the macOS launchd WatchPaths agent (com.vrg.sol.identity-sync)
within 15 seconds of any edit in lldap, or manually via `python3 scripts/identity_sync.py --apply`.

Reads `data/lldap/users.db?immutable=1` directly via SQLite (decoding bincode attributes) and
short-circuits in <50ms via `/tmp/sol_identity_sync.sha256` when LLDAP user/group state and `.env`
mtime are unchanged — preventing any self-triggering `WatchPaths` login write loop.

Targets reconciled from lldap:
  1. users.json    read-only exported snapshot of lldap users + discovered Jellyfin/Seerr IDs
  2. Tinyauth      data/tinyauth/whitelist.txt, .env TINYAUTH_OAUTH_WHITELIST, role-scoped oidc_consents
  3. Jellyfin      users exist, AuthenticationProviderId = LDAP-Auth,
                   LDAP-Auth.xml + SSO-Auth.xml (DefaultProvider + DefaultUsernameClaim + CanonicalLinks),
                   branding.xml ("Sign in with Google SSO" button)
  4. Seerr         every Jellyfin user imported, Seerr email = primary email
  5. Paperless-ngx auth_user + socialaccount_socialaccount pre-linked for 0-click first login
  6. AirTrail      "user" table pre-seeded with short username + oauth_id for 0-click first login
  7. Homebox       users + user_groups pre-linked to household group with oidc_issuer = https://auth.vrg.rocks
  8. Readeck       "user" table pre-seeded with username + group + ext_id + preserve_lldap_user_identity trigger
  9. Copyparty     idp-hm-usr Remote-Email -> uid mappings in config/copyparty/copyparty.conf
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import sqlite3
import struct
import sys
from pathlib import Path

NO_KEYCHAIN_DIR = Path("/tmp/sol_no_keychain")
NO_KEYCHAIN_SHIM = NO_KEYCHAIN_DIR / "docker-credential-osxkeychain"
try:
    if not NO_KEYCHAIN_SHIM.exists():
        NO_KEYCHAIN_DIR.mkdir(parents=True, exist_ok=True)
        NO_KEYCHAIN_SHIM.write_text('#!/bin/sh\necho "{}"\n')
        NO_KEYCHAIN_SHIM.chmod(0o755)
except OSError:
    pass

os.environ["PATH"] = (
    f"{NO_KEYCHAIN_DIR}:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:"
    + os.environ.get("PATH", "")
)

BASE = Path(os.environ.get("SOL_BASE") or Path(__file__).resolve().parent.parent)
USERS_JSON = Path(os.environ.get("SOL_USERS_JSON") or BASE / "config/auth/users.json")
ENV_FILE = BASE / ".env"
WHITELIST = BASE / "data/tinyauth/whitelist.txt"
TINYAUTH_DB = BASE / "data/tinyauth/tinyauth.db"
LLDAP_DIR = BASE / "data/lldap"
LLDAP_DB = LLDAP_DIR / "users.db"
LLDAP_BOOT = LLDAP_DIR / "bootstrap"
LLDAP_SECRETS = LLDAP_DIR / "secrets"
JF_CONFIG_DIR = BASE / "config/jellyfin"
JF_PLUGIN_CFG = JF_CONFIG_DIR / "data/plugins/configurations"
SEERR_SETTINGS = BASE / "config/seerr/settings.json"
HOMEBOX_DB = BASE / "data/homebox/homebox.db"
READECK_DB = BASE / "data/readeck/data/db.sqlite3"
READECK_CONF = BASE / "data/readeck/config.toml"
COPYPARTY_CONF = BASE / "config/copyparty/copyparty.conf"
LOCK_FILE = Path("/tmp/sol_identity_sync.lock")
HASH_FILE = Path("/tmp/sol_identity_sync.sha256")


def _fast_decode_bincode(blob: bytes | None, is_list: bool) -> list[str]:
    if not blob:
        return []
    try:
        offset = 0
        if is_list:
            if len(blob) < 8:
                return []
            (count,) = struct.unpack_from("<Q", blob, offset)
            offset += 8
        else:
            count = 1
        out: list[str] = []
        for _ in range(count):
            if offset + 8 > len(blob):
                break
            (slen,) = struct.unpack_from("<Q", blob, offset)
            offset += 8
            if offset + slen > len(blob):
                break
            out.append(blob[offset : offset + slen].decode("utf-8", errors="replace"))
            offset += slen
        return out
    except Exception:
        return []


def read_lldap_sqlite() -> tuple[list[dict], dict[str, int], str]:
    """Read users, groups, memberships, and bincode attributes directly from lldap users.db?immutable=1."""
    if not LLDAP_DB.exists():
        sys.exit(f"LLDAP database not found at {LLDAP_DB}")
    con = sqlite3.connect(f"file:{LLDAP_DB}?immutable=1", uri=True)
    group_rows = con.execute("SELECT group_id, display_name FROM groups ORDER BY group_id").fetchall()
    groups_by_id = {gid: dname for gid, dname in group_rows}
    gql_groups = {dname: gid for gid, dname in group_rows}

    memberships: dict[str, list[dict]] = {}
    for uid, gid in con.execute("SELECT user_id, group_id FROM memberships ORDER BY user_id, group_id"):
        memberships.setdefault(uid, []).append({"id": gid, "displayName": groups_by_id.get(gid, "")})

    attrs_by_user: dict[str, dict[str, list[str]]] = {}
    attr_query = """
        SELECT ua.user_attribute_user_id, ua.user_attribute_name, ua.user_attribute_value,
               COALESCE(uas.user_attribute_schema_is_list, 0)
        FROM user_attributes ua
        LEFT JOIN user_attribute_schema uas
          ON ua.user_attribute_name = uas.user_attribute_schema_name
        ORDER BY ua.user_attribute_user_id, ua.user_attribute_name
    """
    for uid, name, val, is_list in con.execute(attr_query):
        attrs_by_user.setdefault(uid, {})[name] = _fast_decode_bincode(val, bool(is_list))

    users: list[dict] = []
    user_query = """
        SELECT user_id, COALESCE(email, ''), COALESCE(display_name, ''), COALESCE(uuid, ''),
               COALESCE(modified_date, ''), COALESCE(password_modified_date, '')
        FROM users
        ORDER BY user_id
    """
    for uid, email, display, u_uuid, mod_date, pw_mod_date in con.execute(user_query):
        ua = attrs_by_user.get(uid, {})
        users.append(
            {
                "id": uid,
                "email": email,
                "displayName": display,
                "firstName": (ua.get("first_name") or [""])[0],
                "lastName": (ua.get("last_name") or [""])[0],
                "uuid": u_uuid,
                "modifiedDate": str(mod_date),
                "passwordModifiedDate": str(pw_mod_date),
                "attributes": [{"name": k, "value": v} for k, v in sorted(ua.items())],
                "groups": memberships.get(uid, []),
            }
        )
    con.close()

    env_mtime_ns = ENV_FILE.stat().st_mtime_ns if ENV_FILE.exists() else 0
    digest_payload = {
        "users": users,
        "groups": [{"id": gid, "displayName": dname} for gid, dname in group_rows],
        "env_mtime_ns": env_mtime_ns,
    }
    state_hash = hashlib.sha256(json.dumps(digest_payload, sort_keys=True).encode("utf-8")).hexdigest()
    return users, gql_groups, state_hash


if __name__ == "__main__" and not any(flag in sys.argv[1:] for flag in ("--force", "--only", "-h", "--help")):
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    _fast_lock_fd = LOCK_FILE.open("w")
    fcntl.flock(_fast_lock_fd.fileno(), fcntl.LOCK_EX)
    if HASH_FILE.exists():
        _, _, _fast_hash = read_lldap_sqlite()
        if HASH_FILE.read_text().strip() == _fast_hash:
            print(f"SKIP   lldap state + .env unchanged (sha256={_fast_hash[:12]}...); exiting in <50ms.", flush=True)
            sys.exit(0)

import argparse
import re
import secrets
import shutil
import subprocess
import time
import uuid
import xml.etree.ElementTree as ET

LDAP_PROVIDER = "Jellyfin.Plugin.LDAP_Auth.LdapAuthenticationProviderPlugin"
DEFAULT_PROVIDER = "Jellyfin.Server.Implementations.Users.DefaultAuthenticationProvider"
CONSENT_SCOPE = "openid profile email groups"
USERS_JSON_COMMENT = (
    "Exported one-way identity snapshot generated from lldap (data/lldap/users.db) by scripts/identity_sync.py. "
    "Copy to config/auth/users.json or run scripts/identity_sync.py --apply."
)
JF_SSO_DISCLAIMER = (
    '<form action="/sso/OID/start/google-sso">'
    '<button class="raised button-submit block emby-button" type="submit">'
    "Sign in with Google SSO"
    "</button></form>"
)
UUID_RE = re.compile(r"^[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}$", re.I)
BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

APPLY = False
FORCE = False
UNREDACTED = False


def mask_email(e: str) -> str:
    if UNREDACTED or "@" not in e:
        return e
    local, dom = e.split("@", 1)
    return f"{local[:1]}***@{dom}"


def log(msg: str) -> None:
    print(msg, flush=True)


def act(msg: str) -> bool:
    """Print a planned action. Return True when the caller must execute it."""
    log(("APPLY  " if APPLY else "PLAN   ") + msg)
    return APPLY


def load_env(path: Path) -> dict:
    """Line-by-line .env parser."""
    env = {}
    if not path.exists():
        return env
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def docker(*args: str, check: bool = True, input_text: str | None = None) -> str:
    r = subprocess.run(["docker", *args], capture_output=True, text=True, input=input_text)
    if check and r.returncode != 0:
        raise RuntimeError(f"docker {' '.join(args[:3])} failed: {r.stderr.strip()[:300]}")
    return r.stdout


def norm_guid(g: str) -> str:
    g = g.replace("-", "").lower()
    return f"{g[0:8]}-{g[8:12]}-{g[12:16]}-{g[16:20]}-{g[20:32]}"


def tinyauth_username(email: str) -> str:
    return email.replace("@", "_", 1)


def oidc_sub(username: str, client_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{username}:{client_id}"))


# --------------------------------------------------------------------------- model & lldap SQLite pull


def load_users() -> dict:
    data = json.loads(USERS_JSON.read_text())
    seen_uid, seen_mail = set(), set()
    for u in data["users"]:
        uid = u["uid"]
        if uid != uid.lower() or not re.fullmatch(r"[a-z0-9_.-]+", uid):
            sys.exit(f"uid {uid!r} must be lowercase [a-z0-9_.-] (lldap lowercases user ids)")
        if uid in seen_uid:
            sys.exit(f"duplicate uid {uid}")
        seen_uid.add(uid)
        if not u.get("emails"):
            sys.exit(f"{uid}: at least one email is required")
        u["emails"] = [e.strip().lower() for e in u["emails"]]
        for e in u["emails"]:
            if e in seen_mail:
                sys.exit(f"email {e} is listed twice")
            seen_mail.add(e)
        if u.get("role") not in ("admin", "user"):
            sys.exit(f"{uid}: role must be admin or user")
        if u.get("jellyfin_id"):
            if not UUID_RE.match(u["jellyfin_id"]):
                sys.exit(f"{uid}: bad jellyfin_id")
            u["jellyfin_id"] = norm_guid(u["jellyfin_id"])
    return data


def prune_lldap_jwt_storage() -> None:
    """Clean up accumulated headless admin JWT rows in data/lldap/users.db during --force runs."""
    if not LLDAP_DB.exists():
        return
    con = sqlite3.connect(f"file:{LLDAP_DB}?immutable=1", uri=True)
    jwt_cnt = con.execute("SELECT COUNT(*) FROM jwt_storage WHERE user_id = 'admin'").fetchone()[0]
    ref_cnt = con.execute("SELECT COUNT(*) FROM jwt_refresh_storage WHERE user_id = 'admin'").fetchone()[0]
    con.close()
    if (jwt_cnt or ref_cnt) and act(
        f"lldap: prune {jwt_cnt} jwt_storage + {ref_cnt} jwt_refresh_storage stale admin rows"
    ):
        wcon = sqlite3.connect(str(LLDAP_DB), timeout=10.0)
        wcon.execute("DELETE FROM jwt_storage WHERE user_id = 'admin'")
        wcon.execute("DELETE FROM jwt_refresh_storage WHERE user_id = 'admin'")
        wcon.commit()
        wcon.close()


def lldap_graphql(query: str, variables: dict | None = None) -> dict:
    """Invoke LLDAP GraphQL API only when mutating LLDAP group memberships (never for read-only polling)."""
    payload = json.dumps({"query": query, "variables": variables or {}})
    script = (
        "PW_FILE=/data/secrets/vrg.pw; USER=vrg; "
        "[ -f /data/secrets/vrg.pw ] || { PW_FILE=/data/secrets/admin.pw; USER=admin; }; "
        "TOKEN=$(curl -s -X POST localhost:17170/auth/simple/login -H 'Content-Type: application/json' "
        '-d "{\\"username\\":\\"$USER\\",\\"password\\":\\"$(cat $PW_FILE)\\"}" | jq -r .token); '
        'curl -s localhost:17170/api/graphql -H "Authorization: Bearer $TOKEN" -H \'Content-Type: application/json\' '
        "--data-binary @-"
    )
    out = docker("exec", "-i", "lldap", "sh", "-c", script, input_text=payload)
    return json.loads(out)


def pull_from_lldap(data: dict, gql_users: list[dict], gql_groups: dict[str, int]) -> bool:
    """Reconcile users read from lldap SQLite into data['users']."""
    log("\n== Pull from lldap (SQLite immutable=1) ==")
    jf_users_gid = gql_groups.get("jellyfin_users")

    by_uid = {u["uid"]: u for u in data["users"]}
    new_users_list = []
    dirty = False

    if data.get("_comment") != USERS_JSON_COMMENT:
        data["_comment"] = USERS_JSON_COMMENT
        dirty = True

    for gu in gql_users:
        uid = gu["id"].strip().lower()
        if uid in ("admin", "svc_bind"):
            continue
        primary_email = (gu.get("email") or "").strip().lower()
        if not primary_email:
            log(f"WARN   lldap user {uid!r} has no email address; skipping until email is set")
            continue

        group_names = {g["displayName"] for g in gu.get("groups", [])}
        if jf_users_gid and "jellyfin_users" not in group_names:
            if act(f"lldap: auto-add {uid} to group jellyfin_users"):
                lldap_graphql(
                    f'mutation {{ addUserToGroup(userId: "{gu["id"]}", groupId: {jf_users_gid}) {{ ok }} }}'
                )

        attrs = {a["name"]: a["value"] for a in gu.get("attributes", [])}
        aliases = [e.strip().lower() for e in attrs.get("mailalias", []) if e.strip()]
        emails = list(dict.fromkeys([primary_email] + aliases))
        role = "admin" if ("jellyfin_admin" in group_names or "lldap_admin" in group_names or uid == "vrg") else "user"
        display = (gu.get("displayName") or uid).strip()
        first_name = (gu.get("firstName") or "").strip()
        last_name = (gu.get("lastName") or "").strip()

        existing = by_uid.get(uid)
        masked_emails = [mask_email(e) for e in emails]
        if existing:
            if (
                existing["emails"] != emails
                or existing["display"] != display
                or existing["role"] != role
                or (first_name and existing.get("first_name") != first_name)
                or (last_name and existing.get("last_name") != last_name)
            ):
                log(f"INFO   lldap updated user {uid}: emails={masked_emails} display={display} role={role}")
                existing["emails"] = emails
                existing["display"] = display
                existing["role"] = role
                if first_name:
                    existing["first_name"] = first_name
                if last_name:
                    existing["last_name"] = last_name
                dirty = True
            new_users_list.append(existing)
        else:
            log(f"INFO   lldap added new user {uid}: emails={masked_emails} display={display} role={role}")
            entry = {
                "uid": uid,
                "display": display,
                "emails": emails,
                "role": role,
                "jellyfin_id": None,
                "seerr_id": None,
            }
            if first_name:
                entry["first_name"] = first_name
            if last_name:
                entry["last_name"] = last_name
            new_users_list.append(entry)
            dirty = True

    removed = set(by_uid.keys()) - {u["uid"] for u in new_users_list}
    if removed:
        log(f"INFO   lldap removed users: {sorted(removed)}")
        dirty = True

    if dirty:
        data["users"] = new_users_list
    return dirty


def all_emails(data: dict) -> list:
    return [e for u in data["users"] for e in u["emails"]]


# --------------------------------------------------------------------------- 1. Tinyauth


def sync_tinyauth(data: dict, env: dict) -> None:
    log("\n== Tinyauth ==")
    want = all_emails(data)
    have = (
        [l.strip().lower() for l in WHITELIST.read_text().splitlines() if l.strip() and not l.startswith("#")]
        if WHITELIST.exists()
        else []
    )
    changed = set(have) != set(want)
    if changed and act(f"write {WHITELIST.relative_to(BASE)} ({len(want)} emails)"):
        WHITELIST.write_text("\n".join(want) + "\n")
    csv = ",".join(want)
    if set(filter(None, env.get("TINYAUTH_OAUTH_WHITELIST", "").lower().split(","))) != set(want):
        changed = True
        if act("set .env TINYAUTH_OAUTH_WHITELIST"):
            text = ENV_FILE.read_text()
            if re.search(r"^TINYAUTH_OAUTH_WHITELIST=", text, flags=re.M):
                text = re.sub(r"^TINYAUTH_OAUTH_WHITELIST=.*$", f"TINYAUTH_OAUTH_WHITELIST={csv}", text, flags=re.M)
            else:
                text += f"\nTINYAUTH_OAUTH_WHITELIST={csv}\n"
            ENV_FILE.write_text(text)

    client_ids = sorted({v for k, v in env.items() if re.fullmatch(r"TINYAUTH_OIDC_[A-Z0-9_]+_CLIENT_ID", k) and v})
    admin_only_clients = {
        env.get("TINYAUTH_OIDC_ARCANE_CLIENT_ID"),
        env.get("TINYAUTH_OIDC_CODER_CLIENT_ID"),
    } - {None, ""}
    admin_emails = {e for u in data["users"] if u.get("role") == "admin" for e in u["emails"]}
    wanted_pairs = {
        (tinyauth_username(e), c)
        for e in want
        for c in client_ids
        if c not in admin_only_clients or e in admin_emails
    }

    con = sqlite3.connect(f"file:{TINYAUTH_DB}?immutable=1", uri=True)
    rows = set(con.execute("SELECT username, client_id FROM oidc_consents").fetchall())
    con.close()
    missing = sorted(wanted_pairs - rows)
    stale_pairs = sorted((u, c) for (u, c) in rows if (u, c) not in wanted_pairs and u.lower() != "vrg")
    log(
        f"INFO   {len(client_ids)} OIDC clients, {len(missing)} consent rows missing, "
        f"{len(stale_pairs)} stale/non-admin consent rows to prune"
    )
    if (missing or stale_pairs or changed) and act("stop tinyauth, sync consents, start tinyauth"):
        docker("stop", "tinyauth", check=False)
        con = sqlite3.connect(str(TINYAUTH_DB))
        now = int(time.time())
        if missing:
            con.executemany(
                "INSERT INTO oidc_consents (username, client_id, scope, created_at) VALUES (?,?,?,?) "
                "ON CONFLICT(username, client_id) DO UPDATE SET scope = excluded.scope",
                [(u, c, CONSENT_SCOPE, now) for (u, c) in missing],
            )
        if stale_pairs:
            con.executemany(
                "DELETE FROM oidc_consents WHERE username = ? AND client_id = ?",
                stale_pairs,
            )
        con.commit()
        con.close()
        subprocess.run(["docker", "compose", "up", "-d", "tinyauth"], cwd=BASE, check=True)


# --------------------------------------------------------------------------- 2. Jellyfin


def jf_token(env: dict) -> str:
    if env.get("JELLYFIN_API_KEY"):
        return env["JELLYFIN_API_KEY"]
    db = BASE / "config/jellyfin/data/data/jellyfin.db"
    con = sqlite3.connect(f"file:{db}?immutable=1", uri=True)
    row = con.execute("select AccessToken from ApiKeys order by DateCreated desc limit 1").fetchone()
    con.close()
    if not row:
        sys.exit("No JELLYFIN_API_KEY in .env and no ApiKeys row in jellyfin.db")
    return row[0]


def jf(token: str, method: str, path: str, body=None):
    cmd = [
        "exec",
        "-i",
        "jellyfin",
        "curl",
        "-s",
        "-X",
        method,
        f"http://localhost:8096{path}",
        "-H",
        f'Authorization: MediaBrowser Token="{token}"',
        "-H",
        "Content-Type: application/json",
    ]
    if body is not None:
        cmd += ["--data-binary", "@-"]
    out = docker(*cmd, input_text=json.dumps(body) if body is not None else None)
    return json.loads(out) if out.strip().startswith(("{", "[")) else out


def sync_jellyfin(data: dict, env: dict) -> bool:
    log("\n== Jellyfin ==")
    token = jf_token(env)
    users = {norm_guid(u["Id"]): u for u in jf(token, "GET", "/Users")}
    by_name = {u["Name"].upper(): norm_guid(u["Id"]) for u in users.values()}
    dirty_json = False
    jf_renames: list[tuple[str, str, str]] = []
    for u in data["users"]:
        jid = u.get("jellyfin_id")
        if not jid and u["display"].upper() in by_name:
            jid = by_name[u["display"].upper()]
            log(f"INFO   {u['uid']}: matched existing Jellyfin user {u['display']} = {jid}")
        if not jid:
            if act(f"create Jellyfin user {u['display']} (random local pw, LDAP becomes the provider)"):
                r = jf(token, "POST", "/Users/New", {"Name": u["display"], "Password": secrets.token_urlsafe(24)})
                jid = norm_guid(r["Id"])
                users[jid] = jf(token, "GET", f"/Users/{jid.replace('-', '')}")
        if jid and jid != u.get("jellyfin_id"):
            u["jellyfin_id"] = jid
            dirty_json = True
        if not jid or jid not in users:
            continue
        ju = users[jid]
        if ju.get("Name") != u["display"]:
            jf_renames.append((jid, ju.get("Name", ""), u["display"]))
        pol = ju["Policy"]
        if pol.get("AuthenticationProviderId") != LDAP_PROVIDER and act(
            f"{u['display']}: AuthenticationProviderId -> LDAP-Auth"
        ):
            pol["AuthenticationProviderId"] = LDAP_PROVIDER
            pol["PasswordResetProviderId"] = LDAP_PROVIDER
            jf(token, "POST", f"/Users/{jid.replace('-', '')}/Policy", pol)

    ldap_path = JF_PLUGIN_CFG / "LDAP-Auth.xml"
    ldap_tree = ET.parse(ldap_path)
    ldap_root = ldap_tree.getroot()
    bind_pw_file = LLDAP_SECRETS / "svc_bind.pw"
    bind_pw = bind_pw_file.read_text().strip() if bind_pw_file.exists() else "PENDING_SVC_BIND_PW"
    want_ldap = {
        "LdapServer": "lldap",
        "LdapPort": "3890",
        "UseSsl": "false",
        "UseStartTls": "false",
        "SkipSslVerify": "false",
        "LdapBindUser": f"uid=svc_bind,ou=people,{data['defaults']['ldap_base_dn']}",
        "LdapBindPassword": bind_pw,
        "LdapBaseDn": f"ou=people,{data['defaults']['ldap_base_dn']}",
        "LdapSearchFilter": f"(memberOf=cn=jellyfin_users,ou=groups,{data['defaults']['ldap_base_dn']})",
        "LdapAdminBaseDn": "",
        "LdapAdminFilter": f"(memberOf=cn=jellyfin_admin,ou=groups,{data['defaults']['ldap_base_dn']})",
        "EnableLdapAdminFilterMemberUid": "false",
        "LdapSearchAttributes": "uid, mail, mailalias",
        "CreateUsersFromLdap": "true",
        "AllowPassChange": "false",
        "LdapUidAttribute": "entryUUID",
        "LdapUsernameAttribute": "cn",
        "EnableAllFolders": "true",
    }
    ldap_edits = [k for k, v in want_ldap.items() if (ldap_root.findtext(k) or "").strip() != v]

    sso_path = JF_PLUGIN_CFG / "SSO-Auth.xml"
    tree = ET.parse(sso_path)
    provider = data["defaults"]["jellyfin_sso_provider"]
    pc = None
    for item in tree.getroot().find("OidConfigs"):
        if item.find("key/string").text == provider:
            pc = item.find("value/PluginConfiguration")
    if pc is None:
        sys.exit(f"SSO-Auth.xml has no OidConfigs item {provider!r}")
    want_links = {e: u["jellyfin_id"] for u in data["users"] if u.get("jellyfin_id") for e in u["emails"]}
    cl = pc.find("CanonicalLinks")
    have_links = {i.find("key/string").text: i.find("value/guid").text for i in cl} if cl is not None else {}

    branding_path = JF_CONFIG_DIR / "branding.xml"
    branding_tree = ET.parse(branding_path) if branding_path.exists() else None
    branding_disc = (branding_tree.getroot().findtext("LoginDisclaimer") or "").strip() if branding_tree else ""

    edits = []
    if jf_renames:
        edits.append("Jellyfin Users rename: " + ", ".join(f"{old}->{new}" for _, old, new in jf_renames))
    if ldap_edits:
        edits.append("LDAP-Auth.xml -> lldap:3890 (uid, mail, mailalias -> cn)")
    if (pc.findtext("DefaultProvider") or "").strip() != LDAP_PROVIDER:
        edits.append("SSO-Auth DefaultProvider -> LDAP-Auth")
    if (pc.findtext("DefaultUsernameClaim") or "").strip() != "email":
        edits.append("SSO-Auth DefaultUsernameClaim -> email")
    if (pc.findtext("SchemeOverride") or "").strip() != "https":
        edits.append("SSO-Auth SchemeOverride -> https")
    if have_links != want_links:
        edits.append(f"SSO-Auth CanonicalLinks -> {len(want_links)} email links")
    if branding_tree and branding_disc != JF_SSO_DISCLAIMER:
        edits.append("branding.xml LoginDisclaimer -> 'Sign in with Google SSO' button")

    if edits and act("stop jellyfin, edit XMLs: " + "; ".join(edits)):
        docker("stop", "jellyfin")
        ts = int(time.time())
        if jf_renames:
            jf_db = BASE / "config/jellyfin/data/data/jellyfin.db"
            con = sqlite3.connect(str(jf_db))
            for jid, _, new_name in jf_renames:
                con.execute("UPDATE Users SET Username = ? WHERE UPPER(Id) = UPPER(?)", (new_name, jid))
            con.commit()
            con.close()
        if ldap_edits:
            shutil.copy2(ldap_path, ldap_path.with_suffix(f".xml.bak.{ts}"))
            if bind_pw_file.exists():
                want_ldap["LdapBindPassword"] = bind_pw_file.read_text().strip()
            for k, v in want_ldap.items():
                el = ldap_root.find(k)
                if el is None:
                    el = ET.SubElement(ldap_root, k)
                el.text = v if v != "" else None
            ET.indent(ldap_tree, space="  ")
            ldap_tree.write(ldap_path, encoding="utf-8", xml_declaration=True)
        shutil.copy2(sso_path, sso_path.with_suffix(f".xml.bak.{ts}"))

        def setel(tag, text):
            el = pc.find(tag)
            if el is None:
                el = ET.SubElement(pc, tag)
            el.text = text

        setel("DefaultProvider", LDAP_PROVIDER)
        setel("DefaultUsernameClaim", "email")
        setel("SchemeOverride", "https")
        if cl is None:
            cl = ET.SubElement(pc, "CanonicalLinks")
        for child in list(cl):
            cl.remove(child)
        for email, jid in sorted(want_links.items()):
            it = ET.SubElement(cl, "item")
            ET.SubElement(ET.SubElement(it, "key"), "string").text = email
            ET.SubElement(ET.SubElement(it, "value"), "guid").text = jid
        ET.indent(tree, space="  ")
        tree.write(sso_path, encoding="utf-8", xml_declaration=True)

        if branding_tree and branding_disc != JF_SSO_DISCLAIMER:
            broot = branding_tree.getroot()
            ld = broot.find("LoginDisclaimer")
            if ld is None:
                ld = ET.SubElement(broot, "LoginDisclaimer")
            ld.text = JF_SSO_DISCLAIMER
            ET.indent(branding_tree, space="  ")
            branding_tree.write(branding_path, encoding="utf-8", xml_declaration=True)

        docker("start", "jellyfin")
        for _ in range(30):
            time.sleep(1)
            try:
                out = docker(
                    "exec",
                    "jellyfin",
                    "curl",
                    "-s",
                    "http://localhost:8096/Users",
                    "-H",
                    f'Authorization: MediaBrowser Token="{token}"',
                    check=False,
                )
                if out.strip().startswith("["):
                    break
            except Exception:
                pass
    return dirty_json


# --------------------------------------------------------------------------- 4. Seerr


def seerr(api_key: str, method: str, path: str, body=None):
    cmd = [
        "exec",
        "seerr",
        "wget",
        "-qO-",
        f"--header=X-Api-Key: {api_key}",
        "--header=Content-Type: application/json",
    ]
    if method == "POST":
        cmd.append("--post-data=" + json.dumps(body or {}))
    cmd.append(f"http://localhost:5055/api/v1{path}")
    out = docker(*cmd)
    return json.loads(out) if out.strip() else None


def sync_seerr(data: dict) -> bool:
    log("\n== Seerr ==")
    api_key = json.loads(SEERR_SETTINGS.read_text())["main"]["apiKey"]
    have = seerr(api_key, "GET", "/user?take=500")["results"]
    by_jf = {(s.get("jellyfinUserId") or "").replace("-", "").lower(): s for s in have}
    dirty_json = False
    for u in data["users"]:
        if not u.get("jellyfin_id"):
            continue
        key = u["jellyfin_id"].replace("-", "")
        s = by_jf.get(key)
        if s is None and act(f"import Jellyfin user {u['display']} into Seerr"):
            seerr(api_key, "POST", "/user/import-from-jellyfin", {"jellyfinUserIds": [key]})
            have = seerr(api_key, "GET", "/user?take=500")["results"]
            s = {(x.get("jellyfinUserId") or "").replace("-", "").lower(): x for x in have}.get(key)
        if s is None:
            continue
        if s["id"] != u.get("seerr_id"):
            u["seerr_id"] = s["id"]
            dirty_json = True
        if (s.get("email") or "").lower() != u["emails"][0] and act(
            f"Seerr user {s['id']} ({u['display']}): email -> {mask_email(u['emails'][0])}"
        ):
            main = seerr(api_key, "GET", f"/user/{s['id']}/settings/main")
            main["email"] = u["emails"][0]
            seerr(api_key, "POST", f"/user/{s['id']}/settings/main", main)
        if (s.get("jellyfinUsername") or "") != u["display"] and act(
            f"Seerr user {s['id']}: jellyfinUsername -> {u['display']}"
        ):
            seerr_db = BASE / "config/seerr/db/db.sqlite3"
            if seerr_db.exists():
                docker("stop", "seerr", check=False)
                con = sqlite3.connect(str(seerr_db))
                con.execute("UPDATE user SET jellyfinUsername = ? WHERE id = ?", (u["display"], s["id"]))
                con.commit()
                con.close()
                docker("start", "seerr", check=False)
    return dirty_json


# --------------------------------------------------------------------------- 5. OIDC Apps (Paperless, AirTrail, Homebox, Readeck)


def sync_oidc_apps(data: dict, env: dict) -> None:
    log("\n== OIDC Apps (Paperless-ngx, AirTrail, Homebox, Readeck) ==")
    # 5a. Paperless-ngx (auth_user + auth_user_groups + socialaccount_socialaccount)
    pl_cid = env.get("TINYAUTH_OIDC_PAPERLESS_CLIENT_ID")
    if pl_cid:
        raw_users = docker(
            "exec",
            "paperless-db",
            "psql",
            "-U",
            "paperless",
            "-d",
            "paperless",
            "-t",
            "-A",
            "-c",
            "SELECT id, username, lower(email), COALESCE(first_name, ''), COALESCE(last_name, '') FROM auth_user;",
        )
        pl_by_email, pl_by_name, pl_rows = {}, {}, {}
        for line in raw_users.strip().splitlines():
            if "|" in line:
                uid_s, uname, mail, fname, lname = line.split("|", 4)
                pid = int(uid_s)
                pl_rows[pid] = (uname, mail, fname, lname)
                pl_by_name[uname.upper()] = pid
                if mail:
                    pl_by_email[mail] = pid
        raw_sa = docker(
            "exec",
            "paperless-db",
            "psql",
            "-U",
            "paperless",
            "-d",
            "paperless",
            "-t",
            "-A",
            "-c",
            "SELECT uid, user_id FROM socialaccount_socialaccount WHERE provider='tinyauth';",
        )
        have_sa = {}
        for line in raw_sa.strip().splitlines():
            if "|" in line:
                s_uid, s_user_id = line.split("|", 1)
                have_sa[s_uid] = int(s_user_id)
        raw_ug = docker(
            "exec",
            "paperless-db",
            "psql",
            "-U",
            "paperless",
            "-d",
            "paperless",
            "-t",
            "-A",
            "-c",
            "SELECT ug.user_id FROM auth_user_groups ug JOIN auth_group g ON ug.group_id = g.id WHERE g.name = 'Family';",
        )
        in_family_grp = {int(x) for x in raw_ug.strip().splitlines() if x.strip().isdigit()}

        for u in data["users"]:
            email = u["emails"][0]
            fname = (u.get("first_name") or "").replace("'", "''")
            lname = (u.get("last_name") or "").replace("'", "''")
            disp = u["display"].replace("'", "''")
            mail_esc = email.replace("'", "''")
            pl_id = None
            for e in u["emails"]:
                pl_id = pl_id or pl_by_email.get(e) or have_sa.get(oidc_sub(tinyauth_username(e), pl_cid))
            pl_id = pl_id or pl_by_name.get(u["display"].upper())
            if not pl_id and act(f"Paperless-ngx: create user {u['display']} ({mask_email(email)})"):
                is_sup = "true" if u["role"] == "admin" else "false"
                sql = (
                    f"INSERT INTO auth_user (password, is_superuser, username, first_name, last_name, email, is_staff, is_active, date_joined) "
                    f"VALUES ('!', {is_sup}, '{disp}', '{fname}', '{lname}', '{mail_esc}', {is_sup}, true, NOW()) RETURNING id;"
                )
                out = docker(
                    "exec", "paperless-db", "psql", "-U", "paperless", "-d", "paperless", "-t", "-A", "-c", sql
                )
                pl_id = int(out.strip().splitlines()[0])
            elif pl_id and pl_id in pl_rows:
                cur_uname, cur_mail, cur_fname, cur_lname = pl_rows[pl_id]
                if (
                    cur_uname != u["display"]
                    or cur_mail != email
                    or cur_fname != (u.get("first_name") or "")
                    or cur_lname != (u.get("last_name") or "")
                ) and act(f"Paperless-ngx: update user_id={pl_id} -> username={u['display']}"):
                    sql = (
                        f"UPDATE auth_user SET username='{disp}', first_name='{fname}', last_name='{lname}', email='{mail_esc}' "
                        f"WHERE id={pl_id};"
                    )
                    docker("exec", "paperless-db", "psql", "-U", "paperless", "-d", "paperless", "-c", sql)
            if pl_id:
                if pl_id not in in_family_grp and act(
                    f"Paperless-ngx: add {u['display']} (user_id={pl_id}) to group 'Family'"
                ):
                    sql = (
                        f"INSERT INTO auth_user_groups (user_id, group_id) "
                        f"SELECT {pl_id}, id FROM auth_group WHERE name='Family' ON CONFLICT DO NOTHING;"
                    )
                    docker("exec", "paperless-db", "psql", "-U", "paperless", "-d", "paperless", "-c", sql)
                for e in u["emails"]:
                    sub = oidc_sub(tinyauth_username(e), pl_cid)
                    if sub not in have_sa and act(
                        f"Paperless-ngx: link socialaccount {mask_email(e)} -> user_id={pl_id}"
                    ):
                        extra = json.dumps({"email": e, "name": u["display"]}).replace("'", "''")
                        sql = (
                            f"INSERT INTO socialaccount_socialaccount (provider, uid, last_login, date_joined, extra_data, user_id) "
                            f"VALUES ('tinyauth', '{sub}', NOW(), NOW(), '{extra}'::jsonb, {pl_id}) "
                            f"ON CONFLICT (provider, uid) DO UPDATE SET user_id = EXCLUDED.user_id, extra_data = EXCLUDED.extra_data;"
                        )
                        docker("exec", "paperless-db", "psql", "-U", "paperless", "-d", "paperless", "-c", sql)

    # 5b. AirTrail ("user" table in airtrail DB)
    at_cid = env.get("TINYAUTH_OIDC_AIRTRAIL_CLIENT_ID")
    if at_cid:
        raw_at = docker(
            "exec",
            "paperless-db",
            "psql",
            "-U",
            "paperless",
            "-d",
            "airtrail",
            "-t",
            "-A",
            "-c",
            'SELECT username, COALESCE(oauth_id, \'\') FROM "user";',
        )
        at_have = set()
        at_by_oauth = {}
        for line in raw_at.strip().splitlines():
            if "|" in line:
                uname, oid = line.split("|", 1)
                at_have.add(uname.upper())
                if oid:
                    at_by_oauth[oid] = uname
        for u in data["users"]:
            sub = oidc_sub(tinyauth_username(u["emails"][0]), at_cid)
            disp = u["display"].replace("'", "''")
            if sub in at_by_oauth and at_by_oauth[sub] != u["display"]:
                if act(f"AirTrail: rename user {at_by_oauth[sub]} -> {u['display']}"):
                    sql = f"UPDATE \"user\" SET username='{disp}', display_name='{disp}' WHERE oauth_id='{sub}';"
                    docker("exec", "paperless-db", "psql", "-U", "paperless", "-d", "airtrail", "-c", sql)
            elif (
                sub not in at_by_oauth
                and u["display"].upper() not in at_have
                and act(f"AirTrail: seed user {u['display']} (oauth_id={sub[:8]}...)")
            ):
                uid_row = f"{u['uid']}-{secrets.token_hex(4)}"[:15]
                is_primary_owner = (u.get("uid") or u.get("user_id") or "").lower() == "vrg"
                is_owner = "true" if is_primary_owner else "false"
                role_val = (
                    "NULL"
                    if is_primary_owner
                    else ("'role-administrator'" if u["role"] == "admin" else "'role-user'")
                )
                sql = (
                    f'INSERT INTO "user" (id, username, password, display_name, oauth_id, is_owner, role_id) '
                    f"VALUES ('{uid_row}', '{disp}', NULL, '{disp}', '{sub}', {is_owner}, {role_val}) "
                    f"ON CONFLICT (oauth_id) DO NOTHING;"
                )
                docker("exec", "paperless-db", "psql", "-U", "paperless", "-d", "airtrail", "-c", sql)

    # 5c. Homebox (users + user_groups in data/homebox/homebox.db)
    hb_cid = env.get("TINYAUTH_OIDC_HOMEBOX_CLIENT_ID")
    if hb_cid and HOMEBOX_DB.exists():
        con = sqlite3.connect(f"file:{HOMEBOX_DB}?immutable=1", uri=True)
        grp_row = con.execute("SELECT id FROM groups LIMIT 1").fetchone()
        hb_group = grp_row[0] if grp_row else None
        hb_users = {
            r[0].lower(): (r[1], r[2], r[3], r[4])
            for r in con.execute("SELECT email, id, oidc_issuer, oidc_subject, COALESCE(name, '') FROM users")
        }
        con.close()
        hb_actions = []
        for u in data["users"]:
            email = u["emails"][0]
            sub = oidc_sub(tinyauth_username(email), hb_cid)
            if email not in hb_users:
                hb_actions.append(("insert", u, email, sub))
            elif (
                hb_users[email][1] != "https://auth.vrg.rocks"
                or hb_users[email][2] != sub
                or hb_users[email][3] != u["display"]
            ):
                hb_actions.append(("update", u, email, sub))
        if hb_actions and hb_group and act(
            f"Homebox: stop container and sync {len(hb_actions)} user(s) into group {hb_group[:8]}..."
        ):
            docker("stop", "homebox", check=False)
            con = sqlite3.connect(str(HOMEBOX_DB))
            for kind, u, email, sub in hb_actions:
                is_sup = 1 if u["role"] == "admin" else 0
                if kind == "insert":
                    new_id = str(uuid.uuid4())
                    con.execute(
                        "INSERT INTO users (id, created_at, updated_at, name, email, password, is_superuser, superuser, "
                        "activated_on, oidc_issuer, oidc_subject, default_group_id, settings) "
                        "VALUES (?, datetime('now'), datetime('now'), ?, ?, '', ?, ?, datetime('now'), "
                        "'https://auth.vrg.rocks', ?, ?, '{}')",
                        (new_id, u["display"], email, is_sup, is_sup, sub, hb_group),
                    )
                    con.execute(
                        "INSERT OR IGNORE INTO user_groups (user_id, group_id, role) VALUES (?, ?, ?)",
                        (new_id, hb_group, "owner" if is_sup else "user"),
                    )
                else:
                    con.execute(
                        "UPDATE users SET name=?, oidc_issuer='https://auth.vrg.rocks', oidc_subject=?, default_group_id=? WHERE lower(email)=?",
                        (u["display"], sub, hb_group, email),
                    )
            con.commit()
            con.close()
            docker("start", "homebox", check=False)

    # 5d. Readeck (users + preserve_lldap_user_identity trigger in data/readeck/data/db.sqlite3)
    rd_cid = env.get("TINYAUTH_OIDC_READECK_CLIENT_ID")
    if READECK_CONF.exists():
        conf_text = READECK_CONF.read_text()
        cleaned_conf = re.sub(r'^(id\s*=\s*"tinyauth"|issuer\s*=\s*"https://auth\.vrg\.rocks")\s*\n', "", conf_text, flags=re.M)
        if cleaned_conf != conf_text and act("Readeck: remove unrecognized id/issuer keys from data/readeck/config.toml"):
            READECK_CONF.write_text(cleaned_conf)
    if rd_cid and READECK_DB.exists():
        con = sqlite3.connect(f"file:{READECK_DB}?immutable=1", uri=True)
        rd_rows = con.execute(
            'SELECT id, username, lower(email), "group", COALESCE(ext_id, \'\') FROM "user"'
        ).fetchall()
        has_trigger = (
            con.execute(
                "SELECT 1 FROM sqlite_master WHERE type='trigger' AND name='preserve_lldap_user_identity'"
            ).fetchone()
            is not None
        )
        con.close()

        rd_by_email = {r[2]: r for r in rd_rows}
        rd_by_uname = {r[1].upper(): r for r in rd_rows}
        rd_actions = []
        for u in data["users"]:
            email = u["emails"][0]
            sub = oidc_sub(tinyauth_username(email), rd_cid)
            ext_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"https://auth.vrg.rocks#{sub}"))
            want_grp = "admin" if u["role"] == "admin" else "user"
            row = rd_by_email.get(email) or rd_by_uname.get(u["display"].upper())
            if row is None:
                rd_actions.append(("insert", None, u["display"], email, want_grp, ext_id))
            else:
                rid, cur_uname, cur_email, cur_grp, cur_ext_id = row
                if cur_uname != u["display"] or cur_email != email or cur_grp != want_grp or cur_ext_id != ext_id:
                    rd_actions.append(("update", rid, u["display"], email, want_grp, ext_id))

        if (rd_actions or not has_trigger) and act(
            f"Readeck: sync {len(rd_actions)} user(s) + preserve_lldap_user_identity trigger"
        ):
            docker("stop", "readeck", check=False)
            con = sqlite3.connect(str(READECK_DB))
            con.execute("DROP TRIGGER IF EXISTS preserve_lldap_user_identity")
            for kind, rid, uname, email, want_grp, ext_id in rd_actions:
                if kind == "insert":
                    new_uid = "".join(secrets.choice(BASE58_ALPHABET) for _ in range(22))
                    seed = secrets.randbelow(9000) + 1000
                    con.execute(
                        'INSERT INTO "user" (uid, created, updated, last_login, username, email, password, "group", '
                        "settings, seed, totp_secret, ext_id, ext_info) "
                        "VALUES (?, strftime('%Y-%m-%d %H:%M:%f000+00:00', 'now'), "
                        "strftime('%Y-%m-%d %H:%M:%f000+00:00', 'now'), '0001-01-01 00:00:00+00:00', "
                        "?, ?, '', ?, 'null', ?, NULL, ?, NULL)",
                        (new_uid, uname, email, want_grp, seed, ext_id),
                    )
                else:
                    con.execute(
                        'UPDATE "user" SET username = ?, email = ?, "group" = ?, ext_id = ?, '
                        "updated = strftime('%Y-%m-%d %H:%M:%f000+00:00', 'now') WHERE id = ?",
                        (uname, email, want_grp, ext_id, rid),
                    )
            con.execute(
                """
                CREATE TRIGGER IF NOT EXISTS preserve_lldap_user_identity
                AFTER UPDATE ON "user"
                WHEN OLD.ext_id IS NOT NULL
                BEGIN
                    UPDATE "user"
                    SET username = OLD.username,
                        "group" = OLD."group"
                    WHERE id = NEW.id;
                END
                """
            )
            con.commit()
            con.close()
            docker("start", "readeck", check=False)


# --------------------------------------------------------------------------- 6. Copyparty


def sync_copyparty(data: dict) -> None:
    log("\n== Copyparty ==")
    if not COPYPARTY_CONF.exists():
        return
    text = COPYPARTY_CONF.read_text()
    want_lines = [f"  idp-hm-usr: ^Remote-Email^{e}^{u['uid']}" for u in data["users"] for e in u["emails"]]
    have_lines = [l for l in text.splitlines() if l.strip().startswith("idp-hm-usr:")]
    if have_lines != want_lines and act(f"update Copyparty idp-hm-usr mappings ({len(want_lines)} emails)"):
        lines = [l for l in text.splitlines() if not l.strip().startswith("idp-hm-usr:")]
        out_lines = []
        inserted = False
        for l in lines:
            out_lines.append(l)
            if l.strip().startswith("idp-h-usr:") and not inserted:
                out_lines.extend(want_lines)
                inserted = True
        COPYPARTY_CONF.write_text("\n".join(out_lines) + "\n")
        docker("restart", "copyparty", check=False)


# --------------------------------------------------------------------------- report & main


def report(data: dict, env: dict) -> None:
    log("\n== Identity map ==")
    client_ids = {k: v for k, v in env.items() if re.fullmatch(r"TINYAUTH_OIDC_[A-Z0-9_]+_CLIENT_ID", k)}
    for u in data["users"]:
        log(
            f"{u['uid']:8} {u['display']:8} role={u['role']:5} jellyfin={u.get('jellyfin_id')} seerr={u.get('seerr_id')}"
        )
        for e in u["emails"]:
            subs = ", ".join(
                f"{k.split('_')[2].lower()}={oidc_sub(tinyauth_username(e), v)[:8]}"
                for k, v in sorted(client_ids.items())
            )
            log(f"           {mask_email(e):30} tinyauth={mask_email(tinyauth_username(e))}  sub: {subs}")


def main() -> None:
    global APPLY, FORCE, UNREDACTED
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="execute the plan (default is dry-run unless --force)")
    ap.add_argument("--force", action="store_true", help="bypass SHA-256 fast-path cache and apply full sync")
    ap.add_argument("--dry-run", action="store_true", help="force dry-run even when --force is passed")
    ap.add_argument("--unredacted", action="store_true", help="show full email addresses in log output")
    ap.add_argument(
        "--from-lldap",
        action="store_true",
        help="accepted for compatibility (one-way pull from lldap SQLite is always active)",
    )
    ap.add_argument(
        "--only", choices=["tinyauth", "jellyfin", "seerr", "oidc", "copyparty", "report"], action="append"
    )
    a = ap.parse_args()
    FORCE = a.force
    APPLY = (a.apply or a.force) and not a.dry_run
    UNREDACTED = a.unredacted

    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    lock_fd = LOCK_FILE.open("w")
    fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)

    gql_users, gql_groups, state_hash = read_lldap_sqlite()
    if not FORCE and not a.only and HASH_FILE.exists():
        cached_hash = HASH_FILE.read_text().strip()
        if cached_hash == state_hash:
            log(f"SKIP   lldap state + .env unchanged (sha256={state_hash[:12]}...); exiting in <50ms.")
            return

    if FORCE:
        prune_lldap_jwt_storage()

    data, env = load_users(), load_env(ENV_FILE)
    dirty = pull_from_lldap(data, gql_users, gql_groups)

    steps = a.only or ["tinyauth", "jellyfin", "seerr", "oidc", "copyparty", "report"]
    if "tinyauth" in steps:
        sync_tinyauth(data, env)
    if "jellyfin" in steps:
        dirty |= sync_jellyfin(data, env)
    if "seerr" in steps:
        dirty |= sync_seerr(data)
    if "oidc" in steps:
        sync_oidc_apps(data, env)
    if "copyparty" in steps:
        sync_copyparty(data)
    if "report" in steps:
        report(data, env)
    if dirty and act(f"export lldap state + discovered IDs to {USERS_JSON}"):
        USERS_JSON.write_text(json.dumps(data, indent=2) + "\n")

    if APPLY and not a.only:
        _, _, final_hash = read_lldap_sqlite()
        HASH_FILE.write_text(final_hash + "\n")
    elif not APPLY:
        log("\nDry-run only. Re-run with --apply (or --force) to execute.")


if __name__ == "__main__":
    main()
