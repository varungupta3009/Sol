#!/usr/bin/env python3
"""Sol unified identity sync: lldap <-> users.json -> Tinyauth, OIDC apps, Jellyfin, Seerr, Copyparty.

Can be driven either from:
  - lldap Web UI (https://ldap.vrg.rocks) via `--from-lldap` (triggered automatically by launchd WatchPaths on data/lldap/users.db)
  - CLI (`./scripts/allowlist_user.sh` or `python3 scripts/identity_sync.py --apply`)

Targets reconciled:
  1. lldap         users, mail + mailalias (editable), groups jellyfin_users / jellyfin_admin
  2. Tinyauth      data/tinyauth/whitelist.txt, .env TINYAUTH_OAUTH_WHITELIST, oidc_consents
  3. Jellyfin      users exist, AuthenticationProviderId = LDAP-Auth,
                   LDAP-Auth.xml + SSO-Auth.xml (DefaultProvider + DefaultUsernameClaim + CanonicalLinks),
                   branding.xml ("Sign in with Google SSO" button)
  4. Seerr         every Jellyfin user imported, Seerr email = primary email
  5. Paperless-ngx auth_user + socialaccount_socialaccount pre-linked for 0-click first login
  6. AirTrail      "user" table pre-seeded with short username + oauth_id for 0-click first login
  7. Homebox       users + user_groups pre-linked to household group with oidc_issuer = https://auth.vrg.rocks
  8. Copyparty     idp-hm-usr Remote-Email -> uid mappings in config/copyparty/copyparty.conf
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import shutil
import sqlite3
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

os.environ["PATH"] = "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:" + os.environ.get("PATH", "")

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
COPYPARTY_CONF = BASE / "config/copyparty/copyparty.conf"
LOCK_FILE = LLDAP_DIR / ".identity_sync.lock"
HASH_FILE = LLDAP_DIR / ".identity_sync.sha256"

LDAP_PROVIDER = "Jellyfin.Plugin.LDAP_Auth.LdapAuthenticationProviderPlugin"
DEFAULT_PROVIDER = "Jellyfin.Server.Implementations.Users.DefaultAuthenticationProvider"
CONSENT_SCOPE = "openid profile email groups"
JF_SSO_DISCLAIMER = (
    '<form action="/sso/OID/start/google-sso">'
    '<button class="raised button-submit block emby-button" type="submit">'
    'Sign in with Google SSO'
    '</button></form>'
)
UUID_RE = re.compile(r"^[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}$", re.I)

APPLY = False


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


# --------------------------------------------------------------------------- model & lldap pull

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


def lldap_graphql(query: str, variables: dict | None = None) -> dict:
    payload = json.dumps({"query": query, "variables": variables or {}})
    script = (
        "TOKEN=$(curl -s -X POST localhost:17170/auth/simple/login -H 'Content-Type: application/json' "
        "-d \"{\\\"username\\\":\\\"admin\\\",\\\"password\\\":\\\"$(cat /data/secrets/admin.pw)\\\"}\" | jq -r .token); "
        "curl -s localhost:17170/api/graphql -H \"Authorization: Bearer $TOKEN\" -H 'Content-Type: application/json' "
        "--data-binary @-"
    )
    out = docker("exec", "-i", "lldap", "sh", "-c", script, input_text=payload)
    return json.loads(out)


def pull_from_lldap(data: dict) -> bool:
    """Read live users from lldap GraphQL and reconcile into data['users']."""
    log("\n== Pull from lldap ==")
    res = lldap_graphql(
        "{users{id email displayName firstName lastName attributes{name value} groups{id displayName}} "
        "groups{id displayName}}"
    )
    gql_users = res["data"]["users"]
    gql_groups = {g["displayName"]: g["id"] for g in res["data"]["groups"]}
    jf_users_gid = gql_groups.get("jellyfin_users")

    by_uid = {u["uid"]: u for u in data["users"]}
    new_users_list = []
    dirty = False

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

        existing = by_uid.get(uid)
        if existing:
            if existing["emails"] != emails or existing["display"] != display or existing["role"] != role:
                log(f"INFO   lldap updated user {uid}: emails={emails} display={display} role={role}")
                existing["emails"] = emails
                existing["display"] = display
                existing["role"] = role
                dirty = True
            new_users_list.append(existing)
        else:
            log(f"INFO   lldap added new user {uid}: emails={emails} display={display} role={role}")
            entry = {
                "uid": uid,
                "display": display,
                "emails": emails,
                "role": role,
                "jellyfin_id": None,
                "seerr_id": None,
            }
            if gu.get("firstName"):
                entry["first_name"] = gu["firstName"]
            if gu.get("lastName"):
                entry["last_name"] = gu["lastName"]
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
    have = [l.strip().lower() for l in WHITELIST.read_text().splitlines() if l.strip() and not l.startswith("#")] if WHITELIST.exists() else []
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

    client_ids = sorted({v for k, v in env.items() if re.fullmatch(r"TINYAUTH_OIDC_[A-Z0-9_]+_CLIENT_ID", k)})
    con = sqlite3.connect(f"file:{TINYAUTH_DB}?immutable=1", uri=True)
    rows = set(con.execute("select username, client_id from oidc_consents").fetchall())
    con.close()
    missing = [(tinyauth_username(e), c) for e in want for c in client_ids if (tinyauth_username(e), c) not in rows]
    log(f"INFO   {len(client_ids)} OIDC clients, {len(missing)} consent rows missing")
    if (missing or changed) and act("stop tinyauth, seed consents, start tinyauth"):
        docker("stop", "tinyauth", check=False)
        con = sqlite3.connect(str(TINYAUTH_DB))
        now = int(time.time())
        con.executemany(
            "INSERT INTO oidc_consents (username, client_id, scope, created_at) VALUES (?,?,?,?) "
            "ON CONFLICT(username, client_id) DO UPDATE SET scope = excluded.scope",
            [(u, c, CONSENT_SCOPE, now) for (u, c) in missing],
        )
        con.commit()
        con.close()
        subprocess.run(["docker", "compose", "up", "-d", "tinyauth"], cwd=BASE, check=True)


# --------------------------------------------------------------------------- 2. lldap

def lldap_secret(name: str, create: bool) -> tuple:
    p = LLDAP_SECRETS / f"{name}.pw"
    if p.exists():
        return p, False
    if create and APPLY:
        LLDAP_SECRETS.mkdir(parents=True, exist_ok=True)
        LLDAP_SECRETS.chmod(0o700)
        p.write_text(secrets.token_urlsafe(18) + "\n")
        p.chmod(0o600)
    return p, True


def lldap_existing_users() -> set:
    try:
        res = lldap_graphql("{users{id}}")
        return {u["id"] for u in res["data"]["users"]}
    except Exception as e:
        log(f"WARN   cannot list lldap users ({e}); treating all as new")
        return set()


def sync_lldap(data: dict) -> None:
    log("\n== lldap ==")
    existing = lldap_existing_users()
    user_rows, new_pw = [], []
    for u in data["users"]:
        groups = ["jellyfin_users"] + (["jellyfin_admin"] if u["role"] == "admin" else [])
        row = {
            "id": u["uid"],
            "email": u["emails"][0],
            "displayName": u["display"],
            "firstName": u.get("first_name"),
            "lastName": u.get("last_name"),
            "groups": groups,
            "mailalias": u["emails"][1:],
        }
        if u["uid"] not in existing:
            p, _ = lldap_secret(u["uid"], create=True)
            row["password_file"] = f"/data/secrets/{p.name}"
            new_pw.append(u["uid"])
        user_rows.append({k: v for k, v in row.items() if v is not None})
    bp, _ = lldap_secret("svc_bind", create=True)
    svc = {"id": "svc_bind", "email": "svc_bind@vrg.rocks", "displayName": "Service Bind",
           "groups": ["lldap_strict_readonly"]}
    if "svc_bind" not in existing:
        svc["password_file"] = f"/data/secrets/{bp.name}"
    user_rows.append(svc)

    files = {
        LLDAP_BOOT / "user-schemas/schema.json": json.dumps(
            [{"name": "mailalias", "attributeType": "STRING", "isEditable": True, "isList": True, "isVisible": True}]),
        LLDAP_BOOT / "group-configs/groups.json": "\n".join(json.dumps({"name": g}) for g in ("jellyfin_users", "jellyfin_admin")),
        LLDAP_BOOT / "user-configs/users.json": "\n".join(json.dumps(r) for r in user_rows),
    }
    changed = False
    for path, content in files.items():
        if not path.exists() or path.read_text().strip() != content.strip():
            changed = True
            if act(f"write {path.relative_to(BASE)}"):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content + "\n")
    if new_pw:
        log(f"INFO   new lldap users get a password in data/lldap/secrets/<uid>.pw: {new_pw}")
    if (changed or new_pw) and act("docker exec lldap /app/bootstrap.sh (idempotent; DO_CLEANUP=false)"):
        out = docker("exec", "-e", "LLDAP_ADMIN_PASSWORD_FILE=/data/secrets/admin.pw",
                     "-e", "USER_CONFIGS_DIR=/data/bootstrap/user-configs",
                     "-e", "GROUP_CONFIGS_DIR=/data/bootstrap/group-configs",
                     "-e", "USER_SCHEMAS_DIR=/data/bootstrap/user-schemas",
                     "lldap", "/app/bootstrap.sh")
        bad = [l for l in out.splitlines() if re.search(r"error|not exists|failed", l, re.I)]
        log("\n".join("  " + l for l in bad) or "  bootstrap: no errors")


# --------------------------------------------------------------------------- 3. Jellyfin

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
    cmd = ["exec", "-i", "jellyfin", "curl", "-s", "-X", method, f"http://localhost:8096{path}",
           "-H", f'Authorization: MediaBrowser Token="{token}"', "-H", "Content-Type: application/json"]
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
        pol = ju["Policy"]
        if pol.get("AuthenticationProviderId") != LDAP_PROVIDER and act(f"{u['display']}: AuthenticationProviderId -> LDAP-Auth"):
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
    if ldap_edits:
        edits.append("LDAP-Auth.xml -> lldap:3890 (uid, mail, mailalias -> cn)")
    if (pc.findtext("DefaultProvider") or "").strip() != LDAP_PROVIDER:
        edits.append("SSO-Auth DefaultProvider -> LDAP-Auth")
    if (pc.findtext("DefaultUsernameClaim") or "").strip() != "email":
        edits.append("SSO-Auth DefaultUsernameClaim -> email")
    if have_links != want_links:
        edits.append(f"SSO-Auth CanonicalLinks -> {len(want_links)} email links")
    if branding_tree and branding_disc != JF_SSO_DISCLAIMER:
        edits.append("branding.xml LoginDisclaimer -> 'Sign in with Google SSO' button")

    if edits and act("stop jellyfin, edit XMLs: " + "; ".join(edits)):
        docker("stop", "jellyfin")
        ts = int(time.time())
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
                out = docker("exec", "jellyfin", "curl", "-s", "http://localhost:8096/Users",
                             "-H", f'Authorization: MediaBrowser Token="{token}"', check=False)
                if out.strip().startswith("["):
                    break
            except Exception:
                pass
    return dirty_json


# --------------------------------------------------------------------------- 4. Seerr

def seerr(api_key: str, method: str, path: str, body=None):
    cmd = ["exec", "seerr", "wget", "-qO-", f"--header=X-Api-Key: {api_key}",
           "--header=Content-Type: application/json"]
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
        if (s.get("email") or "").lower() != u["emails"][0] and act(f"Seerr user {s['id']}: email -> {u['emails'][0]}"):
            main = seerr(api_key, "GET", f"/user/{s['id']}/settings/main")
            main["email"] = u["emails"][0]
            seerr(api_key, "POST", f"/user/{s['id']}/settings/main", main)
    return dirty_json


# --------------------------------------------------------------------------- 5. OIDC Apps (Paperless, AirTrail, Homebox)

def sync_oidc_apps(data: dict, env: dict) -> None:
    log("\n== OIDC Apps (Paperless-ngx, AirTrail, Homebox) ==")
    # 5a. Paperless-ngx (auth_user + socialaccount_socialaccount)
    pl_cid = env.get("TINYAUTH_OIDC_PAPERLESS_CLIENT_ID")
    if pl_cid:
        raw_users = docker("exec", "paperless-db", "psql", "-U", "paperless", "-d", "paperless", "-t", "-A", "-c",
                           "SELECT id, username, lower(email) FROM auth_user;")
        pl_by_email, pl_by_name = {}, {}
        for line in raw_users.strip().splitlines():
            if "|" in line:
                uid_s, uname, mail = line.split("|", 2)
                pl_by_name[uname.upper()] = int(uid_s)
                if mail:
                    pl_by_email[mail] = int(uid_s)
        raw_sa = docker("exec", "paperless-db", "psql", "-U", "paperless", "-d", "paperless", "-t", "-A", "-c",
                        "SELECT uid FROM socialaccount_socialaccount WHERE provider='tinyauth';")
        have_sa = set(raw_sa.strip().splitlines())
        for u in data["users"]:
            email = u["emails"][0]
            pl_id = pl_by_email.get(email) or pl_by_name.get(u["display"].upper())
            if not pl_id and act(f"Paperless-ngx: create user {u['display']} ({email})"):
                is_sup = "true" if u["role"] == "admin" else "false"
                sql = (
                    f"INSERT INTO auth_user (password, is_superuser, username, first_name, last_name, email, is_staff, is_active, date_joined) "
                    f"VALUES ('!', {is_sup}, '{u['display']}', '', '', '{email}', {is_sup}, true, NOW()) RETURNING id;"
                )
                out = docker("exec", "paperless-db", "psql", "-U", "paperless", "-d", "paperless", "-t", "-A", "-c", sql)
                pl_id = int(out.strip().splitlines()[0])
            if pl_id:
                for e in u["emails"]:
                    sub = oidc_sub(tinyauth_username(e), pl_cid)
                    if sub not in have_sa and act(f"Paperless-ngx: link socialaccount {e} -> user_id={pl_id}"):
                        extra = json.dumps({"email": e, "name": u["display"]})
                        sql = (
                            f"INSERT INTO socialaccount_socialaccount (provider, uid, last_login, date_joined, extra_data, user_id) "
                            f"VALUES ('tinyauth', '{sub}', NOW(), NOW(), '{extra}'::jsonb, {pl_id}) "
                            f"ON CONFLICT (provider, uid) DO NOTHING;"
                        )
                        docker("exec", "paperless-db", "psql", "-U", "paperless", "-d", "paperless", "-c", sql)

    # 5b. AirTrail ("user" table in airtrail DB)
    at_cid = env.get("TINYAUTH_OIDC_AIRTRAIL_CLIENT_ID")
    if at_cid:
        raw_at = docker("exec", "paperless-db", "psql", "-U", "paperless", "-d", "airtrail", "-t", "-A", "-c",
                        'SELECT username, COALESCE(oauth_id, \'\') FROM "user";')
        at_have = set()
        at_oauth_ids = set()
        for line in raw_at.strip().splitlines():
            if "|" in line:
                uname, oid = line.split("|", 1)
                at_have.add(uname.upper())
                if oid:
                    at_oauth_ids.add(oid)
        for u in data["users"]:
            sub = oidc_sub(tinyauth_username(u["emails"][0]), at_cid)
            if sub not in at_oauth_ids and u["display"].upper() not in at_have and act(f"AirTrail: seed user {u['display']} (oauth_id={sub[:8]}...)"):
                uid_row = f"{u['uid']}-{secrets.token_hex(4)}"[:15]
                is_owner = "true" if u["role"] == "admin" else "false"
                role_val = "NULL" if u["role"] == "admin" else "'role-user'"
                sql = (
                    f'INSERT INTO "user" (id, username, password, display_name, oauth_id, is_owner, role_id) '
                    f"VALUES ('{uid_row}', '{u['display']}', NULL, '{u['display']}', '{sub}', {is_owner}, {role_val}) "
                    f"ON CONFLICT (oauth_id) DO NOTHING;"
                )
                docker("exec", "paperless-db", "psql", "-U", "paperless", "-d", "airtrail", "-c", sql)

    # 5c. Homebox (users + user_groups in data/homebox/homebox.db)
    hb_cid = env.get("TINYAUTH_OIDC_HOMEBOX_CLIENT_ID")
    if hb_cid and HOMEBOX_DB.exists():
        con = sqlite3.connect(f"file:{HOMEBOX_DB}?immutable=1", uri=True)
        grp_row = con.execute("SELECT id FROM groups LIMIT 1").fetchone()
        hb_group = grp_row[0] if grp_row else None
        hb_users = {r[0].lower(): (r[1], r[2], r[3]) for r in con.execute("SELECT email, id, oidc_issuer, oidc_subject FROM users")}
        con.close()
        hb_actions = []
        for u in data["users"]:
            email = u["emails"][0]
            sub = oidc_sub(tinyauth_username(email), hb_cid)
            if email not in hb_users:
                hb_actions.append(("insert", u, email, sub))
            elif hb_users[email][1] != "https://auth.vrg.rocks" or hb_users[email][2] != sub:
                hb_actions.append(("update", u, email, sub))
        if hb_actions and hb_group and act(f"Homebox: stop container and sync {len(hb_actions)} user(s) into group {hb_group[:8]}..."):
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
                        "UPDATE users SET oidc_issuer='https://auth.vrg.rocks', oidc_subject=?, default_group_id=? WHERE lower(email)=?",
                        (sub, hb_group, email),
                    )
            con.commit()
            con.close()
            docker("start", "homebox", check=False)


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
        log(f"{u['uid']:8} {u['display']:8} role={u['role']:5} jellyfin={u.get('jellyfin_id')} seerr={u.get('seerr_id')}")
        for e in u["emails"]:
            subs = ", ".join(f"{k.split('_')[2].lower()}={oidc_sub(tinyauth_username(e), v)[:8]}" for k, v in sorted(client_ids.items()))
            log(f"           {e:30} tinyauth={tinyauth_username(e)}  sub: {subs}")


def main() -> None:
    global APPLY
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="execute the plan (default is dry-run)")
    ap.add_argument("--from-lldap", action="store_true", help="pull user list from live lldap before syncing")
    ap.add_argument("--only", choices=["tinyauth", "lldap", "jellyfin", "seerr", "oidc", "copyparty", "report"], action="append")
    a = ap.parse_args()
    APPLY = a.apply

    data, env = load_users(), load_env(ENV_FILE)
    dirty = False
    if a.from_lldap:
        dirty |= pull_from_lldap(data)

    steps = a.only or ["tinyauth", "lldap", "jellyfin", "seerr", "oidc", "copyparty", "report"]
    if "lldap" in steps and not a.from_lldap:
        sync_lldap(data)
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
    if dirty and act(f"write discovered ids/users back to {USERS_JSON}"):
        USERS_JSON.write_text(json.dumps(data, indent=2) + "\n")
    if not APPLY:
        log("\nDry-run only. Re-run with --apply to execute.")


if __name__ == "__main__":
    main()
