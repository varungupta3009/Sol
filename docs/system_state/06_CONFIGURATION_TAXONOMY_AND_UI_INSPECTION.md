# 06. Configuration Taxonomy & Full-Stack Inspection Matrix

> **Scope:** Complete taxonomy of configuration storage mechanisms across all 29 active containers, 16 standby/ops containers, 10 static web apps, and 2 host LaunchAgents on `Sol` (`dash.vrg.rocks`), reconciling declarative files with SQLite/PostgreSQL database state verified during the October 20, 2026 31-agent swarm audit.  
> **Host Root:** `/Users/vrg/Documents/Sol`  
> **Original Audit Date:** August 2026  
> **Last Synced to Ground Truth:** 2026-10-20  

---

## 1. Executive Summary & Configuration Taxonomy

Every service in the Sol ecosystem falls into one of two configuration models—both of which have now been 100% audited on disk, via live APIs, and inside SQLite (`?immutable=1`) and PostgreSQL (`paperless-db` and `coder` embedded PG) databases:

```text
                                  +---------------------------------------+
                                  |     Sol Server Container Ecosystem    |
                                  +-------------------+-------------------+
                                                      |
                         +----------------------------+----------------------------+
                         |                                                         |
                         v                                                         v
          [ CATEGORY A: DECLARATIVE FILES ]                         [ CATEGORY B: HYBRID DB + FILE / API ]
          (Configured via Git / Host Config Files)                  (Configured via SQLite / PG + Sync Scripts)
          ----------------------------------------                  -------------------------------------------
          - Caddy (Caddyfile, 33 active blocks)                     - Tinyauth v5 (Env + tinyauth.db OIDC consents)
          - Compose Stacks (compose/*.yml, 45 services)             - LLDAP (Env + users.db, source of truth)
          - Glance (glance.yml + user.css)                          - Jellyfin (jellyfin.db + XML + SSO/LDAP plugins)
          - Copyparty (copyparty.conf, synced by script)            - Seerr (db.sqlite3 + settings.json, 43 requests)
          - ntfy (server.yml + cache.db WAL pragmas)                - Radarr (radarr.db + custom_scripts, 0 broken links)
          - code-server (settings.json + Compose env)               - Sonarr (sonarr.db + custom_scripts, 1,379 symlinks)
          - Byparr (Compose env + /tmp tmpfs + shm_size)            - Lidarr (lidarr.db + config.xml)
          - Ignis (Compose env + /vaults mount)                     - Prowlarr (prowlarr.db + FlareSolverr tag routing)
          - Enclosed (Compose env + /app/.data)                     - Bazarr (bazarr.db + config.yaml, profileId=1)
          - Backrest (config.json + excludes.txt)                   - qBittorrent (qBittorrent.conf + categories.json)
          - Scripts & LaunchAgents (scripts/*.sh, *.py, *.plist)    - QUI (qui.db + config.toml, 25 trackers + 10 FUP rules)
                                                                    - Paperless-ngx (PostgreSQL 17 Alpine + Redis 8)
                                                                    - AirTrail (PostgreSQL 17 Alpine 'airtrail' DB)
                                                                    - Homebox (homebox.db v0.26 unified entities)
                                                                    - Readeck (db.sqlite3 + config.toml + SQLite trigger)
                                                                    - Arcane (arcane.db WAL + native OIDC)
                                                                    - Coder (Embedded PG 13.21 + coder/main.tf template)
                                                                    - PocketBase (data.db + auxiliary.db, logs.minLevel=4)
```

---

## 2. Category A: Declarative & File-Driven Services

| Service / Artifact | Primary Configuration Path | Format | Status | Verified Post-Phase-2 Ground Truth (2026-10-20) |
| :--- | :--- | :--- | :--- | :--- |
| **`caddy`** | `./Caddyfile` | Caddyfile | Active (`healthy`) | 33 active site blocks, 12 commented standby vhosts, `(security_headers)` with `Permissions-Policy`, `(optimize)`, `(forward_auth)` to `tinyauth:3000`, `(static_site)` with `route { try_files ...; file_server }` after `forward_auth` and `@immutable` cache headers, streaming buffers on `watch`/`jellyfin`, and external write gates on `ntfy.vrg.rocks` & `send.vrg.rocks`. |
| **Compose stacks** | `docker-compose.yml`, `compose/*.yml` | YAML | Active | 8 domain files defining **29 active `(healthy)` containers**, **15 `standby` containers**, and **1 `ops` container (`rclone`)** = **45** Compose services. Retired `authentik-*`, `flaresolverr`, and `cross-seed` blocks removed. |
| **`ports.json`** | `./ports.json` | JSON | Active | 46 entries (29 active containers, 15 standby containers, 1 ops container `rclone`, 1 standby native app `jellyfin-metal`). Only `caddy` (`80`, `443`) and `qbittorrent` (`42069`) bind host ports in active mode. |
| **`glance`** | `config/glance/config/glance.yml`, `config/glance/assets/user.css` | YAML + CSS | Active (`healthy`) | 3 pages (`Sol`, `Stats`, `Radar`), inlined `sol-catppuccin-mocha` default theme, authenticated Jellyfin (`MediaBrowser Token`) & Paperless (`Accept: application/json`) `custom-api` widgets, `https://auth.vrg.rocks/api/healthz` ingress monitor, and 17 GitHub release trackers. |
| **`copyparty`** | `config/copyparty/copyparty.conf` | Conf | Active (`healthy`) | `v1.20.13`, `rproxy: -1`, `xf-proto-fb: https`, `idp-h-usr: X-Tinyauth-Username`, `rwmda: vrg`, `noidx` excluding `.Spotlight-V100`/`._*`/`backups`, serving `/w/{copyparty,media,torrents,external}`. |
| **`ntfy`** | `config/ntfy/etc/ntfy/server.yml` | YAML | Active (`healthy`) | `v2.31.1`, `base-url: "https://ntfy.vrg.rocks"`, `behind-proxy: true`, `cache-startup-queries` enabling `WAL` + `busy_timeout = 5000`. External unauthenticated `POST`/`PUT` blocked at Caddy edge while internal containers publish to `http://ntfy:80`. |
| **`code-server`** | `compose/coding.yml` + `config/code-server/` | YAML + JSON | Active (`healthy`) | `AUTH: none` behind Tinyauth admin `forward_auth` (`TINYAUTH_APPS_CODE_*`), mounts `/Server` (`/Users/vrg/Documents/Sol`) and `/Documents`, healthcheck on `127.0.0.1:8443/healthz`. |
| **`byparr`** | `compose/media.yml` | YAML | Active (`healthy`) | `v3.0.4` (`invisible-playwright` Firefox 151.0), network alias `flaresolverr`, `shm_size: 1gb`, `tmpfs: /tmp:size=512m,exec,mode=1777`, `BLOCK_MEDIA: "true"`, lightweight `/openapi.json` healthcheck (eliminating 65 GB/day idle browser disk churn). |
| **`ignis`** | `compose/knowledge.yml` + `data/ignis/` | YAML | Active (`healthy`) | `v0.8.18` (Obsidian `1.14.4`), locked to admin emails via `TINYAUTH_APPS_IGNIS_*` (`notes.vrg.rocks` redirects to `ignis.vrg.rocks`), healthcheck on `127.0.0.1:8080/api/version`. |
| **`enclosed`** | `compose/utilities.yml` + `data/enclosed/` | YAML | Active (`healthy`) | `v1.16.0`, note creation (`/`, `/api/notes`) gated by Tinyauth `forward_auth` in `Caddyfile` while recipient note links (`/@*`, `/api/notes/*`) remain publicly viewable. |
| **`backrest`** | `config/backrest/config.json`, `config/backrest/excludes.txt` | JSON + Text | Active (`healthy`) | `v1.14.1` (Restic `0.19.1`, Rclone `v1.74.4`), repos `local-panopticon` (`/repos/local-panopticon`) and `onedrive-cloud` (`rclone:OneDrive:Sol-Restic`), excluding live Postgres/WAL/caches and `/userdata/sol/web/mi`. |
| **Host Scripts & LaunchAgents** | `scripts/*.sh`, `scripts/*.py`, `scripts/launchd/*.plist` | Bash / Python / XML | Active | `stage_db_backups.sh` (TCC-free via Python wrapper + OrbStack `redis:8-alpine` symlink manifest), `identity_sync.py` (`<50ms` SHA-256 fast-path), `torrent_finished.py`, `arr_symlink_dedupe.sh`, `restore.sh`, `sync_static_tools.sh`. |

---

## 3. Category B: Database & API-Driven Services (Audited & Reconciled)

### 1. Tinyauth v5 (`auth.vrg.rocks` / `http://tinyauth:3000`) & LLDAP (`ldap.vrg.rocks` / `http://lldap:17170`)
* **Storage Engines:** SQLite (`data/tinyauth/tinyauth.db`, `data/lldap/users.db`) + `/data/oidc/key.pem` (`0600`) + `/data/whitelist.txt`.
* **Verified State:**
  - **LLDAP (`v0.6.2`, `600 KiB` RAM):** Authoritative identity directory for 4 household users (`vrg` and 3 household member accounts) and groups (`lldap_admin`, `family`). Watched by `com.vrg.sol.identity-sync.plist`.
  - **Tinyauth (`v5.2.0`, `8.98 MiB` RAM):** Enforces Google OAuth 2.0 zero-click login, 17 per-app admin domain whitelists (`TINYAUTH_APPS_*` locked to `TINYAUTH_ADMIN_EMAILS`), and 7 OIDC clients (`paperless`, `arcane`, `homebox`, `airtrail`, `coder`, `readeck`, `jellyfin`).
  - **OIDC Consents:** Pre-seeded in `tinyauth.db` by `scripts/identity_sync.py` (`arcane` and `coder` consents restricted strictly to `admin` users; 29 total consent rows).

---

### 2. Jellyfin (`watch.vrg.rocks` / `http://jellyfin:8096`) & Standby Jellyfin Metal (`:8097`)
* **Storage Engine:** SQLite (`config/jellyfin/data/data/jellyfin.db`) + XML (`system.xml`, `database.xml`, `encoding.xml`, `branding.xml`, `SSO-Auth.xml`, `LDAP-Auth.xml`).
* **Verified State:**
  - **Runtime & Storage:** Jellyfin `12.2.0` (`12.2ubu2604-ls54`), `/tmp/jellyfin` mounted as `2 GiB` `tmpfs` owned by `uid=501,gid=20,mode=0755`, `<LockingBehavior>Optimistic</LockingBehavior>` in `database.xml`, `<ServerName>Sol</ServerName>` in `system.xml`, orphaned `library.db*` removed.
  - **Libraries:** `Movies` (`/media/internal/movies` + `/media/external/media/movies`, 59 movies, 0 broken symlinks), `Shows` (`/media/internal/tv` + `/media/external/media/tv`, 5 series, 758 episodes, 0 broken symlinks), `Home Videos` (`/media/internal/home-videos`, containing `VRG's 1st Birthday` and `The Ba***ds of Business (1995).mp4`).
  - **Zero-Click SSO + LDAP:** `LDAP-Auth` (`v24.0.0.0`) binds to `lldap:3890` (`dc=vrg,dc=rocks`) as primary `AuthenticationProviderId` for all 4 users; `SSO-Auth` (`v4.0.0.4`) maps all 5 Google emails via `<CanonicalLinks>` to the 4 LDAP-backed user GUIDs with a 300ms JS auto-redirect in `branding.xml`.
  - **Jellyfin Metal (`scripts/setup_jellyfin_metal.py`):** Configured as `"status": "standby"` in `ports.json` (`metal.vrg.rocks` commented in `Caddyfile`); `DB_FILE` path bug (`data/data/jellyfin.db`) fixed in `scripts/setup_jellyfin_metal.py`.

---

### 3. Seerr (`request.vrg.rocks` / `http://seerr:5055`)
* **Storage Engine:** SQLite (`config/seerr/db/db.sqlite3`) + `config/seerr/settings.json`.
* **Verified State:**
  - **Version & History:** Seerr `v3.2.0` (`ghcr.io/seerr-team/seerr:latest`), `43` total media requests (including 27 historical Overseerr requests merged via `scripts/archive/merge_overseerr_history.py`) across 4 users.
  - **Radarr & Sonarr Target Roots:** `radarr[0].activeDirectory` updated to `"/external/media/movies"` (`VRG HQ (UHD/FHD)`), `sonarr[0].activeDirectory` set to `"/external/media/tv"` (`Ultra-HD`).
  - **Jellyfin Sync:** Syncs `Movies` and `Shows` cleanly (with `Home Videos` excluded and `The Ba***ds of Business (1995)` relocated to `/media/internal/home-videos/`).

---

### 4. Radarr (`radarr.vrg.rocks`), Sonarr (`sonarr.vrg.rocks`), Lidarr (`lidarr.vrg.rocks`), Prowlarr (`prowlarr.vrg.rocks`) & Bazarr (`bazarr.vrg.rocks`)
* **Storage Engines:** SQLite (`radarr.db`, `sonarr.db`, `lidarr.db`, `prowlarr.db`, `bazarr.db`) + XML/YAML configs.
* **Verified State:**
  - **ExFAT Zero-Copy Pipeline (`radarr` & `sonarr`):** `enablecompleteddownloadhandling = False`, `recyclebin = /external/media/.recycle` (`14` days), `LogLevel = info` across all 4 Servarr apps (with ~300 MB of legacy `.debug.txt` logs purged). `scripts/torrent_finished.py` and `config/{radarr,sonarr}/custom_scripts/arr_symlink_dedupe.sh` maintain relative symlinks (`../../../torrents/...`) on `/Volumes/PANOPTICON` (`0` broken symlinks across `38` movie symlinks and `1,379` TV episode/chapter symlinks; *The Sixth Sense (1999)* linked at `/external/media/movies/The Sixth Sense (1999)`).
  - **Prowlarr (`v2.3.6.5351`):** `FlareSolverr` proxy (`http://flaresolverr:8191/`, backed by `byparr`) timeout increased to `90s`, tag `1` (`flare`) applied to `1337x` and `RuTracker.org`, and zero-grab `LimeTorrents` disabled (eliminating 6-hourly `400 BadRequest` sync errors on Radarr/Lidarr).
  - **Bazarr (`v1.6.2`):** Default language profiles enabled (`serie_default_enabled: true`, `movie_default_enabled: true`, `profileId = 1` assigned to all `5/5` series and `42/42` movies), `default_und_audio_lang: en`, and broken `subdl`/`wizdom` providers removed.

---

### 5. qBittorrent (`qb.vrg.rocks` / `http://qbittorrent:8080`) & QUI (`qui.vrg.rocks` / `http://qui:7476`)
* **Storage Engines:** `qBittorrent.conf` + `categories.json` + `BT_backup/*.fastresume` (`150` torrents) + `config/qui/qui.db`.
* **Verified State:**
  - **qBittorrent (`v5.1.4`):** Unified `/data` and `/external` mounts (`/downloads` retired), `sonarr` category `save_path` fixed to `/external/torrents/tv`, stale `/downloads/files` watched folder and broken `OnTorrentAdded` hook removed, and 7 cross-seed torrents in `/data/torrents/cross-seed-links/` re-pointed to live PANOPTICON paths.
  - **QUI (`v1.32.0`):** All 25 tracker customizations (`tracker_registry.json`) and 10 active FUP/tagging automation rules (38 condition blocks) are active in `qui.db`, governing upload caps and ratio limits across `150 / 150` torrents (`0` untagged) plus 30-minute RSS cross-seed scans (`37/37` runs `success`).

---

### 6. Paperless-ngx (`docs.vrg.rocks`) & AirTrail (`fly.vrg.rocks`) on Shared `paperless-db`
* **Storage Engine:** PostgreSQL 17.11 Alpine (`paperless-db`, `24.2 MiB` RAM) + Redis 8 Alpine (`paperless-broker`, `5.98 MiB` RAM, `--maxmemory 256mb --maxmemory-policy volatile-lru`).
* **Verified State:**
  - **Paperless-ngx (`v2.20.14`):** `290` archived documents, `PAPERLESS_OCR_LANGUAGE=eng+hin+kan+pan`, `2` workers × `2` threads, `passwords.txt` locked to `0600`, and `${PASSPHRASE}` leak removed from `data/paperless/scripts/ntfy_notify.sh`.
  - **AirTrail (`v3.13.0`):** `86,258` airports, `2,165` airlines, 4 OIDC-linked household users (`VRG` as single owner `is_owner=t`, others as `role-user`), guarded against single-owner constraint collisions in `scripts/identity_sync.py`.

---

### 7. Homebox (`inv.vrg.rocks`), Readeck (`links.vrg.rocks`), Arcane (`arcane.vrg.rocks`), Coder (`coder.vrg.rocks`) & PocketBase (`pb.vrg.rocks`)
* **Homebox (`v0.26.2`, `data/homebox/homebox.db`):** Active (`14.1 MiB` RAM), 4 OIDC users in `Home` group (`INR`), `HBOX_OPTIONS_ALLOW_LOCAL_LOGIN: "true"` and `HBOX_WEB_MAX_UPLOAD_SIZE: "10"` enabled so `scan.vrg.rocks` barcode scanner PWA can authenticate and refresh tokens against `POST /api/v1/users/login`.
* **Readeck (`v0.22.3`, `data/readeck/data/db.sqlite3`):** Native OIDC via Tinyauth (redundant `forward_auth` removed from `links.vrg.rocks`), all 4 LLDAP users pre-seeded (`VRG` as `admin`) with `preserve_lldap_user_identity` SQLite trigger, orphaned 0-byte `data/readeck/db.sqlite3` removed.
* **Arcane (`v2.16.1`, `data/arcane/arcane.db`):** Native OIDC (`VRG` mapped to `role_admin`), Distroless `["CMD", "curl", "-fsS", "http://127.0.0.1:3552/api/health"]` healthcheck active, orphaned `arcane.francis.db*` removed.
* **Coder (`v2.38.0`, `config/coder/coderv2/postgres`):** `group_add: ["0"]` grants `/var/run/docker.sock` access inside OrbStack, `CODER_CLUSTER_HOST: "127.0.0.1"` enables in-process NATS pub/sub, `CODER_OIDC_ALLOW_SIGNUPS: "false"` locks out non-admin signups, and `/Sol/coder/main.tf` is pushed and active as template `sol-workspace`.
* **PocketBase (`v0.40.5`, `data/pocketbase/data.db`):** `pb.vrg.rocks/` redirects `302 -> /_/`, `logs.minLevel = 4` set in `_params` (stopping 4,320/day `/api/health` writes to `auxiliary.db`), and `auxiliary.db` excluded from SQLite staging and Restic backups.
