# Sol Authentication, Zero-Click SSO, OIDC & Unified LDAP Strategy (`Tinyauth v5.2.0` + `lldap`)

**Status:** Active Production Standard (October 2026)
**Primary Identity & OIDC Provider:** `tinyauth` (`ghcr.io/tinyauthapp/tinyauth:v5` v5.2.0 at `https://auth.vrg.rocks`, ~29.4 MiB RAM)
**Unified LDAP Directory (Jellyfin & Seerr):** `lldap` (`lldap/lldap:stable` at `ldap://lldap:3890` and `https://ldap.vrg.rocks`, ~12 MiB RAM)
**Authoritative Identity Manifest & Sync Engine:** [`config/auth/users.json`](../../config/auth/users.json) + [`scripts/identity_sync.py`](../../scripts/identity_sync.py) + [`scripts/allowlist_user.sh`](../../scripts/allowlist_user.sh)
**Standby Legacy Provider:** `authentik-server` + `authentik-worker` + `authentik-postgresql` (`profiles: ["standby"]` in `compose/core.yml`, ~502 MiB RAM saved)

---

## 1. Core Architectural Requirements

Sol's authentication architecture enforces five strict invariants across all `*.vrg.rocks` endpoints:

1. **One Email Connects All Interfaces (`lldap` -> `users.json` One-Way Identity Spine):**
   - **`lldap` (`https://ldap.vrg.rocks`, `data/lldap/users.db`) is the single authoritative user database.** Users and emails are added, edited, or removed exclusively in `lldap`.
   - A macOS `launchd` `WatchPaths` agent (`/Users/vrg/Library/LaunchAgents/com.vrg.sol.identity-sync.plist`) watches `data/lldap/users.db` and `data/lldap/users.db-wal` and automatically runs `python3 scripts/identity_sync.py --apply` within 15 seconds of any change in `lldap`.
   - [`config/auth/users.json`](../../config/auth/users.json) is a **one-way exported snapshot** generated from `lldap` (storing the exported user list alongside discovered `jellyfin_id` and `seerr_id` keys).
   - Running `scripts/identity_sync.py` deterministically synchronizes every `lldap` user across all downstream targets:
     - **lldap Group Enforcement**: Automatically adds any new `lldap` user to `jellyfin_users` via GraphQL.
     - **Tinyauth forward-auth & OIDC** (`data/tinyauth/whitelist.txt`, `.env` `TINYAUTH_OAUTH_WHITELIST` + `TINYAUTH_ADMIN_EMAILS`, and pre-seeded `oidc_consents` in `data/tinyauth/tinyauth.db` across all 7 OIDC clients).
     - **OIDC App Databases (`Paperless-ngx`, `AirTrail`, `Homebox`)**: Pre-provisions non-admin user accounts and links their deterministic Tinyauth OIDC `sub` UUIDs in `paperless` (`auth_user` + `socialaccount_socialaccount`), `airtrail` (`"user"`), and `homebox.db` (`users` + `user_groups`) so first-time OIDC logins succeed in 0 clicks without manual registration errors.
     - **Jellyfin (`watch.vrg.rocks`)** (`LDAP-Auth.xml` with `( &(objectClass=person)(|(uid={0})(cn={0})(mail={0})(mailalias={0})) )` filter so users can log in on TV/mobile/web using their email, alias, or username; `SSO-Auth.xml` with `<DefaultProvider>Jellyfin.Plugin.LDAP_Auth.LdapAuthenticationProviderPlugin</DefaultProvider>`, `<DefaultUsernameClaim>email</DefaultUsernameClaim>`, `<SchemeOverride>https</SchemeOverride>`, and pre-seeded `<CanonicalLinks>` mapping every user's email and aliases to their existing Jellyfin GUID; plus `branding.xml` `<LoginDisclaimer>` rendering a 1-click **"Sign in with Google SSO"** button on the web login page).
     - **Seerr (`request.vrg.rocks`)** (linked to the matching `jellyfinUserId` and `email` in `config/seerr/db/db.sqlite3` with `userType = 3` so "Sign in with Jellyfin" accepts the same email/username + LDAP password or Quick Connect and maps to the same account).
     - **Copyparty (`files.vrg.rocks`)** (`idp-hm-usr` header mappings in `config/copyparty/copyparty.conf`).
2. **Zero-Click Google SSO:**
   - When signed into an allowlisted Google account in the browser, navigating to any `*.vrg.rocks` service authenticates and opens the application with **zero button clicks** (no provider selection screen, no OIDC consent prompt, and no secondary app login screen).
   - Enforced at the IdP via `TINYAUTH_OAUTH_AUTOREDIRECT=google`, pre-seeded `oidc_consents` rows in `/data/tinyauth/tinyauth.db`, and per-container auto-redirect/external-auth flags.
3. **Sole Hardcoded Admin (`VRG`):**
   - Varun (`admin@example.com` / `admin-alias@example.com`) is the only administrator across all infrastructure and application databases (`VRG`, superuser/owner, and member of `jellyfin_admins` in `lldap`).
   - Admin-only forward-auth subdomains (`code`, `backrest`, `qui`, `radarr`, `sonarr`, `lidarr`, `prowlarr`, `bazarr`, `cs`, `byparr`, `pb`, `router`, `ldap`) are locked down at the Caddy/Tinyauth edge via `TINYAUTH_APPS_<APP>_OAUTH_WHITELIST` so even allowlisted family accounts cannot access infrastructure consoles.
4. **Strict Email Allowlist & Approval Gate:**
   - No user can authenticate through `auth.vrg.rocks` unless their email address is explicitly listed in [`config/auth/users.json`](../../config/auth/users.json) and synced to `/Users/vrg/Documents/Sol/data/tinyauth/whitelist.txt`.
   - Any unapproved login attempt is rejected at the OAuth callback (`https://auth.vrg.rocks/unauthorized`) and logged via `TINYAUTH_LOG_STREAMS_AUDIT_ENABLED=true`.
   - Approving a new user is a single idempotent command (`./scripts/allowlist_user.sh add <email> [DisplayName]`) that updates `config/auth/users.json` and runs the full 5-target identity sync.
5. **Provider-Agnostic Caddy Forward-Auth Snippet & Native OIDC First:**
   - `Caddyfile` defines a single provider-agnostic `(forward_auth)` snippet imported as `import forward_auth` across all protected routes. `login.vrg.rocks` and `tinyauth.vrg.rocks` permanently redirect (`301`) to `https://auth.vrg.rocks{uri}`.
   - Every container that supports native OpenID Connect (OIDC), LDAP, or trusted reverse-proxy headers / external auth uses its native integration instead of double-login forward-auth.

---

## 2. Four-Tier Authentication Matrix Across All Services

### Tier A: Native OpenID Connect (OIDC) Clients (`https://auth.vrg.rocks/.well-known/openid-configuration`)

Tinyauth v5.2.0 runs a built-in OpenID Certified OIDC Provider backed by RS256 signing keys at `/data/tinyauth/oidc/key.pem`. It computes a deterministic, pairwise `sub` claim for each `(username, client_id)` pair using UUIDv5 (`uuid.uuid5(uuid.NAMESPACE_URL, f"{tinyauth_username}:{client_id}")`), where `tinyauth_username` is the user's email with `@` replaced by `_` (for example `admin_example.com`). Note that `TINYAUTH_LDAP_*` is intentionally **not** set on Tinyauth so Google OAuth remains the sole Tinyauth login backend and `sub` UUIDs never fragment.

| Service | Domain | OIDC Env / Config | Zero-Click Mechanism | Admin (`VRG`) Enforcement |
| :--- | :--- | :--- | :--- | :--- |
| **Paperless-ngx** | `docs.vrg.rocks` | `PAPERLESS_SOCIALACCOUNT_PROVIDERS` (`provider_id: "tinyauth"`) | `PAPERLESS_REDIRECT_LOGIN_TO_SSO: "true"` + `PAPERLESS_DISABLE_REGULAR_LOGIN: "true"` | `auth_user.id=3` (`VRG`, `is_superuser=t`) linked in `socialaccount_socialaccount`. Family accounts (`Member3`, `Member2`, `Member1`) are non-superuser. |
| **Arcane** | `arcane.vrg.rocks` | `OIDC_ENABLED: "true"`, `OIDC_ISSUER_URL: https://auth.vrg.rocks` | `OIDC_AUTO_REDIRECT_TO_PROVIDER: "true"` + `authLocalEnabled=false` in `arcane.db` | `users.username='VRG'` (`roles=["admin"]`, `oidc_subject_id` bound to Tinyauth `sub`). |
| **Homebox** | `inv.vrg.rocks` | `HBOX_OIDC_ENABLED: "true"`, `HBOX_OIDC_ISSUER_URL: https://auth.vrg.rocks` | `HBOX_OIDC_AUTO_REDIRECT: "true"` + `HBOX_OPTIONS_ALLOW_LOCAL_LOGIN: "false"` + `HBOX_OPTIONS_TRUST_PROXY: "true"` | `users.email='admin@example.com'` (`is_superuser=1`). `HBOX_OPTIONS_ALLOW_REGISTRATION: "false"`. |
| **AirTrail** | `fly.vrg.rocks` | `OAUTH_ENABLED: "true"`, `OAUTH_ISSUER_URL: https://auth.vrg.rocks`, callback `https://fly.vrg.rocks/login` | `OAUTH_AUTO_LOGIN: "true"` + `OAUTH_HIDE_PASSWORD_FORM: "true"` | `"user"` table pre-seeded with `VRG` (`is_owner=true, role_id=NULL`) and family (`is_owner=false, role_id='role-user'`). |
| **Coder** | `coder.vrg.rocks` | `CODER_HTTP_ADDRESS: "0.0.0.0:7080"`, `CODER_OIDC_ISSUER_URL: https://auth.vrg.rocks`, `CODER_DISABLE_PASSWORD_AUTH: "true"` | Caddy `redir /login /api/v2/users/oidc/callback 302` | `users.email='admin@example.com'` (`rbac_roles={owner}`, `login_type='oidc'`). New OIDC users default to `member`. |
| **Readeck** | `links.vrg.rocks` | `[[auth.oidc.providers]]` (`id = "tinyauth"`, `url = "https://auth.vrg.rocks"`, `issuer = "https://auth.vrg.rocks"`) in `data/readeck/config.toml` | Native OIDC provider (`https://auth.vrg.rocks`) + Tinyauth edge protection | `VRG` (`admin@example.com`) created with `-a` (admin) flag. |
| **Jellyfin** | `watch.vrg.rocks` | `SSO-Auth.xml` (`google-sso` pointing to `https://auth.vrg.rocks`, `DefaultUsernameClaim=email`, `CanonicalLinks`) + `LDAP-Auth.xml` (`lldap:3890`) | Browser: 1-click Google SSO (`/sso/OID/start/google-sso`) or email/username + LDAP password; TV/Mobile Apps: email/username + LDAP password or Quick Connect | `VRG` (`IsAdministrator=1`, `jellyfin_admins`), `Member1`, `Member2`, `Member3` (`IsAdministrator=0`, `jellyfin_users`). |

### Tier B: Unified LDAP (`lldap`) for Jellyfin & Seerr

- **`lldap` (`lldap/lldap:stable`, `~12 MiB` RAM):**
  - Listens on `::` port `3890` (LDAP, dual-stack IPv6/IPv4 for `sol_default`) and port `17170` (Web UI / GraphQL API at `https://ldap.vrg.rocks`, protected by `import forward_auth` + `TINYAUTH_APPS_LDAP_OAUTH_WHITELIST` for `VRG` only).
  - Base DN: `dc=vrg,dc=rocks`. Users live under `ou=people,dc=vrg,dc=rocks` with custom attribute `mailalias` (`STRING`, `isList: true`, `isVisible: true`) and groups `jellyfin_users` and `jellyfin_admins`.
- **Jellyfin (`watch.vrg.rocks`):**
  - `LDAP-Auth` (`v22.0.0.0`) binds to `lldap:3890` and searches `( &(objectClass=person)(|(uid={0})(cn={0})(mail={0})(mailalias={0})) )` with `<LdapUsernameAttribute>cn</LdapUsernameAttribute>` and `<LdapUidAttribute>entryUUID</LdapUidAttribute>`.
  - Every Jellyfin user (`VRG`, `Member1`, `Member2`, `Member3`) has `AuthenticationProviderId = Jellyfin.Plugin.LDAP_Auth.LdapAuthenticationProviderPlugin`, allowing login by primary email (`admin@example.com`), alias (`admin-alias@example.com`), or username (`VRG` / `vrg`).
  - `SSO-Auth` (`v4.0.0.3`) sets `<DefaultProvider>Jellyfin.Plugin.LDAP_Auth.LdapAuthenticationProviderPlugin</DefaultProvider>` and `<CanonicalLinks>` mapping each email/alias to the existing Jellyfin user GUID so OIDC logins never overwrite `AuthenticationProviderId` or create duplicate accounts.
- **Seerr (`request.vrg.rocks`):**
  - Uses "Sign in with Jellyfin" (`POST /api/v1/auth/jellyfin`), which forwards credentials to Jellyfin `POST /Users/AuthenticateByName` (validated by `lldap`) and matches the returned Jellyfin GUID to `user.jellyfinUserId` in `config/seerr/db/db.sqlite3`.

### Tier C: Trusted-Header & External Auth Behind Tinyauth Forward-Auth

These containers do not need a secondary password prompt because they either read `Remote-Email` / `Remote-User` injected by Caddy's `(forward_auth)` snippet or set their internal auth mode to `External` / `none`:

| Service | Domain | Native Integration Setting | Edge ACL Policy |
| :--- | :--- | :--- | :--- |
| **Copyparty** | `files.vrg.rocks` | `idp-h-usr: Remote-Email` + `idp-hm-usr` mappings in `config/copyparty/copyparty.conf` (auto-managed by `identity_sync.py`) | Allowlisted users (`VRG` gets `rw` on `/` and `/priv`; `member1` and family get `r` on `/`). |
| **QUI** | `qui.vrg.rocks` | `QUI__AUTH_DISABLED: "true"` + `QUI__I_ACKNOWLEDGE_THIS_IS_A_BAD_IDEA: "true"` + `QUI__AUTH_DISABLED_ALLOWED_CIDRS: "0.0.0.0/0,::/0"` | Admin-only (`TINYAUTH_APPS_QUI_OAUTH_WHITELIST`). |
| **code-server** | `code.vrg.rocks` | `AUTH: none` in `compose/coding.yml` | Admin-only (`TINYAUTH_APPS_CODE_OAUTH_WHITELIST`). |
| **Backrest** | `backrest.vrg.rocks` | `"auth": { "disabled": true }` in `config/backrest/config.json` | Admin-only (`TINYAUTH_APPS_BACKREST_OAUTH_WHITELIST`). |
| **Radarr / Sonarr / Lidarr / Prowlarr** | `{radarr,sonarr,lidarr,prowlarr}.vrg.rocks` | `<AuthenticationMethod>External</AuthenticationMethod>` in `config/*/config.xml` (API keys remain enforced for `/api/*`) | Admin-only (`TINYAUTH_APPS_<ARR>_OAUTH_WHITELIST`). |
| **Bazarr** | `bazarr.vrg.rocks` | `auth.type: null` in `config/bazarr/config/config.yaml` (API key remains enforced) | Admin-only (`TINYAUTH_APPS_BAZARR_OAUTH_WHITELIST`). |

### Tier D: Stateless Apps, Shared Apps & Mobile-Direct Exceptions

- **Stateless Web & Dashboard Apps (`dash`, `ignis`, `mind`, `fam`, `scan`, `tools`, `chef`, `pdf`, `speed`, `draw`, `mi`):** Protected by `import forward_auth` in `Caddyfile`. Open in 0 clicks for allowlisted users.
- **Admin Infrastructure Endpoints (`router`, `byparr`, `pb`, `ldap`):** Protected by `import forward_auth` + `TINYAUTH_APPS_<APP>_OAUTH_WHITELIST` restricting access strictly to `VRG`.
- **Intentional Mobile/Public Exceptions (No Browser Forward-Auth):**
  - `qb.vrg.rocks` (`qbittorrent`): Uses qBittorrent native auth so the Android mobile client (`qBitController`) can connect without browser OAuth redirects (`qui.vrg.rocks` is the 0-click web UI).
  - `ntfy.vrg.rocks` (`ntfy`): Accessed directly by the iOS/Android `ntfy` mobile push daemon.
  - `send.vrg.rocks` (`enclosed`): Client-side zero-knowledge E2EE note drop (`PUBLIC_IS_AUTHENTICATION_REQUIRED: "false"`).
  - `aysynbm.vrg.rocks`: Public static utility.

---

## 3. User Allowlist, LDAP & Identity Sync Workflow

### Current Allowlisted Accounts ([`config/auth/users.json`](../../config/auth/users.json))

| UID (`lldap`) | Display Name (`cn` / Jellyfin) | Primary Email (`mail`) | Email Aliases (`mailalias`) | Role | Jellyfin GUID | Seerr ID |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `vrg` | `VRG` | `admin@example.com` | `admin-alias@example.com` | `admin` | `00000000000000000000000000000001` | `1` |
| `member1` | `Member1` | `member1@example.com` | — | `user` | `00000000000000000000000000000002` | `2` |
| `member2` | `Member2` | `member2@example.com` | — | `user` | `00000000000000000000000000000003` | `3` |
| `member3` | `Member3` | `member3@example.com` | — | `user` | Auto-provisioned & synced | Auto-provisioned & synced |

### Approving, Editing, or Revoking Users (`lldap` -> `users.json` One-Way Sync)

- **Add, Edit, or Remove Users in `lldap` (`https://ldap.vrg.rocks`):**
  - Open `https://ldap.vrg.rocks` and create, edit, or delete users (`mail`, `mailalias`, `displayName`, and optional password).
  - Within 15 seconds, the `com.vrg.sol.identity-sync` `launchd` `WatchPaths` agent automatically runs `python3 scripts/identity_sync.py --apply`, which exports the updated user list to [`config/auth/users.json`](../../config/auth/users.json) and syncs Tinyauth, OIDC apps, Jellyfin, Seerr, and Copyparty.
- **Passwordless Users on Jellyfin & Seerr:**
  - If a user is created in `lldap` with only an email and no password (`password_hash = NULL`), direct LDAP password binds will be rejected by `lldap` until a password is set.
  - However, passwordless users can still log into both **Jellyfin (`watch.vrg.rocks`)** and **Seerr (`request.vrg.rocks`)** immediately without any password:
    1. **Jellyfin Web (`watch.vrg.rocks`):** Click **"Sign in with Google SSO"** on the login page (`SSO-Auth.xml` maps their email via `<CanonicalLinks>` to their pre-provisioned Jellyfin user).
    2. **Jellyfin TV & Mobile Apps:** Use **Quick Connect** on the TV/mobile app and approve the 6-digit code from their signed-in `watch.vrg.rocks` browser session (`User Icon -> Quick Connect`).
    3. **Seerr (`request.vrg.rocks`):** Click **"Use Quick Connect"** on the Seerr login page (`/api/v1/auth/jellyfin/quickconnect/initiate`) and approve the 6-digit code in `watch.vrg.rocks`.

```bash
# List the exported config/auth/users.json snapshot
./scripts/allowlist_user.sh list

# Manually dry-run or trigger the one-way lldap -> users.json -> apps sync
./scripts/allowlist_user.sh sync
./scripts/allowlist_user.sh sync --apply
```

---

## 4. Standby Authentik Preservation & Rollback

Authentik has **not** been deleted:
- Its PostgreSQL 16 database (`data/authentik`) and configuration/certificates (`config/authentik`) remain untouched on disk and are still backed up by `scripts/backup.sh` / Backrest.
- Its three services (`authentik-postgresql`, `authentik-server`, `authentik-worker`) are gated behind `profiles: ["standby"]` in `compose/core.yml`.
- Because `Caddyfile` uses the provider-agnostic `(forward_auth)` snippet, switching forward-auth providers only ever requires updating the single `(forward_auth)` block in `Caddyfile`.
