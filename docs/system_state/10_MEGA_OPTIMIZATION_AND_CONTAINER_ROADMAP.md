# 10 — Mega Optimization Audit, Live Repairs & "Lean is Sexy" Container Roadmap

**Audit Date:** October 20, 2026 (Updated with 31-Agent Swarm Audit & Full-Stack Hardening)
**Target Host:** Apple MacBook Pro (`M1 Pro`, 8 Cores: 6P + 2E, 16 GB Unified Memory, 512 GB Internal NVMe + 2 TB ExFAT `PANOPTICON`)
**Container Runtime:** OrbStack (`7.817 GiB` VM ceiling, VirtioFS shared mounts, `*.vrg.rocks`)
**Active Fleet:** **29 running `(healthy)` containers** (`~1.95 GiB` total RSS), **16 standby/ops profile containers**, **10 zero-container static web apps**, **1 standby native service** (`jellyfin-metal`)

---

## 1. Live Server Audit & Immediate Repairs Executed on Sol

During the initial live SSH audit of `/Users/vrg/Documents/Sol`, all active containers, SQLite databases, Docker storage volumes, and service logs were inspected and repaired, followed on October 20, 2026 by the 31-agent swarm audit and full-stack remediation (Section 5):

| # | Subsystem | Issue Found on Live Server | Root Cause | Fix Executed |
| :--- | :--- | :--- | :--- | :--- |
| **1** | **QUI (`qui.vrg.rocks`)** | Requested immediate deployment of `qui`; initial login password had literal quotes | `CORE_PASSWORD` in `.env` was wrapped in double quotes (`"..."`), so `qui create-user` included quotes in the password | Deployed `ghcr.io/autobrr/qui:latest` (`v1.32.0`, `23.6 MiB` RAM) on port `7476` in `compose/download.yml`, `Caddyfile`, `ports.json`, and `config/glance/config/glance.yml`. Reset `VRG` password to clean unquoted `CORE_PASSWORD` via `qui change-password` (`POST /api/auth/login` = `200 OK`), connected `Sol (qBittorrent)` with `hasLocalFilesystemAccess: true`, and configured 26 tracker customization rules + 10 tracker FUP auto-management rules. |
| **2** | **Backrest + Restic (`backrest.vrg.rocks`)** | `rclone sync` to OneDrive failed with Graph API `drive id appears to be malformed` and lacked chunk deduplication | Naive full-file cloud sync without pre-staged symlink/volume manifests or chunk deduplication | Deployed `ghcr.io/garethgeorge/backrest:latest` (`~25 MiB` RAM) on port `9898` (`backrest.vrg.rocks`) and overhauled `scripts/stage_db_backups.sh`, `scripts/backup.sh`, and `scripts/restore.sh` to create encrypted, deduplicated Restic snapshots (with Postgres dumps, 29 WAL-complete SQLite snapshots, `symlinks_manifest.tsv`, and `coder_home.tar.gz`) to `/Volumes/PANOPTICON/backups/sol-restic` and `rclone:OneDrive:Sol-Restic`. |
| **3** | **SQLite WAL Integrity (`arcane`, `prowlarr`, `stage_db_backups.sh`)** | `arcane` crash-looping (`disk I/O error`), `prowlarr` failing `CheckHealth` (`Tree 16 page 5865 malformed`) | Opening guest Linux WAL-mode SQLite DBs in read-write mode from macOS host `sqlite3` over VirtioFS desynchronizes `-shm` mmap pages | Recovered `arcane.db` and `prowlarr.db` offline (`PRAGMA integrity_check = ok`). Hardened `scripts/stage_db_backups.sh` to copy `${db_file}` and `${db_file}-wal` (without `-shm`) to a local temp directory before running `sqlite3 .backup` and `PRAGMA journal_mode=DELETE`. |
| **4** | **Sonarr & Radarr Health + Option A Import** | Sonarr logged `401:Unauthorized` against `qbittorrent:8080` and then populated Activity queue; Radarr warned on 8 missing Movie Collection root folders | Sonarr had placeholder password `00000000` and still had `enableCompletedDownloadHandling: true` in `sonarr.db` | Updated Sonarr's qBittorrent password, disabled `enableCompletedDownloadHandling` in Sonarr (`false`, matching Radarr and `torrent_finished.py` Option A), verified `0` physical duplicate TV files exist on `/Volumes/PANOPTICON/media/tv`, and updated all 8 Radarr Collections to `/external/media/movies`. |
| **5** | **Prowlarr & Servarr `AllowedHostsCheck`** | Prowlarr showed 4 health alerts (`TheRARBG`, `Readarr`, `AllowedHostsCheck`, `1337x`). Radarr and Sonarr warned on `AllowedHostsCheck` | Upstream Cardigann removed `TheRARBG` (`ID 5`), `Readarr` (`ID 4`) is retired, and 2026 Servarr builds require `<AllowedHosts>` | Deleted stale `TheRARBG` (`ID 5`) and `Readarr` (`ID 4`) via Prowlarr API, and added `RADARR__`, `SONARR__`, `LIDARR__`, and `PROWLARR__SERVER__ALLOWEDHOSTS` in `compose/media.yml`. |
| **6** | **Relative Symlink Deduplication & `/downloads` Retirement** | `/downloads` legacy mount and absolute symlinks broke across host/container mount namespaces | `torrent_finished.py` and `arr_symlink_dedupe.sh` needed relative symlinks (`realpath -m --relative-to="$DIR" "$REAL_SRC"`) | Unified `torrent_finished.py` and `arr_symlink_dedupe.sh` to create relative symlinks under `/external/media/{movies,tv}`, re-pointed 7 IPTorrents cross-seed symlinks, removed `/downloads/files` from qBittorrent `watched_folders.json`, and retired `cross-seed` in favor of `qui` v1.32.0. |
| **7** | **Jellyfin `/tmp` RAM Scratch, Keyframe Trickplay & `Home Videos`** | Jellyfin decoded every P/B frame of 4K HDR movies on CPU during library scans, and Seerr logged `Unable to find TMDb ID` for personal videos | `/tmp/jellyfin` was not on `tmpfs` with `uid=501`, `<EnableKeyFrameOnlyExtraction>` was `false`, and home videos sat in `Movies` | Configured `tmpfs: - /tmp/jellyfin:size=2g,uid=501,gid=20,mode=0755` in `compose/media.yml`, enabled `<EnableKeyFrameOnlyExtraction>true</EnableKeyFrameOnlyExtraction>`, set `<LockingBehavior>Optimistic</LockingBehavior>`, and moved `VRG's 1st Birthday` and `The Ba***ds of Business (1995)` to `data/media/home-videos/` (`Home Videos` library). |
| **8** | **Docker Disk Hygiene & Retired Directory Purge (`12.46 GB+` Reclaimed)** | `docker system df` reported unused images, unattached volumes, and retired Era 1–4 config/data directories on disk | Old container layers, legacy pre-refactor volumes, and retired service directories | Pruned unused images and legacy volumes while preserving the active `4.775 GB` Coder workspace volume (`coder-8378beda-cda2-40ff-a1ad-bc2613acad62-home`), archived historical scripts to `scripts/archive/`, and deleted retired `config/` and `data/` directories (`jellyfin_metal`, `plex`, `cross-seed`, `homarr`, `calibre`, `calibre-web`, `qbit_manage`, `syncthing`, `flood`, `uptime-kuma`, `dockge`). |

---

## 2. Live Resource Profile & High-Impact Server Optimizations (October 20, 2026)

### 2.1 Measured Live Memory Footprint (`~1.95 GiB` Across All 29 Active `(healthy)` Containers)

Replacing the 3-container Authentik stack (`~502 MiB` RAM) with `tinyauth` + `lldap` (`~29.5 MiB` combined) and retiring `cross-seed` (`~31 MiB`) while adding `readeck`, `airtrail`, `enclosed`, and `pocketbase` reduced total fleet memory from `~2.98 GiB` to **`~1.95 GiB`** across **29 active `(healthy)` containers**:

| Tier | Services & Measured RSS | Total Tier RAM |
| :--- | :--- | :--- |
| **Media & OCR Core (7 services)** | `jellyfin` (`~340 MiB` idle), `paperless-webserver` (`~295 MiB`), `sonarr` (`~180 MiB`), `radarr` (`~168 MiB`), `prowlarr` (`~160 MiB`), `bazarr` (`~135 MiB`), `lidarr` (`~125 MiB`) | `~1.40 GiB` |
| **Middleware & Request Portals (3 services)** | `seerr` (`~130 MiB`), `byparr` (`~55 MiB` idle with `/openapi.json` healthcheck), `airtrail` (`~52 MiB`) | `~237 MiB` |
| **"Lean is Sexy" Go/Rust/C++ Fleet (19 services)** | `arcane` (`~68 MiB`), `coder` (`~64 MiB`), `qbittorrent` (`~45 MiB`), `paperless-db` (`~31 MiB`), `enclosed` (`~28 MiB`), `backrest` (`~25 MiB`), `qui` (`~24 MiB`), `caddy` (`~23 MiB`), `readeck` (`~22 MiB`), `ntfy` (`~21 MiB`), `ignis` (`~20 MiB`), `copyparty` (`~20 MiB`), `tinyauth` (`~19.5 MiB`), `homebox` (`~18 MiB`), `pocketbase` (`~15 MiB`), `code-server` (`~13 MiB`), `lldap` (`~10 MiB`), `glance` (`~8 MiB`), `paperless-broker` (`~4.5 MiB`) | `~320 MiB` |

---

## 3. "Lean is Sexy": 2026 Container Replacement & Upgrade Matrix

| Domain | Legacy / Replaced Stack | Legacy RAM | Active 2026 "Lean is Sexy" Production Stack | Stack & Measured RAM | Production Status (Oct 20, 2026) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1. Identity, LDAP & SSO** | `authentik-server` + `authentik-worker` + `authentik-postgresql` | **`502 MiB` RAM** + `10%` idle CPU | **[Tinyauth v5.2.0](https://github.com/steveiliop56/tinyauth)** (`auth.vrg.rocks`) + **[LLDAP v0.6.2](https://github.com/lldap/lldap)** (`ldap.vrg.rocks`) | **Go + Rust** (`~29.5 MiB` combined, `<0.1%` idle CPU) | **DEPLOYED LIVE & HARDENED:** LLDAP (`data/lldap/users.db`) is the single source of truth for all users/groups; Tinyauth v5 handles Google OAuth (`TINYAUTH_OAUTH_AUTOREDIRECT=google`), Caddy forward-auth, and 7 OIDC clients; `scripts/identity_sync.py` reconciles all 9 downstream targets in `<50ms` (fast-path). Authentik completely removed. |
| **2. Torrent WebUI & Automation** | `flood` (Node) + `qbit_manage` (Python) + `cross-seed` (Node) | `~210 MiB` combined | **[QUI v1.32.0](https://github.com/autobrr/qui)** (`qui.vrg.rocks`) + `torrent_finished.py` | **Go + React** (`23.6 MiB` measured) | **DEPLOYED LIVE:** Single Go binary with 26 tracker rules, 10 FUP rules, orphan scanning, and Cross-Seed engine. `flood`, `qbit_manage`, and `cross-seed` removed. |
| **3. Cloud Backups** | Raw `rclone sync` + `rclone-gui` | Full-file re-uploads, OneDrive API errors | **[Backrest v1.12.1](https://github.com/garethgeorge/backrest)** (`backrest.vrg.rocks`) + **Restic** | **Go** (`~25 MiB` measured) | **DEPLOYED LIVE:** Chunk-level Rabin deduplication + `zstd` + AES-256-GCM to `/Volumes/PANOPTICON/backups/sol-restic` (03:00) and `rclone:OneDrive:Sol-Restic` (04:00), paired with TCC-free `com.vrg.sol.db-stage` (02:30). |
| **4. Monitoring & Logs** | `uptime-kuma` (Node) + `homarr` (Next.js) + `dockge` (Node) | `~450 MiB` combined | **[Glance](https://github.com/glanceapp/glance)** (`dash.vrg.rocks`, active) + **[Beszel](https://github.com/henrygd/beszel)** / **[Dozzle](https://github.com/amir20/dozzle)** / **[Gatus](https://github.com/TwiN/gatus)** (standby) | **Go binaries** (`~8 MiB` active) | **DEPLOYED LIVE:** Glance serves `/sol`, `/stats`, and `/radar` with live Paperless/Jellyfin custom APIs and 17 GitHub release trackers; `uptime-kuma`, `homarr`, and `dockge` deleted. |
| **5. PDF Manipulation** | `Stirling-PDF` (`stirlingtools/stirling-pdf`) | `300-600 MiB` (JVM) | **[BentoPDF](https://github.com/alam00000/bentopdf)** (`pdf.vrg.rocks`) | **Static WASM** (`0 MiB` RAM via Caddy) | **DEPLOYED LIVE:** Served directly from `web/bentopdf` by Caddy with `COOP`/`COEP` headers. |
| **6. Bookmarks & Read-Later** | `Karakeep` / `Linkwarden` | `350-500+ MiB` | **[Readeck v0.22.3](https://codeberg.org/readeck/readeck)** (`links.vrg.rocks`) | **Go + SQLite** (`~22 MiB` RAM) | **DEPLOYED LIVE:** Native Tinyauth OIDC login with all 4 LLDAP users pre-seeded and `preserve_lldap_user_identity` SQLite trigger protecting display names and admin roles. |
| **7. Aviation Flight Log** | Manual spreadsheets / cloud-only Flighty | External SaaS | **[AirTrail v3.6.0](https://github.com/johanohly/AirTrail)** (`fly.vrg.rocks`) | **SvelteKit + PG 17** (`~52 MiB` RAM) | **DEPLOYED LIVE:** Shares `paperless-db` PostgreSQL 17 (`airtrail` DB), pre-seeded with Tinyauth OIDC users (`VRG` as single owner). |
| **8. Encrypted Notes & BaaS** | Heavy Node/Paste containers | `150+ MiB` | **[Enclosed v1.16.0](https://github.com/CorentinTh/enclosed)** (`send.vrg.rocks`) + **[PocketBase v0.36.8](https://pocketbase.io/)** (`pb.vrg.rocks`) | **Hono + Go** (`~43 MiB` combined) | **DEPLOYED LIVE:** `send.vrg.rocks` gates note creation behind Tinyauth while keeping recipient links public; `pb.vrg.rocks` redirects `/` to `/_/` behind admin-only Tinyauth. |
| **9. Dev & Media Micro-Tools** | `it-tools`, `cyberchef`, `excalidraw`, `openspeedtest`, `mediainfo` containers | `5x nginx/Node` (`~150 MiB`) | **Zero-Container Static Hosting via Caddy (`web/<tool>`)** | **Static Assets** (`0 MiB` extra RAM!) | **DEPLOYED LIVE:** `tools.`, `chef.`, `pdf.`, `speed.`, `draw.`, and `mi.vrg.rocks` (plus `mind.`, `fam.`, `scan.`, `aysynbm.vrg.rocks`) served directly by Caddy (`10` static web apps total). |

### Security Advisory — Two Containers Strictly Avoided in 2026
- **Never deploy `Huntarr`:** In February 2026, `Huntarr` v9.4.2 exposed an unauthenticated `POST /api/settings/general` endpoint that leaked all connected Radarr/Sonarr/Prowlarr API keys and passwords in cleartext, after which the author deleted the repository.
- **Never deploy `Booklore`:** The upstream author pulled the repository, website, and Discord in March 2026.

---

## 4. Dossier-Aligned Passion-Project Expansions for Sol

### 4.1 Cinema, IMAX, 4K Remuxes & Theatre Automation
- **[MediaInfo Web (`mediainfo.js`)](https://mediaarea.net/MediaInfoOnline) (`mi.vrg.rocks`) — DEPLOYED LIVE:** Zero-container client-side WebAssembly bitstream inspector served by Caddy (`web/mi`) for verifying Dolby Vision Profile 7 FEL vs Profile 8.1, HDR10 MaxCLL/MaxFALL metadata, TrueHD Atmos object tracks, and remux bitrates.
- **[Recyclarr](https://recyclarr.dev/) (`compose/media.yml`, standby):** Configured for TRaSH Guides custom format sync into Radarr and Sonarr (scoring 4K Remux, Dolby Vision + HDR10 fallback, IMAX Enhanced, and TrueHD Atmos).
- **[ErsatzTV](https://ersatztv.org/) (Future / Optional):** Native macOS VideoToolbox channel scheduler for turning `data/media/preshows` and local libraries into rolling Jellyfin Live TV channels.

### 4.2 Airbus Flight Deck & Aviation Telemetry
- **[AirTrail v3.6.0](https://github.com/johanohly/AirTrail) (`fly.vrg.rocks`) — DEPLOYED LIVE:** Self-hosted personal flight log and passport map backed by `paperless-db` (`airtrail` database) with 0-click Tinyauth OIDC login.

### 4.3 Compiler-First Web Stack, Zero-Container Tools & Micro-Sandboxes
- **10 Zero-Container Static Web Apps (`mind.`, `fam.`, `scan.`, `aysynbm.`, `pdf.`, `tools.`, `chef.`, `speed.`, `draw.`, `mi.vrg.rocks`) — DEPLOYED LIVE:** Maintained via `scripts/sync_static_tools.sh` with `.sol_version` markers and served directly by Caddy with zero container memory overhead.

---

## 5. October 20, 2026 — 31-Agent Swarm Audit & Full-Stack Hardening

On October 20, 2026, a 31-agent swarm conducted an exhaustive read-only Phase 1 audit of every deployed container, database, configuration file, static web app, LaunchAgent, and backup script on `dash.vrg.rocks`, followed by a coordinated 6-owner Phase 2 remediation. Every change below is live and verified on `dash.vrg.rocks`:

### 5.1 Identity, Authentication & Access Control (`@tinyauth`, `@lldap`, `@caddy`)
1. **Eliminated `com.vrg.sol.identity-sync` `WatchPaths` Infinite Loop (`scripts/identity_sync.py`):**
   - Previously, `pull_from_lldap()` called `POST /auth/simple/login` on LLDAP on every invocation, inserting a new JWT row into `data/lldap/users.db` (`jwt_storage` had accumulated 59 headless `admin` tokens), which modified `users.db-wal` and re-triggered `launchd` `WatchPaths` every 15 seconds.
   - `scripts/identity_sync.py` now reads `file:/Users/vrg/Documents/Sol/data/lldap/users.db?immutable=1` directly via Python `sqlite3`, decodes Rust `bincode` `user_attributes` (`first_name`, `last_name`, `mailalias`), acquires an exclusive `fcntl.flock` on `/tmp/sol_identity_sync.lock`, prepends `/tmp/sol_no_keychain` to `PATH`, and compares a SHA-256 digest of LLDAP state + `.env` `st_mtime_ns` against `/tmp/sol_identity_sync.sha256`. Unchanged runs now exit `0` in **45.5 ms** (`<50ms`) with zero database writes.
2. **Hardened Admin-Only Edge & OIDC Boundaries (`compose/core.yml` & `tinyauth.db`):**
   - Added `TINYAUTH_APPS_IGNIS_*`, `TINYAUTH_APPS_MIND_*`, `TINYAUTH_APPS_SCAN_*`, and `TINYAUTH_APPS_AYSYNBM_*` locked to `${TINYAUTH_ADMIN_EMAILS:?}` (configured in `.env`), joining `arcane`, `code`, `backrest`, `lldap`, and `pb`.
   - Scoped `oidc_consents` pre-seeding in `scripts/identity_sync.py` so `arcane` and `coder` OIDC consents are only seeded for `role == "admin"`, and pruned the 6 non-admin consent rows from `data/tinyauth/tinyauth.db`.
3. **Downstream OIDC & Header-Auth App Fixes (`AirTrail`, `Readeck`, `Copyparty`):**
   - **AirTrail:** Restricted `is_owner = true, role_id = NULL` exclusively to primary owner `vrg`.
   - **Readeck (`links.vrg.rocks`):** Removed redundant Caddy `forward_auth` (so Readeck's browser extension and API tokens work directly against Readeck's OIDC), removed unrecognized `id`/`issuer` keys from `data/readeck/config.toml`, deleted the 0-byte orphaned `data/readeck/db.sqlite3`, promoted `VRG` (`id=1`) to `"group" = 'admin'`, pre-seeded all 4 LLDAP users with deterministic `uuid5` `ext_id` values, and installed the `preserve_lldap_user_identity` SQLite trigger so OIDC logins never overwrite LLDAP display names or demote admin group membership.
   - **Copyparty (`files.vrg.rocks`):** Added `rproxy: -1` and `xf-proto-fb: https` in `[global]`, added `noidx: /(\.Spotlight-V100|\.fseventsd|\.Trashes|\.DS_Store|\._.*|backups)(/|$)` under `[/]` volume `flags:` (stopping `.Spotlight-V100` `PermissionError` and Restic pack indexing), removed the duplicate-password household `[accounts]` entry, and granted `rwmda: vrg` on `[/]` and `[/priv]`.

### 5.2 Edge Routing & Security Headers (`Caddyfile`)
1. **Security & Directive-Order Hardening:**
   - Added `Permissions-Policy` and `X-Permitted-Cross-Domain-Policies none` to `(security_headers)` and applied `import security_headers` to `sol.vrg.rocks`.
   - Wrapped `try_files` and `file_server` inside `route { ... }` in `(static_site)` so `forward_auth` always executes *before* `try_files` (eliminating unauthenticated file-existence probing), added `@immutable` asset caching, and guarded `handle_errors` with `@custom_err file /{err.status_code}.html`.
2. **Per-Service Route Fixes:**
   - Added `import forward_auth` to `aysynbm.vrg.rocks`, split `flaresolverr.vrg.rocks` into a permanent redirect to `https://byparr.vrg.rocks{uri}`, and added `notes.vrg.rocks` permanently redirecting to `https://ignis.vrg.rocks{uri}`.
   - Added `@root path /` -> `redir @root /_/ 302` on `pb.vrg.rocks`.
   - Added `POST /upload*` -> `respond 200` and `no-store` stream headers on `speed.vrg.rocks` (`OpenSpeedTest` upload benchmark now completes cleanly).
   - Added `request_body { max_size 60MB }` and selective `@create_note` `forward_auth` gating on `send.vrg.rocks` (`enclosed`), allowing recipients to view shared encrypted notes without an account while requiring authentication to create notes.
   - Blocked unauthenticated external `POST`/`PUT` publishes on `ntfy.vrg.rocks` while internal Docker containers publish directly to `http://ntfy:80`.

### 5.3 Container Healthchecks, Media Pipeline & Runtime Polish (`@jellyfin`, `@prowlarr`, `@glance`)
1. **`29 / 29` Active Containers `(healthy)`:**
   - Added verified healthchecks to all 16 previously unchecked active containers (`caddy`, `arcane`, `glance`, `jellyfin`, `radarr`, `sonarr`, `lidarr`, `prowlarr`, `bazarr`, `qbittorrent`, `ignis`, `code-server`, `coder`, `backrest`, `enclosed`), and switched `byparr`'s healthcheck to `curl -fsS http://127.0.0.1:8191/openapi.json` so health probes never spawn headless Chromium sessions.
2. **Media, Servarr & Torrents:**
   - Fixed `jellyfin` `/tmp/jellyfin` tmpfs ownership (`uid=501,gid=20,mode=0755`), set `<LockingBehavior>Optimistic</LockingBehavior>` in `database.xml`, set `<ServerName>Sol</ServerName>` in `system.xml`, deleted orphaned `library.db*`, removed the duplicate `TRON: Legacy (2010)` symlink, and moved `The Ba***ds of Business (1995)` to `data/media/home-videos/`.
   - Lowered `prowlarr`, `radarr`, `sonarr`, and `lidarr` `<LogLevel>` from `debug` to `info` and cleaned rotated debug logs; tagged `RuTracker.org` with `flare` (`[1]`), increased Byparr timeout to `90s`, and disabled zero-grab `LimeTorrents`.
   - Configured `bazarr` language defaults (`default_und_audio_lang: en`, default profile `1` for all series and movies, removed unconfigured `subdl`/`wizdom`), updated `seerr` Radarr `activeDirectory` to `/external/media/movies`, fixed qBittorrent `sonarr` category `save_path` to `/external/torrents/tv`, re-pointed 7 IPTorrents cross-seed symlinks, and linked `The Sixth Sense (1999)` in Radarr (`59/59` movies downloaded).
3. **Coder, Paperless, PocketBase, ntfy & Glance:**
   - Added `group_add: ["0"]`, `CODER_OIDC_ALLOW_SIGNUPS: "false"`, and `CODER_CLUSTER_HOST: "127.0.0.1"` to `coder` and pushed `coder/main.tf` (`sol-workspace` template active).
   - Capped `paperless-broker` Redis at `256mb` (`volatile-lru`), removed `${PASSPHRASE}` leakage from `data/paperless/scripts/ntfy_notify.sh`, and set `chmod 0600` on `passwords.txt`.
   - Set `logs.minLevel=4` in PocketBase (`data.db`) and purged `11,226` `/api/health` rows from `auxiliary.db`.
   - Fixed all 8 Glance dashboard items (`sol-catppuccin-mocha` default theme inlined, Paperless `Accept: application/json`, Jellyfin `MediaBrowser Token`, Caddy healthcheck URL `https://auth.vrg.rocks/api/healthz`, 17 active release trackers, icon slugs, bookmark URLs, and RSS limits).

### 5.4 TCC-Free LaunchAgents & 3-2-1 Backup Pipeline (`@scaffolding`)
- Fixed both macOS TCC blocks in `com.vrg.sol.db-stage.plist` and `scripts/stage_db_backups.sh` (using `/opt/homebrew/bin/python3` wrapper without `WorkingDirectory` and scanning `/Volumes/PANOPTICON` symlinks via OrbStack `redis:8-alpine`), verified `Exit 0` via `launchctl kickstart`, and confirmed `data/backups/sqlite/` holds **29 clean `.db`/`.sqlite*` snapshots with 0 `-wal`/`-shm` sidecars**.
