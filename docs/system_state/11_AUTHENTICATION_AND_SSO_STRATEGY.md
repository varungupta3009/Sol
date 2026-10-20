# 11. Sol Authentication, Zero-Click SSO, OIDC & Unified LDAP Strategy (`Tinyauth v5.2.0` + `LLDAP`)

> **Status:** Active Production Standard (Verified Live 2026-10-20)  
> **Primary Identity & OIDC Provider:** `tinyauth` (`ghcr.io/tinyauthapp/tinyauth:v5` v5.2.0 at `https://auth.vrg.rocks`, `~29 MiB` RAM)  
> **Unified LDAP Directory (Jellyfin, Seerr & User Source of Truth):** `lldap` (`ghcr.io/lldap/lldap:stable` at `ldap://lldap:3890` and `https://ldap.vrg.rocks`, `~12 MiB` RAM)  
> **Authoritative Identity Sync Engine:** [`scripts/identity_sync.py`](../../scripts/identity_sync.py) + [`scripts/launchd/com.vrg.sol.identity-sync.plist`](../../scripts/launchd/com.vrg.sol.identity-sync.plist) + [`scripts/allowlist_user.sh`](../../scripts/allowlist_user.sh)  
> **Exported Identity Snapshot:** [`config/auth/users.json.example`](../../config/auth/users.json.example) (live `config/auth/users.json` gitignored, backed up in Restic)  
> **Retired Legacy Provider (Documented in Section 4):** `authentik-server` + `authentik-worker` + `authentik-postgresql` (purged from `compose/core.yml`, `~502 MiB` RAM saved)  

---

## 1. Core Architectural Invariants

Sol's authentication architecture enforces five invariants across all `*.vrg.rocks` endpoints:

1. **One Email Connects All Interfaces (`lldap` -> `users.json` One-Way Identity Spine):**
   - **`lldap` (`https://ldap.vrg.rocks`, `data/lldap/users.db`) is the single authoritative user database.** Users, display names, primary emails, and `mailalias` values are created, edited, or removed exclusively in `lldap`.
   - **Zero-Write Immutable SQLite Polling & `<50 ms` SHA-256 Fast-Path:** The macOS `launchd` `WatchPaths` agent (`/Users/vrg/Library/LaunchAgents/com.vrg.sol.identity-sync.plist`, tracked in `scripts/launchd/com.vrg.sol.identity-sync.plist`) watches `data/lldap/users.db` and `data/lldap/users.db-wal`. To avoid a self-triggering write loop (where logging into LLDAP via HTTP API would write a new `jwt_storage` row to `users.db-wal` and re-trigger `WatchPaths` every 10 seconds), `scripts/identity_sync.py` reads `file:/Users/vrg/Documents/Sol/data/lldap/users.db?immutable=1` directly via read-only SQLite, decodes Rust `bincode` `user_attributes`, and computes a SHA-256 digest over LLDAP user/group/attribute state plus `.env` `st_mtime_ns` (`/tmp/sol_identity_sync.sha256`). When no user or `.env` state has changed, `identity_sync.py` exits `0` in **~45 ms** before loading heavy standard-library modules, performing zero database writes.
   - **macOS TCC & Keychain Hardening:** `com.vrg.sol.identity-sync.plist` invokes `/opt/homebrew/bin/python3` via an inline `subprocess.call` wrapper without setting `WorkingDirectory` inside `~/Documents` (avoiding `kTCCServiceSystemPolicyDocumentsFolder` `Exit 126` blocks), and `identity_sync.py` prepends a no-op `docker-credential-osxkeychain` shim (`/tmp/sol_no_keychain`) to `PATH` plus an exclusive `fcntl.flock` lock on `/tmp/sol_identity_sync.lock`.
   - **`config/auth/users.json` One-Way Export:** Whenever LLDAP state changes (or `--force` is passed), `identity_sync.py` exports the canonical user list to `config/auth/users.json` (preserving discovered `jellyfin_id` and `seerr_id` keys) and synchronizes every downstream service:
     - **LLDAP Group & Token Hygiene:** Ensures every user belongs to `jellyfin_users` (`group_id=3`), `vrg` belongs to `jellyfin_admins` (`group_id=4`), and prunes stale headless `admin` sessions from `jwt_storage` and `jwt_refresh_storage`.
     - **Tinyauth Whitelist & Admin-Scoped OIDC Consents:** Writes `data/tinyauth/whitelist.txt`, updates `TINYAUTH_OAUTH_WHITELIST` and `TINYAUTH_ADMIN_EMAILS` in `.env`, and pre-seeds `oidc_consents` in `data/tinyauth/tinyauth.db`. Consents for infrastructure clients **`arcane` and `coder` are scoped strictly to `role == "admin"` (`vrg`)**, while shared OIDC clients (`paperless`, `homebox`, `airtrail`, `readeck`, `jellyfin`) are pre-seeded for all allowlisted users (`29` total consent rows).
     - **Downstream OIDC Databases (`Paperless-ngx`, `AirTrail`, `Homebox`, `Readeck`):** Pre-provisions user accounts and links deterministic Tinyauth OIDC `sub` UUIDs so first-time logins succeed in 0 clicks.
     - **Jellyfin (`watch.vrg.rocks`) & Seerr (`request.vrg.rocks`):** Updates `LDAP-Auth.xml`, `SSO-Auth.xml` `<CanonicalLinks>`, `branding.xml`, and `config/seerr/db/db.sqlite3` (`userType = 3`, linked `jellyfinUserId`).
     - **Copyparty (`files.vrg.rocks`):** Updates `idp-hm-usr` header mappings in `config/copyparty/copyparty.conf`.
2. **Zero-Click Google SSO:**
   - When signed into an allowlisted Google account in the browser, navigating to any `*.vrg.rocks` service authenticates and opens the application with **zero button clicks** (no provider selection screen, no OIDC consent screen, and no secondary app login prompt).
   - Enforced at Tinyauth via `TINYAUTH_OAUTH_AUTOREDIRECT=google`, pre-seeded `oidc_consents` rows in `data/tinyauth/tinyauth.db`, and per-container auto-redirect/external-auth flags.
3. **Sole Hardcoded Admin (`VRG`) Across All 17 Admin Consoles:**
   - `VRG` (`${TINYAUTH_ADMIN_EMAILS}`) is the sole administrator across all infrastructure and application databases (`VRG`, superuser/owner, and member of `jellyfin_admins` in `lldap`).
   - All **17** admin-only forward-auth subdomains (`code`, `backrest`, `qui`, `radarr`, `sonarr`, `lidarr`, `prowlarr`, `bazarr`, `cs`, `byparr`, `pb`, `router`, `ldap`, `ignis`, `mind`, `scan`, `aysynbm`) are locked down at the Tinyauth edge in `compose/core.yml` via `TINYAUTH_APPS_<APP>_OAUTH_WHITELIST: ${TINYAUTH_ADMIN_EMAILS:?}` and `TINYAUTH_APPS_<APP>_USERS: nobody`.
4. **Strict Email Allowlist & Approval Gate:**
   - No user can authenticate through `auth.vrg.rocks` unless their email address is present in `lldap` (exported to `config/auth/users.json` and `data/tinyauth/whitelist.txt`).
   - Unapproved login attempts are rejected at `https://auth.vrg.rocks/unauthorized` and logged via `TINYAUTH_LOG_STREAMS_AUDIT_ENABLED=true`.
5. **Provider-Agnostic Caddy Forward-Auth & Native OIDC First:**
   - `Caddyfile` defines a single `(forward_auth)` snippet imported across protected routes, while `login.vrg.rocks` and `tinyauth.vrg.rocks` permanently redirect (`301`) to `https://auth.vrg.rocks{uri}`.
   - Containers that support native OIDC (`arcane`, `docs`/`paperless`, `inv`/`homebox`, `fly`/`airtrail`, `coder`, `links`/`readeck`, `watch`/`jellyfin`) use their native OIDC flow directly without redundant edge `forward_auth`.

---

## 2. Four-Tier Authentication Matrix Across All Services

### Tier A: Native OpenID Connect (OIDC) Clients (`https://auth.vrg.rocks/.well-known/openid-configuration`)

Tinyauth v5.2.0 runs an OpenID Certified OIDC Provider backed by RS256 signing keys at `/data/tinyauth/oidc/key.pem`. It computes a deterministic pairwise `sub` claim for each `(username, client_id)` pair using UUIDv5 (`uuid.uuid5(uuid.NAMESPACE_URL, f"{tinyauth_username}:{client_id}")`), where `tinyauth_username` is the user's email with `@` replaced by `_`. `TINYAUTH_LDAP_*` is intentionally omitted on `tinyauth` so Google OAuth remains the sole Tinyauth login backend and `sub` UUIDs never fragment.

| Service | Domain | OIDC Env / Config | Zero-Click Mechanism | Admin (`VRG`) & Role Enforcement |
| :--- | :--- | :--- | :--- | :--- |
| **Paperless-ngx** | `docs.vrg.rocks`, `paperless.vrg.rocks` | `PAPERLESS_SOCIALACCOUNT_PROVIDERS` (`provider_id: "tinyauth"`) | `PAPERLESS_REDIRECT_LOGIN_TO_SSO: "true"` + `PAPERLESS_DISABLE_REGULAR_LOGIN: "true"` | `auth_user.id=3` (`VRG`, `is_superuser=t`) linked in `socialaccount_socialaccount`. Member accounts pre-seeded with `is_superuser=f`. |
| **Arcane** | `arcane.vrg.rocks` | `OIDC_ENABLED: "true"`, `OIDC_ISSUER_URL: https://auth.vrg.rocks` | `OIDC_AUTO_REDIRECT_TO_PROVIDER: "true"` + `authLocalEnabled=false` in `arcane.db` | Admin-only `oidc_consents` in `tinyauth.db` (`vrg` only). `users.username='VRG'` (`roles=["admin"]`). |
| **Homebox** | `inv.vrg.rocks` | `HBOX_OIDC_ENABLED: "true"`, `HBOX_OIDC_ISSUER_URL: https://auth.vrg.rocks` | `HBOX_OIDC_AUTO_REDIRECT: "true"` + `HBOX_OPTIONS_ALLOW_LOCAL_LOGIN: "true"` + `HBOX_OPTIONS_TRUST_PROXY: "true"` | `VRG` (`is_superuser=1`). Local login stays enabled at `/api/v1/users/login` so `scan.vrg.rocks` PWA can authenticate via API while browser navigation auto-redirects to OIDC. |
| **AirTrail** | `fly.vrg.rocks` | `OAUTH_ENABLED: "true"`, `OAUTH_ISSUER_URL: https://auth.vrg.rocks` | `OAUTH_AUTO_LOGIN: "true"` + `OAUTH_HIDE_PASSWORD_FORM: "true"` | Single-owner invariant enforced by `identity_sync.py`: only `vrg` has `is_owner=true, role_id=NULL`. Additional admins receive `is_owner=false, role_id='role-administrator'`, and regular users receive `role_id='role-user'`. |
| **Coder** | `coder.vrg.rocks` | `CODER_OIDC_ISSUER_URL: https://auth.vrg.rocks`, `CODER_OIDC_ALLOW_SIGNUPS: "false"`, `CODER_DISABLE_PASSWORD_AUTH: "true"` | Caddy `redir /login /api/v2/users/oidc/callback 302` | Signups disabled (`CODER_OIDC_ALLOW_SIGNUPS: "false"`) and `oidc_consents` restricted to `vrg` only (`rbac_roles={owner}`). |
| **Readeck** | `links.vrg.rocks` | `[[auth.oidc.providers]]` (`url = "https://auth.vrg.rocks"`, `client_id = "readeck"`, `roles_claim = "groups"`, `admin_role = "jellyfin_admins"`) in `data/readeck/config.toml` | Native OIDC at `https://links.vrg.rocks/login` (edge `forward_auth` omitted so browser extension `/api/*` tokens work) | `VRG` (`"group"='admin'`, `ext_id=1780b004-...`) and members (`"group"='user'`, deterministic `uuid5(NAMESPACE_URL, "https://auth.vrg.rocks#<sub_uuid>")` `ext_id`) pre-seeded in `data/readeck/data/db.sqlite3`. Protected by `preserve_lldap_user_identity` `AFTER UPDATE ON "user"` SQLite trigger so OIDC logins cannot overwrite LLDAP usernames or demote `VRG`. |
| **Jellyfin** | `watch.vrg.rocks`, `jellyfin.vrg.rocks` | `SSO-Auth.xml` (`google-sso` -> `https://auth.vrg.rocks`, `DefaultUsernameClaim=email`, `SchemeOverride=https`, `CanonicalLinks`) + `LDAP-Auth.xml` (`lldap:3890`) | Browser: 1-click Google SSO (`/sso/OID/start/google-sso`) or email/username + LDAP password. TV/Mobile: LDAP password or Quick Connect | `VRG` (`IsAdministrator=1`, `jellyfin_admins`), standard users (`IsAdministrator=0`, `jellyfin_users`). |

### Tier B: Unified LDAP (`lldap`) for Jellyfin & Seerr

- **`lldap` (`ghcr.io/lldap/lldap:stable`, `~12 MiB` RAM):**
  - Listens on `::` port `3890` (LDAP) and port `17170` (Web UI / GraphQL API at `https://ldap.vrg.rocks`, gated by `import forward_auth` + `TINYAUTH_APPS_LDAP_OAUTH_WHITELIST` for `VRG` only).
  - Base DN: `dc=vrg,dc=rocks`. Users live under `ou=people,dc=vrg,dc=rocks` with custom attribute `mailalias` (`STRING`, `isList: true`, `isVisible: true`) and groups `jellyfin_users` (`id=3`) and `jellyfin_admins` (`id=4`).
- **Jellyfin (`watch.vrg.rocks`):**
  - `LDAP-Auth` (`v22.0.0.0`) binds to `lldap:3890` and searches `( &(objectClass=person)(|(uid={0})(cn={0})(mail={0})(mailalias={0})) )` with `<LdapUsernameAttribute>cn</LdapUsernameAttribute>` and `<LdapUidAttribute>entryUUID</LdapUidAttribute>`.
  - `SSO-Auth` (`v4.0.0.3`) maps every user's primary email and `mailalias` via `<CanonicalLinks>` to their existing Jellyfin GUID so OIDC logins map to the same account without duplicating users.
- **Seerr (`request.vrg.rocks`):**
  - Authenticates against Jellyfin (`POST /api/v1/auth/jellyfin` or Quick Connect `/api/v1/auth/jellyfin/quickconnect/initiate`) and maps to `user.jellyfinUserId` in `config/seerr/db/db.sqlite3`.

### Tier C: Trusted-Header & External Auth Behind Tinyauth Forward-Auth

| Service | Domain | Native Integration Setting | Edge ACL Policy |
| :--- | :--- | :--- | :--- |
| **Copyparty** | `files.vrg.rocks`, `copyparty.vrg.rocks` | `rproxy: -1`, `xf-proto-fb: https`, `idp-h-usr: Remote-Email`, and `idp-hm-usr` mappings in `config/copyparty/copyparty.conf` (auto-managed by `identity_sync.py`, with `noidx` excluding `.Spotlight-V100`, `.fseventsd`, `.Trashes`, `.DS_Store`, `._*`, and `backups`) | Allowlisted users (`vrg` gets `rwmda` on `/` and `/priv`, members get `r` on `/`). |
| **QUI** | `qui.vrg.rocks` | `QUI__AUTH_DISABLED: "true"` + `QUI__I_ACKNOWLEDGE_THIS_IS_A_BAD_IDEA: "true"` | Admin-only (`TINYAUTH_APPS_QUI_OAUTH_WHITELIST`). |
| **code-server** | `code.vrg.rocks` | `AUTH: none` in `compose/coding.yml` | Admin-only (`TINYAUTH_APPS_CODE_OAUTH_WHITELIST`). |
| **Backrest** | `backrest.vrg.rocks` | `"auth": { "disabled": true }` in `config/backrest/config.json` | Admin-only (`TINYAUTH_APPS_BACKREST_OAUTH_WHITELIST`). |
| **Radarr / Sonarr / Lidarr / Prowlarr** | `{radarr,sonarr,lidarr,prowlarr}.vrg.rocks` | `<AuthenticationMethod>External</AuthenticationMethod>` in `config/*/config.xml` (API keys remain enforced for `/api/*`) | Admin-only (`TINYAUTH_APPS_<ARR>_OAUTH_WHITELIST`). |
| **Bazarr** | `bazarr.vrg.rocks` | `auth.type: null` in `config/bazarr/config/config.yaml` (API key remains enforced) | Admin-only (`TINYAUTH_APPS_BAZARR_OAUTH_WHITELIST`). |

### Tier D: Stateless Apps, Shared Apps & Selective Method/Path Gates

- **Admin-Locked Static & Vault Apps (`ignis`, `mind`, `scan`, `aysynbm`):** Protected by `import forward_auth` in `Caddyfile` AND locked to `VRG` in `compose/core.yml` via `TINYAUTH_APPS_{IGNIS,MIND,SCAN,AYSYNBM}_OAUTH_WHITELIST: ${TINYAUTH_ADMIN_EMAILS:?}`.
- **Shared Allowlisted Web & Static Apps (`dash`, `fam`, `tools`, `chef`, `pdf`, `speed`, `draw`, `mi`):** Protected by `import forward_auth` in `Caddyfile`. Open in 0 clicks for all allowlisted users in `whitelist.txt`.
- **Admin Infrastructure Endpoints (`router`, `byparr`, `pb`, `ldap`):** Protected by `import forward_auth` + `TINYAUTH_APPS_{ROUTER,BYPARR,PB,LDAP}_OAUTH_WHITELIST` restricting access strictly to `VRG`. `pb.vrg.rocks` redirects `/` (`302`) to `/_/`.
- **Selective Method/Path Gates & Mobile-Direct Exceptions:**
  - `send.vrg.rocks` (`enclosed`): Note creation (`/` and `/api/notes[/]`) is gated by `import forward_auth` (`max_size 60MB`), while recipient view routes (`/@*` and `/api/notes/<id>`) remain public so recipients can decrypt shared client-side E2EE notes without an account.
  - `ntfy.vrg.rocks` (`ntfy`): Unauthenticated external `POST`/`PUT` requests (`not header Authorization *`) are gated by `import forward_auth`, while mobile client subscriptions (`GET`/WebSocket) and token-authenticated publishes pass directly to `ntfy:80`.
  - `qb.vrg.rocks` (`qbittorrent`): Uses qBittorrent native auth so the Android mobile client (`qBitController`) connects directly without SSO redirects (`qui.vrg.rocks` provides the 0-click web UI).

---

## 3. User Allowlist, LDAP & Identity Sync Workflow

### Identity Schema ([`config/auth/users.json.example`](../../config/auth/users.json.example))

Live user records reside in `data/lldap/users.db` and export automatically to the gitignored `config/auth/users.json` (both backed up in encrypted Restic snapshots):

| UID (`lldap`) | Display Name (`cn` / Jellyfin) | Primary Email (`mail`) | Email Aliases (`mailalias`) | Role | Jellyfin GUID | Seerr ID |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `vrg` | `VRG` | `<admin-email>` | `<admin-alias-email>` | `admin` | `<admin-jellyfin-guid>` | `1` |
| `member1..N` | `<DisplayName>` | `<member-email>` | - | `user` | `<member-jellyfin-guid>` | `2..N` |

### Approving, Editing, or Revoking Users (`lldap` -> `users.json` One-Way Sync)

1. **Edit Users in LLDAP (`https://ldap.vrg.rocks`):** Create, edit, or delete users (`mail`, `mailalias`, `displayName`, and optional password) in the LLDAP web console.
2. **Automatic `<50 ms` WatchPaths Sync:** Within 15 seconds of any change to `data/lldap/users.db` or `users.db-wal`, `com.vrg.sol.identity-sync.plist` triggers `scripts/identity_sync.py --apply`. Because `identity_sync.py` reads `users.db?immutable=1` without logging into LLDAP's HTTP API, it never mutates `users.db-wal` during normal checks and exits in `~45 ms` when unchanged.
3. **Passwordless Users on Jellyfin & Seerr:** Users created in `lldap` without an LDAP password can still sign into `watch.vrg.rocks` via **"Sign in with Google SSO"** (mapped via `SSO-Auth.xml` `<CanonicalLinks>`) and sign into TV/mobile Jellyfin apps and `request.vrg.rocks` (`Seerr`) using **Quick Connect**.

```bash
# List the exported config/auth/users.json snapshot
./scripts/allowlist_user.sh list

# Manually dry-run or force a full reconciliation across all apps
./scripts/allowlist_user.sh sync
python3 ./scripts/identity_sync.py --apply --force
```

---

## 4. Legacy Authentik Architecture & Reconstruction Blueprint

Authentik (`2026.5.3`) was retired in October 2026 in favor of `tinyauth:v5` + `lldap`, saving `~502 MiB` of idle RAM and eliminating background worker CPU polling. Its container definitions (`authentik-postgresql`, `authentik-server`, `authentik-worker`), `224 MB` PostgreSQL cluster (`data/authentik`), and `13 MB` SQL dump (`data/backups/authentik_db.sql.gz`) were purged after recording the reconstruction specification below.

### 4.1 Retired Container Topology

- **`authentik-postgresql`**: `postgres:16-alpine`, database `${PG_DB:-authentik}`, user `${PG_USER:-authentik}`, password `${PG_PASS}`.
- **`authentik-server`**: `ghcr.io/goauthentik/server:2026.5.3` (`command: server`), bound to `127.0.0.1:9000:9000` and `127.0.0.1:9443:9443`, `AUTHENTIK_WEB__WORKERS: 2`, `AUTHENTIK_SECRET_KEY: ${AUTHENTIK_SECRET_KEY}`.
- **`authentik-worker`**: `ghcr.io/goauthentik/server:2026.5.3` (`command: worker`), `AUTHENTIK_WORKER__CONCURRENCY: 2`.

### 4.2 Upstream Google OAuth Source & Silent Redirect Flow

1. **OAuth Source (`authentik_sources_oauth_oauthsource`):** `Google` / `google` (`enabled = true`, `promoted = true`, `provider_type = google`, `pkce = S256`, `user_matching_mode = email_link`), Redirect URI `https://auth.vrg.rocks/source/oauth/callback/google/`.
2. **Identification Stage (`default-authentication-identification`):** `user_fields: {}` (empty array) with `Google` (`promoted = true`) as the sole source, causing `default-authentication-flow` to return an immediate `HTTP 302` redirect to `https://accounts.google.com/o/oauth2/v2/auth`.
3. **User Login Stage (`default-authentication-login`):** `session_duration: seconds=0`, `remember_device: days=30`.
4. **Authorization Flow:** Bound to `default-provider-authorization-implicit-consent` (0 stages, skipping per-app consent prompts).

### 4.3 Legacy Applications, Providers & Caddy Snippet

| Application (`slug`) | Provider Name (`id`) | Type & Mode | Key Parameters & Redirect URIs |
| :--- | :--- | :--- | :--- |
| **`Sol` (`sol`)** | `Caddy` (`id=3`) | `ProxyProvider` (`forward_domain`) | `external_host: https://auth.vrg.rocks`, `cookie_domain: vrg.rocks`, `access_token_validity: hours=24`, `refresh_token_validity: days=30`, `intercept_header_auth: true`. Bound to `authentik Embedded Outpost`. |
| **`Paperless-ngx` (`paperless-ngx`)** | `Provider for Paperless-ngx` (`id=7`) | `OAuth2Provider` (`confidential`) | `sub_mode: hashed_user_id`, `issuer_mode: per_provider`. Redirect URI: `https://docs.vrg.rocks/accounts/oidc/authentik/login/callback/`. |
| **`Arcane` (`arcane`)** | `Provider for Arcane` (`id=9`) | `OAuth2Provider` (`confidential`) | `sub_mode: hashed_user_id`, `issuer_mode: per_provider`. Redirect URI: `https://arcane.vrg.rocks/auth/oidc/callback`. |

```caddyfile
# Standby Authentik forward_auth body (preserved as a comment in Caddyfile):
# forward_auth authentik-server:9000 {
# 	uri /outpost.goauthentik.io/auth/caddy
# 	copy_headers X-Authentik-Username X-Authentik-Groups X-Authentik-Entitlements X-Authentik-Email X-Authentik-Name X-Authentik-Uid X-Authentik-Jwt X-Authentik-Meta-Jwks X-Authentik-Meta-Outpost X-Authentik-Meta-Provider X-Authentik-Meta-App X-Authentik-Meta-Version
# 	trusted_proxies private_ranges
# }
```
