# Sol Authentication, Zero-Click SSO & OIDC Strategy (`Tinyauth v5.2.0`)

**Status:** Active Production Standard (October 2026)
**Primary Identity & OIDC Provider:** `tinyauth` (`ghcr.io/tinyauthapp/tinyauth:v5` v5.2.0 at `https://auth.vrg.rocks`, ~29.4 MiB RAM)
**Standby Legacy Provider:** `authentik-server` + `authentik-worker` + `authentik-postgresql` (`profiles: ["standby"]` in `compose/core.yml`, ~502 MiB RAM saved)

---

## 1. Core Architectural Requirements

Sol's authentication architecture enforces four strict invariants across all `*.vrg.rocks` endpoints:

1. **Zero-Click Google SSO:**
   - When signed into an allowlisted Google account in the browser, navigating to any `*.vrg.rocks` service authenticates and opens the application with **zero button clicks** (no provider selection screen, no OIDC consent prompt, and no secondary app login screen).
   - Enforced at the IdP via `TINYAUTH_OAUTH_AUTOREDIRECT=google`, pre-seeded `oidc_consents` rows in `/data/tinyauth/tinyauth.db`, and per-container auto-redirect/external-auth flags.
2. **Sole Hardcoded Admin (`VRG`):**
   - Varun (`admin@example.com` / `admin-alias@example.com`) is the only administrator across all infrastructure and application databases (`VRG`, superuser/owner).
   - Admin-only forward-auth subdomains (`code`, `backrest`, `qui`, `radarr`, `sonarr`, `lidarr`, `prowlarr`, `bazarr`, `cs`, `byparr`, `pb`, `router`) are locked down at the Caddy/Tinyauth edge via `TINYAUTH_APPS_<APP>_OAUTH_WHITELIST` so even allowlisted family accounts cannot access infrastructure consoles.
3. **Strict Email Allowlist & Approval Gate:**
   - No user can authenticate through `auth.vrg.rocks` unless their email address is explicitly listed in `/Users/vrg/Documents/Sol/data/tinyauth/whitelist.txt` (and `TINYAUTH_OAUTH_WHITELIST`).
   - Any unapproved login attempt is rejected at the OAuth callback (`https://auth.vrg.rocks/unauthorized`) and logged via `TINYAUTH_LOG_STREAMS_AUDIT_ENABLED=true`.
   - Approving a new user is a single idempotent command (`./scripts/allowlist_user.sh add <email>`) that updates `whitelist.txt` and `.env`, pre-seeds 0-click OIDC consent rows for all 7 OIDC clients, and restarts `tinyauth` in ~1 second without invalidating active sessions.
4. **Native OIDC / Trusted-Header Upgrade First:**
   - Every container that supports native OpenID Connect (OIDC) or trusted reverse-proxy headers / external auth uses its native integration instead of double-login forward-auth.

---

## 2. Three-Tier Authentication Matrix Across All Services

### Tier A: Native OpenID Connect (OIDC) Clients (`https://auth.vrg.rocks/.well-known/openid-configuration`)

Tinyauth v5.2.0 runs a built-in OpenID Certified OIDC Provider backed by RS256 signing keys at `/data/tinyauth/oidc/key.pem`. It computes a deterministic, pairwise `sub` claim for each `(username, client_id)` pair using UUIDv5 (`uuid.uuid5(uuid.NAMESPACE_URL, f"{tinyauth_username}:{client_id}")`), where `tinyauth_username` is the user's email with `@` replaced by `_` (for example `admin_example.com`).

| Service | Domain | OIDC Env / Config | Zero-Click Mechanism | Admin (`VRG`) Enforcement |
| :--- | :--- | :--- | :--- | :--- |
| **Paperless-ngx** | `docs.vrg.rocks` | `PAPERLESS_SOCIALACCOUNT_PROVIDERS` (`provider_id: "tinyauth"`) | `PAPERLESS_REDIRECT_LOGIN_TO_SSO: "true"` + `PAPERLESS_DISABLE_REGULAR_LOGIN: "true"` | `auth_user.id=3` (`VRG`, `is_superuser=t`) linked in `socialaccount_socialaccount`. Family accounts (`Member3`, `Member2`, `Member1`) are non-superuser. |
| **Arcane** | `arcane.vrg.rocks` | `OIDC_ENABLED: "true"`, `OIDC_ISSUER_URL: https://auth.vrg.rocks` | `OIDC_AUTO_REDIRECT_TO_PROVIDER: "true"` + `authLocalEnabled=false` in `arcane.db` | `users.username='VRG'` (`roles=["admin"]`, `oidc_subject_id` bound to Tinyauth `sub`). |
| **Homebox** | `inv.vrg.rocks` | `HBOX_OIDC_ENABLED: "true"`, `HBOX_OIDC_ISSUER_URL: https://auth.vrg.rocks` | `HBOX_OIDC_AUTO_REDIRECT: "true"` + `HBOX_OPTIONS_ALLOW_LOCAL_LOGIN: "false"` + `HBOX_OPTIONS_TRUST_PROXY: "true"` | `users.email='admin@example.com'` (`is_superuser=1`). `HBOX_OPTIONS_ALLOW_REGISTRATION: "false"`. |
| **AirTrail** | `fly.vrg.rocks` | `OAUTH_ENABLED: "true"`, `OAUTH_ISSUER_URL: https://auth.vrg.rocks`, callback `https://fly.vrg.rocks/login` | `OAUTH_AUTO_LOGIN: "true"` + `OAUTH_HIDE_PASSWORD_FORM: "true"` | `"user"` table pre-seeded with `VRG` (`is_owner=true, role_id=NULL`) and family (`is_owner=false, role_id='role-user'`). |
| **Coder** | `coder.vrg.rocks` | `CODER_HTTP_ADDRESS: "0.0.0.0:7080"`, `CODER_OIDC_ISSUER_URL: https://auth.vrg.rocks`, `CODER_DISABLE_PASSWORD_AUTH: "true"` | Caddy `redir /login /api/v2/users/oidc/callback 302` | `users.email='admin@example.com'` (`rbac_roles={owner}`, `login_type='oidc'`). New OIDC users default to `member`. |
| **Readeck** | `links.vrg.rocks` | `[[auth.oidc.providers]]` (`id = "tinyauth"`, `url = "https://auth.vrg.rocks"`, `issuer = "https://auth.vrg.rocks"`) in `data/readeck/config.toml` | Native OIDC provider (`https://auth.vrg.rocks`) + Tinyauth edge protection | `VRG` (`admin@example.com`) created with `-a` (admin) flag. |
| **Jellyfin** | `watch.vrg.rocks` | `SSO-Auth.xml` (`google-sso` pointing to `https://auth.vrg.rocks`) | SSO button / `/sso/OID/start/google-sso` (no Caddy forward-auth so TV/mobile apps work natively) | `VRG` (`IsAdministrator=1`), `Member1` & `Member2` (`IsAdministrator=0`). |

### Tier B: Trusted-Header & External Auth Behind Tinyauth Forward-Auth

These containers do not need a secondary password prompt because they either read `Remote-Email` / `Remote-User` injected by Caddy's `(forward_auth)` snippet or set their internal auth mode to `External` / `none`:

| Service | Domain | Native Integration Setting | Edge ACL Policy |
| :--- | :--- | :--- | :--- |
| **Copyparty** | `files.vrg.rocks` | `idp-h-usr: Remote-Email` + `idp-hm-usr: ^Remote-Email^admin@example.com^vrg` in `config/copyparty/copyparty.conf` | Allowlisted users (`VRG` gets `rw` on `/` and `/priv`; `member1` and family get `r` on `/`). |
| **QUI** | `qui.vrg.rocks` | `QUI__AUTH_DISABLED: "true"` + `QUI__I_ACKNOWLEDGE_THIS_IS_A_BAD_IDEA: "true"` + `QUI__AUTH_DISABLED_ALLOWED_CIDRS: "0.0.0.0/0,::/0"` | Admin-only (`TINYAUTH_APPS_QUI_OAUTH_WHITELIST`). |
| **code-server** | `code.vrg.rocks` | `AUTH: none` in `compose/coding.yml` | Admin-only (`TINYAUTH_APPS_CODE_OAUTH_WHITELIST`). |
| **Backrest** | `backrest.vrg.rocks` | `"auth": { "disabled": true }` in `config/backrest/config.json` | Admin-only (`TINYAUTH_APPS_BACKREST_OAUTH_WHITELIST`). |
| **Radarr / Sonarr / Lidarr / Prowlarr** | `{radarr,sonarr,lidarr,prowlarr}.vrg.rocks` | `<AuthenticationMethod>External</AuthenticationMethod>` in `config/*/config.xml` (API keys remain enforced for `/api/*`) | Admin-only (`TINYAUTH_APPS_<ARR>_OAUTH_WHITELIST`). |
| **Bazarr** | `bazarr.vrg.rocks` | `auth.type: null` in `config/bazarr/config/config.yaml` (API key remains enforced) | Admin-only (`TINYAUTH_APPS_BAZARR_OAUTH_WHITELIST`). |

### Tier C: Stateless Apps, Shared Apps & Mobile-Direct Exceptions

- **Stateless Web & Dashboard Apps (`dash`, `ignis`, `mind`, `fam`, `scan`, `tools`, `chef`, `pdf`, `speed`, `draw`, `mi`):** Protected by `import forward_auth` in `Caddyfile`. Open in 0 clicks for allowlisted users.
- **Admin Infrastructure Endpoints (`router`, `cs`, `byparr`, `pb`):** Protected by `import forward_auth` + `TINYAUTH_APPS_<APP>_OAUTH_WHITELIST` restricting access strictly to `VRG`.
- **Seerr (`request.vrg.rocks`):** Protected by `import forward_auth` at the edge plus persistent `connect.sid` session cookie (`VRG` = Admin, `Member1` & `Member2` = Request user).
- **Intentional Mobile/Public Exceptions (No Browser Forward-Auth):**
  - `qb.vrg.rocks` (`qbittorrent`): Uses qBittorrent native auth so the Android mobile client (`qBitController`) can connect without browser OAuth redirects (`qui.vrg.rocks` is the 0-click web UI).
  - `ntfy.vrg.rocks` (`ntfy`): Accessed directly by the iOS/Android `ntfy` mobile push daemon.
  - `send.vrg.rocks` (`enclosed`): Client-side zero-knowledge E2EE note drop (`PUBLIC_IS_AUTHENTICATION_REQUIRED: "false"`).
  - `aysynbm.vrg.rocks`: Public static utility.

---

## 3. User Allowlist & Approval Workflow

### Current Allowlisted Accounts (`/Users/vrg/Documents/Sol/data/tinyauth/whitelist.txt`)

- **Admin (`TINYAUTH_ADMIN_EMAILS`):**
  - `admin@example.com` (`VRG`)
  - `admin-alias@example.com` (`VRG`)
- **Approved Family / Standard Users:**
  - `member1@example.com` (`Member1`)
  - `member2@example.com` (`Member2` / `Member2`)
  - `member3@example.com` (`Member3`)

### Approving or Revoking a User

To approve a new user's email address (so they get instant zero-click access whenever signed into Google with that email, and zero OIDC consent prompts):

```bash
# List currently allowlisted emails
./scripts/allowlist_user.sh list

# Approve a new email address (updates whitelist.txt + .env, pre-seeds OIDC consent, restarts tinyauth)
./scripts/allowlist_user.sh add friend@gmail.com

# Revoke an email address
./scripts/allowlist_user.sh remove friend@gmail.com
```

### Expanding to Additional SSO Providers Later

Because Tinyauth matches allowlisted users by their verified OAuth email address (`TINYAUTH_OAUTH_WHITELISTFILE=/data/whitelist.txt`), adding GitHub, Apple, or any generic OIDC provider later only requires adding `TINYAUTH_OAUTH_PROVIDERS_<PROVIDER>_CLIENTID` and `CLIENTSECRET` in `compose/core.yml`. Any allowlisted email address is automatically recognized regardless of which upstream OAuth provider verified that email.

---

## 4. Standby Authentik Preservation & Rollback

Authentik has **not** been deleted:
- Its PostgreSQL 16 database (`data/authentik`) and configuration/certificates (`config/authentik`) remain untouched on disk and are still backed up by `scripts/backup.sh` / Backrest.
- Its three services (`authentik-postgresql`, `authentik-server`, `authentik-worker`) are gated behind `profiles: ["standby"]` in `compose/core.yml`.
- To start Authentik on standby at any time:
  ```bash
  docker compose --profile standby up -d authentik-postgresql authentik-server authentik-worker
  ```
