<div align="center">

# ☀️ Sol

**A modular home server on an Apple Silicon M1 Pro Mac.**

[![Host](https://img.shields.io/badge/Host-macOS%20Apple%20Silicon%20(M1%20Pro)-000000?style=for-the-badge&logo=apple&logoColor=white)](#)
[![Docker](https://img.shields.io/badge/Docker-Compose%20V2%20(include%20%2B%20profiles)-2496ED?style=for-the-badge&logo=docker&logoColor=white)](#)
[![Reverse Proxy](https://img.shields.io/badge/Ingress-Caddy%20v2%20(HTTP%2F3%20%2B%20TLS)-1F88C0?style=for-the-badge&logo=caddy&logoColor=white)](#)
[![Identity](https://img.shields.io/badge/Auth-Tinyauth%20v5%20%2B%20LLDAP-10B981?style=for-the-badge)](#)
[![Filesystem](https://img.shields.io/badge/Storage-APFS%20Hardlinks%20%2B%20ExFAT%20Symlinks-34D058?style=for-the-badge)](#)
[![Backup](https://img.shields.io/badge/Backup-Backrest%20%2B%20Restic-0078D4?style=for-the-badge)](#)

---

</div>

## Table of Contents

1. [Overview](#overview)
2. [Architecture Topology](#architecture-topology)
3. [Domain Stacks](#domain-stacks)
4. [Active and Standby Services](#active-and-standby-services)
5. [Storage, Hardlinks, and ExFAT Symlinks](#storage-hardlinks-and-exfat-symlinks)
6. [Repository Structure](#repository-structure)
7. [Port and Ingress Matrix](#port-and-ingress-matrix)
8. [Operational Commands](#operational-commands)
9. [Backup and Disaster Recovery](#backup-and-disaster-recovery)
10. [Secrets and Security](#secrets-and-security)
11. [Documentation Index](#documentation-index)

---

## Overview

Sol is a single-node home server on an Apple Silicon M1 Pro MacBook Pro (10-core CPU, 16 GB unified memory, macOS Tahoe 26.2) running OrbStack. It provides:

- Reverse proxy routing with automatic Let's Encrypt HTTPS, HTTP/3 (QUIC), and security headers
- Zero-click Google SSO, native OpenID Connect (OIDC), and centralized LDAP directory sync through Tinyauth v5 (`~29 MiB` RAM) and LLDAP (`~12 MiB` RAM)
- Automated media requests, BitTorrent downloads, tracker FUP governance, and cross-seeding
- Document archiving with multilingual OCR (`eng+hin+kan+pan`)
- Browser IDEs, Coder cloud workspaces (`sol-workspace`), and a PocketBase backend sandbox
- High-speed file serving, WebDAV, physical inventory tracking, flight logging, encrypted file drops, and push notifications

At a glance:

| Item | Value |
| :--- | :--- |
| Active containers (default `docker compose up -d`) | 29 (`29/29` reporting `(healthy)`) |
| Profile-gated containers (`15` on `standby`, `1` on `ops` for `rclone`) | 16 (`45` total Compose service definitions) |
| Zero-container static web apps (served directly by `caddy`) | 10 (`mind.`, `fam.`, `scan.`, `aysynbm.`, `tools.`, `chef.`, `pdf.`, `speed.`, `draw.`, `mi.vrg.rocks`) |
| Standby native host process | 1 (`jellyfin-metal` on port `8097`) |
| Active stack memory footprint | `~1.95 GiB` of `16 GiB` unified RAM |
| Compose project and network | `sol`, `sol_default` |
| Public domain | `*.vrg.rocks` |

### Key Principles

- **Apple Silicon tuning:** Concurrency is set per service. Paperless runs `PAPERLESS_TASK_WORKERS: 2` and `PAPERLESS_THREADS_PER_WORKER: 2`. PostgreSQL 17 (`paperless-db`) uses `shared_buffers=256MB`, `work_mem=16MB`, and `effective_cache_size=1GB`. Redis 8 (`paperless-broker`) is capped at `256mb` (`volatile-lru`). Caddy uses 32 KB streaming buffers on the Jellyfin routes.
- **Modular Compose & healthchecks:** The root `docker-compose.yml` loads 8 domain files under `compose/` with Compose V2 `include:` and `x-logging` JSON log rotation (`max-size: 10m`, `max-file: 3`). Every active container defines an internal `healthcheck`, and containers reach each other by name on `sol_default` (for example `http://radarr:7878` or `http://tinyauth:3000`).
- **Profiles, not comments:** Inactive services are full definitions with `profiles: ["standby"]` (or `profiles: ["ops"]` for `rclone`). `docker compose config` validates all 45 definitions, and only the 29 active services start by default.
- **Zero-copy media storage across APFS and ExFAT:** A unified `/data` mount on the internal APFS SSD lets downloads hardlink into `/data/media`. On the external 2 TB ExFAT drive (`/Volumes/PANOPTICON`, mounted at `/external`), `scripts/torrent_finished.py` and `scripts/arr_symlink_dedupe.sh` create per-file relative symlinks from `/external/media/{movies,tv}` to `/external/torrents/{movies,tv}` so files never duplicate across ExFAT.
- **Zero-click edge, OIDC & Unified LDAP (`lldap`) identity:** Caddy, Tinyauth v5 (`auth.vrg.rocks`), and `lldap` (`ldap.vrg.rocks`) connect every user's single email across all interfaces (`data/lldap/users.db` -> `config/auth/users.json` via `scripts/identity_sync.py` and `com.vrg.sol.identity-sync.plist`), enforcing zero-click Google OAuth, pre-seeded OIDC consent for 7 native OIDC clients (`paperless-ngx`, `arcane`, `homebox`, `airtrail`, `coder`, `readeck`, `jellyfin`), unified LDAP login for Jellyfin and Seerr, trusted-header or external auth on `copyparty`, `qui`, `code-server`, `backrest`, `radarr`, `sonarr`, `lidarr`, `prowlarr`, and `bazarr`, and per-app admin ACLs (`vrg` only). See [`11_AUTHENTICATION_AND_SSO_STRATEGY.md`](docs/system_state/11_AUTHENTICATION_AND_SSO_STRATEGY.md).
- **State vs configuration:** Version control tracks declarative infrastructure only. Application state is backed up nightly through [`scripts/stage_db_backups.sh`](scripts/stage_db_backups.sh) (`com.vrg.sol.db-stage.plist` at `03:00 IST`) and `backrest` (`backrest.vrg.rocks`) as encrypted, deduplicated Restic snapshots to `/Volumes/PANOPTICON/backups/sol-restic` (`03:30 IST`) and `rclone:OneDrive:Sol-Restic` (`04:00 IST`).

---

## Architecture Topology

```text
                                  [ Internet / WAN ]
                                           |
                       +-------------------+-------------------+
                       |                                       |
                       v                                       v
         +---------------------------+            +-------------------------+
         |  Caddy (:80, :443 TCP/UDP)|            | qBittorrent peer port   |
         |  TLS, HTTP/3, forward auth|            | 42069 TCP/UDP (WAN)     |
         +-------------+-------------+            +-------------------------+
                       |
       +---------------+--------------------+--------------------------+
       | forward_auth / OIDC                |                          |
       v                                    v                          v
+-----------------------------+  +--------------------+  +--------------------------+
| Tinyauth v5 (:3000, auth.)  |  | Glance (:8080)     |  | 10 Static Web Apps (0MB) |
| 0-Click Google SSO & 7 OIDC |  | 3-Page Command Ctr |  |  /mind, /fam, /scan,     |
+--------------+--------------+  +--------------------+  |  /aysynbm, /tools, /chef,|
               |                                         |  /pdf, /speed, /draw, /mi|
               v                                         +--------------------------+
+-----------------------------+
| LLDAP (:3890/:17170, ldap.) |
| Rust LDAP + identity_sync   |
+--------------+--------------+
               |
  +------------+-------------------+------------------------------+
  |                                |                              |
  v                                v                              v
+--------------------------+  +------------------------+  +--------------------------+
| Media & Torrent Pipeline |  | Docs, Knowledge & Dev  |  | Utilities, Storage & DR  |
| - Jellyfin (:8096)       |  | - Paperless (:8000)    |  | - Copyparty (:3923)      |
| - Seerr (:5055)          |  | - Redis 8 (:6379)      |  | - Homebox (:7745)        |
| - Radarr (:7878)         |  | - Postgres 17 (:5432)  |  | - Backrest (:9898)       |
| - Sonarr (:8989)         |  | - Ignis (:8080)        |  | - Enclosed (:8787)       |
| - Bazarr (:6767)         |  | - Readeck (:8000)      |  | - AirTrail (:3000)       |
| - Lidarr (:8686)         |  | - code-server (:8443)  |  | - ntfy (:80)             |
| - Prowlarr (:9696)       |  | - Coder (:7080)        |  | - Arcane (:3552)         |
| - Byparr (:8191)         |  | - PocketBase (:8090)   |  +--------------------------+
| - qBittorrent (:8080)    |  +------------------------+
| - QUI (:7476)            |
+--------------------------+
```

---

## Domain Stacks

The server is split into 8 compose files in [`compose/`](compose). Standby services in each file start only with `--profile standby` (or `--profile ops` for `rclone`).

### 1. Ingress and Identity ([`compose/core.yml`](compose/core.yml))

- **[Caddy v2](https://caddyserver.com/)** (`caddy:${CADDY_TAG:-2}`): Edge reverse proxy with Let's Encrypt TLS, HTTP/3, `zstd`/`gzip` compression, security headers (`Permissions-Policy`, `X-Permitted-Cross-Domain-Policies`, HSTS), `(forward_auth)` middleware, and static file hosting for 10 zero-container web apps (`/mind`, `/fam`, `/scan`, `/aysynbm`, `/tools`, `/chef`, `/pdf`, `/speed`, `/draw`, `/mi`).
- **[Tinyauth v5](https://tinyauth.app/)** (`ghcr.io/tinyauthapp/tinyauth:${TINYAUTH_TAG:-v5}`): Primary forward-auth and OpenID Connect (OIDC) provider (`auth.vrg.rocks`, `~29 MiB` RAM) with silent zero-click Google OAuth (`TINYAUTH_OAUTH_AUTOREDIRECT=google`), strict email allowlisting (`data/tinyauth/whitelist.txt`), 7 built-in OIDC clients (`paperless-ngx`, `arcane`, `homebox`, `airtrail`, `coder`, `readeck`, `jellyfin`), and per-app admin ACLs (`code`, `backrest`, `qui`, `radarr`, `sonarr`, `lidarr`, `prowlarr`, `bazarr`, `cs`, `byparr`, `pb`, `router`, `ldap`, `ignis`, `mind`, `scan`, `aysynbm`).
- **[LLDAP](https://github.com/lldap/lldap)** (`ghcr.io/lldap/lldap:${LLDAP_TAG:-stable}`): Lightweight Rust + SQLite LDAP directory (`ldap://lldap:3890` and `https://ldap.vrg.rocks`, `~12 MiB` RAM). Managed by [`scripts/identity_sync.py`](scripts/identity_sync.py) and `com.vrg.sol.identity-sync.plist` (`<50ms` SHA-256 fast-path check on `data/lldap/users.db?immutable=1`) to synchronize users across Tinyauth, OIDC apps, Jellyfin, Seerr, and Copyparty.
- **[Arcane](https://github.com/getarcaneapp/arcane)** (`ghcr.io/ofkm/arcane:${ARCANE_TAG:-latest}`): Docker stack manager (`arcane.vrg.rocks`, port `3552`) with zero-click Tinyauth OIDC (`OIDC_AUTO_REDIRECT_TO_PROVIDER: "true"`), SQLite in WAL mode, and `LOG_LEVEL: info`.

### 2. Monitoring and Dashboards ([`compose/monitoring.yml`](compose/monitoring.yml))

- **[Glance](https://github.com/glanceapp/glance)** (`glanceapp/glance:latest`): Declarative 3-page command center ([`config/glance/config/glance.yml`](config/glance/config/glance.yml)) with `Sol` (`/sol`), `Stats & Ops` (`/stats`), and `Radar` (`/radar`), inlined `sol-catppuccin-mocha` default theme and custom GM3 stylesheet ([`config/glance/assets/user.css`](config/glance/assets/user.css)), internal HTTP health monitors across 26 endpoints, `custom-api` telemetry for Jellyfin, Seerr, Radarr, Sonarr, Prowlarr, and Paperless-ngx, live Docker socket container status, and `/media/panopticon` 2 TB ExFAT drive telemetry (`dash.vrg.rocks`, `sol.vrg.rocks`).
- *Standby:* Gatus, Dozzle, Beszel, Beszel Agent.

### 3. Media and Servarr ([`compose/media.yml`](compose/media.yml))

- **[Jellyfin](https://jellyfin.org/) (container):** Main streaming server (`watch.vrg.rocks`, `jellyfin.vrg.rocks`, port `8096`) with `SSO-Auth` (Google OIDC) + `LDAP-Auth` (`lldap`), `Optimistic` SQLite locking, and a 2 GB `uid=501` `/tmp/jellyfin` `tmpfs` scratch disk.
- **Jellyfin Metal (native macOS standby):** Host process with Apple VideoToolbox hardware transcoding and HDR tone mapping (`metal.vrg.rocks`, port `8097`). Managed by [`scripts/setup_jellyfin_metal.py`](scripts/setup_jellyfin_metal.py).
- **[Seerr](https://github.com/seerr-team/seerr):** Request and discovery portal (`request.vrg.rocks`, `seerr.vrg.rocks`, `jellyseerr.vrg.rocks`, port `5055`) containing all 43 historical and current media requests back to May 2025. Keeps the network alias `jellyseerr`.
- **[Radarr](https://radarr.video/), [Sonarr](https://sonarr.tv/), [Lidarr](https://lidarr.audio/), [Bazarr](https://www.bazarr.media/):** Movie, TV, music, and subtitle managers on the unified `/data` and `/external` mounts with `<AuthenticationMethod>External</AuthenticationMethod>` (zero double-login behind Tinyauth), `/external/media/.recycle` 14-day recycle bin protection, and `arr_symlink_dedupe.sh` custom script hooks.
- **[Prowlarr](https://prowlarr.com/):** Indexer manager (`prowlarr.vrg.rocks`, port `9696`).
- **[Byparr](https://github.com/ThePhaseless/Byparr)** (`ghcr.io/thephaseless/byparr:latest`): Camoufox/Playwright Cloudflare Turnstile solver on port `8191` (`byparr.vrg.rocks`, with `flaresolverr.vrg.rocks` 301 redirect and network alias `flaresolverr`), hardened with `shm_size: 1gb`, `/tmp` tmpfs, `BLOCK_MEDIA: "true"`, and `/openapi.json` healthcheck.
- *Standby:* Recyclarr, Wizarr.

### 4. Downloads and Cross-Seeding ([`compose/download.yml`](compose/download.yml))

- **[qBittorrent](https://www.qbittorrent.org/):** Torrent client with WAN peer port `42069` TCP/UDP and WebUI on `8080` (`qb.vrg.rocks`), paired with the `scripts/torrent_finished.py` Option A completion hook.
- **[QUI](https://github.com/autobrr/qui)** (`ghcr.io/autobrr/qui:v1.32.0`): Single-binary Go WebUI, Cross-Seed engine, and tracker automation manager for qBittorrent on port `7476` (`qui.vrg.rocks`, `~55 MiB` RAM). Configured with 26 tracker definitions ([`config/qui/tracker_registry.json`](config/qui/tracker_registry.json)), 25 Tracker Customizations, 10 FUP and health automation rules, Prowlarr Torznab cross-seeding, Radarr/Sonarr external engines, library scan, and orphan scan.
- Both mount `${DOCKER_DATA_DIR}:/data` and `${EXTERNAL_DRIVE_00}:/external`.
- *Standby:* Unpackerr.

### 5. Document Management and OCR ([`compose/paperless.yml`](compose/paperless.yml))

- **[Paperless-ngx](https://docs.paperless-ngx.com/)** (`ghcr.io/paperless-ngx/paperless-ngx:${PAPERLESS_TAG:-latest}`): Document archive (`docs.vrg.rocks`, `paperless.vrg.rocks`, port `8000`) with OCR (`eng+hin+kan+pan`), zero-click Tinyauth OIDC (`PAPERLESS_REDIRECT_LOGIN_TO_SSO=true`), `pre-consumption.py` PDF decryption hook, and `ntfy_notify.sh` post-consumption alerts.
- **Redis broker (`paperless-broker`):** `redis:8-alpine` tuned with `--save 60 1 --loglevel warning --maxmemory 256mb --maxmemory-policy volatile-lru`.
- **PostgreSQL 17 (`paperless-db`):** `postgres:17-alpine` (`PG 17.11` musl, hosting both the `paperless` and `airtrail` databases).
- *Standby:* Gotenberg, Apache Tika, Paperless-AI.

### 6. Knowledge and Bookmarks ([`compose/knowledge.yml`](compose/knowledge.yml))

- **[Ignis](https://github.com/nobbe/ignis):** Obsidian vault sync (`ignis.vrg.rocks`, with `notes.vrg.rocks` 301 redirect).
- **[Readeck](https://codeberg.org/readeck/readeck)** (`codeberg.org/readeck/readeck:${READECK_TAG:-latest}`): Single-binary Go + SQLite bookmark and read-later article archiver (`links.vrg.rocks`, port `8000`) with native Tinyauth OIDC, full-text reader mode, highlights, EPUB export, and the `preserve_lldap_user_identity` SQLite trigger.
- *Standby:* LeafWiki, Kavita.

### 7. Developer Workspaces & Backend Sandboxes ([`compose/coding.yml`](compose/coding.yml))

- **[code-server](https://github.com/coder/code-server):** Browser VS Code (`code.vrg.rocks`, port `8443`) with the Sol repo at `/Server` and `/Users/vrg/Documents` at `/Documents`, gated by Tinyauth admin ACL (`AUTH=none`).
- **[Coder](https://coder.com/)** (`ghcr.io/coder/coder:latest`): Cloud development workspace platform at `https://coder.vrg.rocks` (port `7080`) with zero-click Tinyauth OIDC (`CODER_OIDC_ALLOW_SIGNUPS=false`), `group_add: ["0"]` for OrbStack Docker socket access, and the active `sol-workspace` Terraform template in [`coder/main.tf`](coder/main.tf). See [`coder/README.md`](coder/README.md).
- **[PocketBase](https://pocketbase.io/)** (`ghcr.io/muchobien/pocketbase:latest`): Single-binary Go + SQLite backend sandbox (`pb.vrg.rocks`, port `8090`, redirecting `/` to `/_/`) with real-time subscriptions, auth, and `logs.minLevel=4`.

### 8. Storage, Aviation & Utilities ([`compose/utilities.yml`](compose/utilities.yml))

- **[Copyparty](https://github.com/9001/copyparty):** High-speed file server and WebDAV (`files.vrg.rocks`, `copyparty.vrg.rocks`, port `3923`) for `data/copyparty`, `data/media`, `data/torrents`, and `/Volumes/PANOPTICON` with trusted-header SSO (`--idp-h-usr Remote-Email`) and `noidx` filters excluding `.Spotlight-V100` and Restic backup packs.
- **[Homebox](https://github.com/sysadminsmedia/homebox):** Physical asset and home inventory manager (`inv.vrg.rocks`, port `7745`) with zero-click Tinyauth OIDC (`HBOX_OIDC_AUTO_REDIRECT=true`) and CORS integration for `scan.vrg.rocks`.
- **[Backrest](https://github.com/garethgeorge/backrest)** (`ghcr.io/garethgeorge/backrest:latest`): Single-binary Go WebUI and scheduler for encrypted, deduplicated Restic backups on port `9898` (`backrest.vrg.rocks`) to `/Volumes/PANOPTICON/backups/sol-restic` and `rclone:OneDrive:Sol-Restic`.
- **[Enclosed](https://github.com/CorentinTh/enclosed)** (`ghcr.io/corentinth/enclosed:latest`): Zero-knowledge client-side encrypted notes and self-destructing file drops (`send.vrg.rocks`, port `8787`, with note creation gated behind Tinyauth and recipient view links public).
- **[AirTrail](https://github.com/johanohly/AirTrail)** (`johly/airtrail:latest`): Personal flight log and aircraft registry built with SvelteKit (`fly.vrg.rocks`, port `3000`, sharing `paperless-db` PostgreSQL 17 with zero-click Tinyauth OIDC).
- **[ntfy](https://ntfy.sh/):** Pub/sub push notifications (`ntfy.vrg.rocks`, port `80`) with open mobile subscriptions and Tinyauth forward-auth on unauthenticated external `POST`/`PUT` publishes.
- *Standby / Ops:* Vaultwarden (`standby`), n8n (`standby`), Home Assistant (`standby`), Rclone (`ops`).

---

## Active and Standby Services

| Set | Count | Services |
| :--- | :--- | :--- |
| Active Containers | 29 | `caddy`, `tinyauth`, `lldap`, `arcane`, `glance`, `jellyfin`, `seerr`, `radarr`, `sonarr`, `bazarr`, `lidarr`, `prowlarr`, `byparr`, `qbittorrent`, `qui`, `paperless-webserver`, `paperless-broker`, `paperless-db`, `ignis`, `readeck`, `code-server`, `coder`, `pocketbase`, `copyparty`, `homebox`, `backrest`, `enclosed`, `airtrail`, `ntfy` |
| Standby / Ops Containers | 16 | `gatus`, `dozzle`, `beszel`, `beszel-agent`, `recyclarr`, `wizarr`, `unpackerr`, `paperless-gotenberg`, `paperless-tika`, `paperless-ai`, `leafwiki`, `kavita`, `vaultwarden`, `n8n`, `homeassistant`, `rclone` (`ops`) |
| Static Web Apps | 10 | `mind.vrg.rocks` (Quartz), `fam.vrg.rocks` (Family Vault), `scan.vrg.rocks` (Homebox Scanner PWA), `aysynbm.vrg.rocks` (Bookmark Utility), `tools.vrg.rocks` (IT-Tools), `chef.vrg.rocks` (CyberChef), `pdf.vrg.rocks` (BentoPDF WASM), `speed.vrg.rocks` (OpenSpeedTest), `draw.vrg.rocks` (Excalidraw), `mi.vrg.rocks` (MediaInfo Web WASM) |
| Standby Native App | 1 | `jellyfin-metal` (macOS Apple VideoToolbox on port `8097`) |

Each standby web service has a matching commented vhost in the [`Caddyfile`](Caddyfile) under a `--- Standby ... Routes ---` header. To bring one online:

1. Start it: `docker compose --profile standby up -d <service>`.
2. Uncomment its vhost block in `Caddyfile`.
3. Recreate Caddy so the updated file is loaded: `docker compose up -d --force-recreate caddy`.
4. Change its `status` in [`ports.json`](ports.json) to `active`.

---

## Storage, Hardlinks, and ExFAT Symlinks

### 1. Internal APFS SSD (`/Users/vrg/Documents/Sol/data` -> `/data`)

`${DOCKER_DATA_DIR}` (`/Users/vrg/Documents/Sol/data`) is mounted at `/data` in Radarr, Sonarr, Lidarr, Bazarr, qBittorrent, QUI, and Unpackerr:

- Downloads: `/data/torrents/{movies,tv,music,books,cross-seed-links,qui-links}`
- Media library: `/data/media/{movies,tv,music,books,preshows,home-videos}`

Both paths sit on one bind mount on the same APFS volume, so an import or cross-seed on internal storage is an instant POSIX hardlink (`link(2)`) with zero extra disk usage.

### 2. External 2 TB ExFAT Drive (`/Volumes/PANOPTICON` -> `/external`)

ExFAT does not support POSIX hardlinks (`Errno 45: Operation not supported`). To prevent Radarr and Sonarr from falling back to multi-gigabyte physical file copies across `/Volumes/PANOPTICON`:

- Built-in `Completed Download Handling` is disabled in Radarr and Sonarr (`enableCompletedDownloadHandling = false`).
- When a torrent finishes in qBittorrent, the `AutoRun` hook [`scripts/torrent_finished.py`](scripts/torrent_finished.py) (paired with [`scripts/arr_symlink_dedupe.sh`](scripts/arr_symlink_dedupe.sh)) creates **per-file relative symlinks** inside real directories under `/external/media/{movies,tv}` pointing to `/external/torrents/{movies,tv}`, cleans up macOS `._*` AppleDouble files, and triggers Radarr, Sonarr, and Jellyfin library refreshes.
- Replaced or upgraded files are routed to `/external/media/.recycle` (`14`-day retention), and `realpath` equality guards prevent symlink replacements from deleting underlying torrent payloads. See [`docs/STORAGE_RESTRUCTURING_AND_VERIFICATION_HISTORY.md`](docs/STORAGE_RESTRUCTURING_AND_VERIFICATION_HISTORY.md).

---

## Repository Structure

```text
/Users/vrg/Documents/Sol/
├── .env.example                          # Master environment template (placeholders, tag pins)
├── .gitignore                            # Ignores secrets, runtime DBs, media, and local archives
├── Caddyfile                             # Caddy v2 routes, (forward_auth), (static_site), standby vhosts
├── ports.json                            # Canonical port, route, status, and profile registry (46 entries)
├── docker-compose.yml                    # Root Compose orchestrator ('name: sol', 'include:')
├── Sol.code-workspace                    # VS Code workspace settings
├── README.md                             # Primary architecture and operations guide
├── TODO.md                               # Roadmap and completed engineering milestones
├── sol.svg                               # Custom Sol vector branding logo
│
├── compose/                              # 8 modular domain Compose stacks (29 active + 16 standby/ops)
│   ├── core.yml                          # Caddy, Tinyauth v5, LLDAP, Arcane
│   ├── monitoring.yml                    # Glance | standby: Gatus, Dozzle, Beszel, Beszel Agent
│   ├── media.yml                         # Jellyfin, Seerr, *arr, Prowlarr, Byparr | standby: Recyclarr, Wizarr
│   ├── download.yml                      # qBittorrent, QUI | standby: Unpackerr
│   ├── paperless.yml                     # Paperless-ngx, Redis 8, PostgreSQL 17 Alpine | standby: Gotenberg, Tika, AI
│   ├── knowledge.yml                     # Ignis, Readeck | standby: LeafWiki, Kavita
│   ├── coding.yml                        # code-server, Coder, PocketBase
│   └── utilities.yml                     # Copyparty, Homebox, Backrest, Enclosed, AirTrail, ntfy | standby: Vaultwarden, n8n, HA | ops: Rclone
│
├── config/
│   ├── auth/
│   │   └── users.json.example            # Tracked single-email identity schema template
│   ├── backrest/
│   │   ├── config.json.example           # Tracked Backrest repositories, schedules, and plans template
│   │   └── excludes.txt.example          # Tracked Restic exclude filter template
│   ├── glance/
│   │   ├── assets/
│   │   │   ├── sol.svg                   # Tracked Glance favicon and logo
│   │   │   └── user.css                  # Tracked Catppuccin Mocha / GM3 stylesheet
│   │   └── config/
│   │       └── glance.yml                # Tracked 3-page declarative Glance dashboard
│   ├── qui/
│   │   └── tracker_registry.json         # Tracked registry of 26 short tracker tags, names, URLs, and announce domains
│   └── rclone/
│       └── filter.txt.example            # Tracked rclone filter template
│
├── scripts/                              # Operational and automation scripts
│   ├── allowlist_user.sh                 # CLI wrapper for user allowlisting & identity sync
│   ├── arr_symlink_dedupe.sh             # Radarr/Sonarr custom script converting physical copies into relative symlinks
│   ├── backup.sh                         # Staging + encrypted Restic snapshots to PANOPTICON and OneDrive
│   ├── identity_sync.py                  # <50ms immutable SQLite SHA-256 reconciler across LLDAP, Tinyauth, OIDC, Jellyfin, Seerr, Copyparty
│   ├── restore.sh                        # Full Mac reset recovery: Restic pull, DB restore, symlink rebuild, Coder volume & LaunchAgent setup
│   ├── setup_jellyfin_metal.py           # Native macOS Jellyfin launcher (--reset re-runs setup wizard)
│   ├── stage_db_backups.sh               # Pre-backup hook: pg_dump, 29 WAL-safe SQLite snapshots, TCC-free symlink manifest, Coder tar
│   ├── sync_static_tools.sh              # Builder/updater for the 6 Wave 1 static web tools (tools, chef, pdf, speed, draw, mi)
│   ├── torrent_finished.py               # qBittorrent AutoRun Option A relative symlink & API refresh hook
│   ├── launchd/
│   │   ├── com.vrg.sol.db-stage.plist    # Nightly 03:00 IST pre-backup staging LaunchAgent (TCC-safe via Homebrew Python)
│   │   └── com.vrg.sol.identity-sync.plist # WatchPaths + 300s LLDAP identity sync LaunchAgent
│   └── archive/
│       ├── merge_overseerr_history.py    # Completed May/June 2025 Overseerr -> Seerr history migration script
│       ├── migrate_panopticon_live.py    # Completed Bencode .fastresume path rewriter for PANOPTICON
│       └── test_cross_seed.sh            # Legacy Cross-Seed hardlink diagnostic script
│
├── coder/                                # Coder Docker workspace template ('sol-workspace')
│   ├── main.tf                           # Terraform template (prebuilt jj v0.28.2, Bun, /home/coder volume)
│   └── README.md                         # Template architecture and 'coder templates push' guide
│
├── docs/
│   ├── SERVER_HISTORY_AND_EVOLUTION.md   # Complete 2018-2026 4-Era archaeological history & legacy Authentik blueprint
│   ├── STORAGE_RESTRUCTURING_AND_VERIFICATION_HISTORY.md # PANOPTICON restructuring, Option A symlinks, and Restic DR
│   ├── archive/
│   │   └── FLASH_LOCAL_VERIFICATION_RUNBOOK.md # Archived October 18, 2026 live verification playbook
│   └── system_state/                     # Living system state architecture reference (00 to 11)
│
│   # --- Runtime data (ignored by git, backed up via Backrest + Restic) ---
├── .env                                  # Live credentials and secrets
├── config/*                              # App configs and SQLite databases (incl. config/auth/users.json)
├── data/                                 # Media, PostgreSQL clusters, torrents, staged backups
├── web/                                  # 9 static web apps (fam, scan, aysynbm, tools, chef, pdf, speed, draw, mi)
├── quartz/                               # Quettamind digital garden source and public/ build (/mind)
└── logs/                                 # Runtime and LaunchAgent logs
```

---

## Port and Ingress Matrix

Active routes and services below match [`Caddyfile`](Caddyfile) and [`ports.json`](ports.json). Standby routes are commented in `Caddyfile`.

| Host Port | Service | Internal Port | Protocol | Route / FQDN | Auth Mechanism | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`80`** | `caddy` | `80` | TCP | `*.vrg.rocks` | HTTP to HTTPS redirect | **Active (Edge)** |
| **`443`** | `caddy` | `443` | TCP/UDP | `*.vrg.rocks` | Edge TLS / HTTP/3 | **Active (Edge)** |
| **`42069`** | `qbittorrent` | `42069` | TCP/UDP | *(BitTorrent peer wire)* | None (WAN torrenting) | **Active** |
| *Bridge only* | `tinyauth` | `3000` | TCP | `auth.vrg.rocks` (`login.`, `tinyauth.` 301) | Tinyauth 0-click Google OAuth & OIDC | **Active** |
| *Bridge only* | `lldap` | `3890`, `17170` | LDAP, HTTP | `ldap.vrg.rocks` | Tinyauth forward auth (Admin ACL) + LLDAP login | **Active** |
| *Bridge only* | `arcane` | `3552` | TCP | `arcane.vrg.rocks` | Native Tinyauth OIDC (0-click, Admin consent) | **Active** |
| *External LAN* | Physical router | `80` | TCP | `router.vrg.rocks` (`http://192.168.50.1`) | Tinyauth forward auth (Admin ACL) | **Active** |
| *Bridge only* | `glance` | `8080` | TCP | `dash.vrg.rocks` (`sol.vrg.rocks` 302 to `/sol`) | Tinyauth forward auth | **Active** |
| *Bridge only* | `jellyfin` | `8096` | TCP | `watch.vrg.rocks`, `jellyfin.vrg.rocks` | Jellyfin native + `LDAP-Auth` (`lldap`) + `SSO-Auth` (Tinyauth OIDC) | **Active** |
| *Bridge only* | `seerr` | `5055` | TCP | `request.vrg.rocks`, `seerr.vrg.rocks`, `jellyseerr.vrg.rocks` | Tinyauth forward auth + Jellyfin/LDAP & Quick Connect | **Active** |
| *Bridge only* | `radarr` | `7878` | TCP | `radarr.vrg.rocks` | Tinyauth forward auth (Admin ACL, External auth) | **Active** |
| *Bridge only* | `sonarr` | `8989` | TCP | `sonarr.vrg.rocks` | Tinyauth forward auth (Admin ACL, External auth) | **Active** |
| *Bridge only* | `bazarr` | `6767` | TCP | `bazarr.vrg.rocks` | Tinyauth forward auth (Admin ACL, External auth) | **Active** |
| *Bridge only* | `lidarr` | `8686` | TCP | `lidarr.vrg.rocks` | Tinyauth forward auth (Admin ACL, External auth) | **Active** |
| *Bridge only* | `prowlarr` | `9696` | TCP | `prowlarr.vrg.rocks` | Tinyauth forward auth (Admin ACL, External auth) | **Active** |
| *Bridge only* | `byparr` | `8191` | TCP | `byparr.vrg.rocks` (`flaresolverr.vrg.rocks` 301) | Tinyauth forward auth (Admin ACL) | **Active** |
| *Bridge only* | `qbittorrent` | `8080` | TCP | `qb.vrg.rocks`, `qbittorrent.vrg.rocks` | qBittorrent native auth (for mobile client compatibility) | **Active** |
| *Bridge only* | `qui` | `7476` | TCP | `qui.vrg.rocks` | Tinyauth forward auth (Admin ACL, `QUI__AUTH_DISABLED=true`) | **Active** |
| *Bridge only* | `paperless-webserver` | `8000` | TCP | `docs.vrg.rocks`, `paperless.vrg.rocks` | Native Tinyauth OIDC (0-click `REDIRECT_LOGIN_TO_SSO`) | **Active** |
| *Bridge only* | `paperless-broker` | `6379` | TCP | `paperless-broker:6379` | Internal bridge only | **Active** |
| *Bridge only* | `paperless-db` | `5432` | TCP | `paperless-db:5432` | PostgreSQL password (`paperless` & `airtrail` DBs) | **Active** |
| *Bridge only* | `ignis` | `8080` | TCP | `ignis.vrg.rocks` (`notes.vrg.rocks` 301) | Tinyauth forward auth (Admin ACL) | **Active** |
| *Bridge only* | `readeck` | `8000` | TCP | `links.vrg.rocks` | Native Tinyauth OIDC + Bearer API tokens | **Active** |
| *Bridge only* | `code-server` | `8443` | TCP | `code.vrg.rocks` | Tinyauth forward auth (Admin ACL, `AUTH=none`) | **Active** |
| *Bridge only* | `coder` | `7080` | TCP | `coder.vrg.rocks` | Native Tinyauth OIDC (0-click `/login` redirect, Admin consent) | **Active** |
| *Bridge only* | `pocketbase` | `8090` | TCP | `pb.vrg.rocks` (`/` 302 to `/_/`) | Tinyauth forward auth (Admin ACL) + PB superuser | **Active** |
| *Bridge only* | `copyparty` | `3923` | TCP | `files.vrg.rocks`, `copyparty.vrg.rocks` | Tinyauth forward auth + `Remote-Email` trusted header | **Active** |
| *Bridge only* | `ntfy` | `80` | TCP | `ntfy.vrg.rocks` | Open subscriptions, unauthenticated `POST`/`PUT` gated by Tinyauth | **Active** |
| *Bridge only* | `homebox` | `7745` | TCP | `inv.vrg.rocks` | Native Tinyauth OIDC (0-click `HBOX_OIDC_AUTO_REDIRECT=true`) | **Active** |
| *Bridge only* | `backrest` | `9898` | TCP | `backrest.vrg.rocks` | Tinyauth forward auth (Admin ACL, `auth.disabled=true`) | **Active** |
| *Bridge only* | `enclosed` | `8787` | TCP | `send.vrg.rocks` | Note creation (`/`, `/api/notes`) gated by Tinyauth, view links (`/@*`) public E2EE | **Active** |
| *Bridge only* | `airtrail` | `3000` | TCP | `fly.vrg.rocks` | Native Tinyauth OIDC (0-click `OAUTH_AUTO_LOGIN=true`) | **Active** |
| *Static* | `caddy` (`/mind`) | n/a | HTTPS | `mind.vrg.rocks` | Tinyauth forward auth (Admin ACL) | **Active** |
| *Static* | `caddy` (`/fam`) | n/a | HTTPS | `fam.vrg.rocks` | Tinyauth forward auth + AES-GCM client vault password | **Active** |
| *Static* | `caddy` (`/scan`) | n/a | HTTPS | `scan.vrg.rocks` | Tinyauth forward auth (Admin ACL) | **Active** |
| *Static* | `caddy` (`/aysynbm`) | n/a | HTTPS | `aysynbm.vrg.rocks` | Tinyauth forward auth (Admin ACL) | **Active** |
| *Static* | `caddy` (`/tools`) | n/a | HTTPS | `tools.vrg.rocks` | Tinyauth forward auth | **Active** |
| *Static* | `caddy` (`/chef`) | n/a | HTTPS | `chef.vrg.rocks` | Tinyauth forward auth | **Active** |
| *Static* | `caddy` (`/pdf`) | n/a | HTTPS | `pdf.vrg.rocks` | Tinyauth forward auth | **Active** |
| *Static* | `caddy` (`/speed`) | n/a | HTTPS | `speed.vrg.rocks` | Tinyauth forward auth | **Active** |
| *Static* | `caddy` (`/draw`) | n/a | HTTPS | `draw.vrg.rocks` | Tinyauth forward auth | **Active** |
| *Static* | `caddy` (`/mi`) | n/a | HTTPS | `mi.vrg.rocks` | Tinyauth forward auth | **Active** |
| **`8097`** | `jellyfin-metal` | `8097` | TCP | `metal.vrg.rocks` *(commented)* | Jellyfin native | **Standby (Native)** |

---

## Operational Commands

Run every command from `/Users/vrg/Documents/Sol`. Compose reads `.env` from the project directory.

### Docker Lifecycle

```bash
# Start all 29 active services
docker compose up -d

# Verify all 29 containers are Up and (healthy)
docker compose ps

# Validate the full Compose model (all 45 service definitions)
docker compose config -q

# Count services that start by default (expect 29)
docker compose config --services | wc -l

# Count all services including standby and ops profiles (expect 45)
docker compose --profile standby --profile ops config --services | wc -l

# Stop all containers
docker compose down
```

### Standby and Ops Profiles

```bash
# Start one standby service (example: wizarr or gatus)
docker compose --profile standby up -d wizarr

# Stop it again
docker compose stop wizarr

# One-off rclone command through the ops profile (example: list remotes)
docker compose --profile ops run --rm rclone listremotes

# OAuth re-authorization for OneDrive (callback on 127.0.0.1:53682)
docker compose --profile ops run --rm --service-ports rclone config reconnect OneDrive:
```

### Service and Stack Operations

```bash
# Restart a group of services (use service names, not -f compose/<file>.yml)
docker compose restart jellyfin seerr radarr sonarr bazarr lidarr prowlarr byparr

# Recreate one service after a compose or .env change
docker compose up -d --force-recreate radarr

# Validate and reload Caddy after a Caddyfile edit
docker exec -i caddy caddy validate --config - --adapter caddyfile < Caddyfile
docker compose up -d --force-recreate caddy
```

Do not run `docker compose -f compose/media.yml ...`. That makes `compose/` the project directory, so Compose does not find the root `.env` and every `${DOCKER_*}` path resolves to empty.

### Identity Sync & LaunchAgents

```bash
# Check status of both macOS LaunchAgents (expect exit status 0)
launchctl list | grep com.vrg.sol

# Manually run the LLDAP -> users.json -> downstream apps reconciler (<50ms when unchanged)
./scripts/allowlist_user.sh sync --apply

# Force full reconciliation across Tinyauth, OIDC consents, Jellyfin, Seerr, Readeck, AirTrail, and Copyparty
python3 scripts/identity_sync.py --apply --force
```

### Pulling Updates

```bash
docker compose pull
docker compose up -d
```

Image tags for pinned services can be overridden in `.env` (`CADDY_TAG`, `TINYAUTH_TAG`, `LLDAP_TAG`, `ARCANE_TAG`, `PAPERLESS_TAG`, `READECK_TAG`).

### Native Jellyfin Metal (macOS Hardware Transcoding, Standby)

```bash
# Launch (keeps config/jellyfin_metal/data/data/jellyfin.db, users, and watch history)
python3 scripts/setup_jellyfin_metal.py

# Wipe config/jellyfin_metal and re-run the first-time setup wizard (destructive)
python3 scripts/setup_jellyfin_metal.py --reset

# Stop
killall jellyfin
```

---

## Backup and Disaster Recovery

### Two-Tier Backup Architecture

Sol uses a two-tier backup architecture for zero-PII version control and deterministic bare-metal state recovery:

1. **Tier 1: Full Server State Backup (Backrest + Restic to `/Volumes/PANOPTICON` and `OneDrive`):**
   - Managed via **Backrest (`https://backrest.vrg.rocks`)** and [`scripts/backup.sh`](scripts/backup.sh), paired with the nightly pre-backup staging hook [`scripts/stage_db_backups.sh`](scripts/stage_db_backups.sh) (scheduled via macOS `launchd` [`scripts/launchd/com.vrg.sol.db-stage.plist`](scripts/launchd/com.vrg.sol.db-stage.plist) at `03:00 IST`).
   - Backs up the entire `/Users/vrg/Documents/Sol` directory **except** bulk media files (`data/media/{movies,tv,music,books,home-videos}`), raw torrent downloads (`data/torrents/{movies,tv,books,music,temp,incomplete}`), live database binary clusters (which are dumped cleanly into `data/backups/*.sql.gz` and `data/backups/sqlite/*`), logs, and regenerable caches/bundles ([`config/backrest/excludes.txt.example`](config/backrest/excludes.txt.example)).
   - **Recovery Guarantee:** After a complete Mac wipe and reset, restoring the Restic snapshot (`./scripts/restore.sh --restore-dbs --start-stack`) with media files in their respective folders brings **100% of the server, databases, secrets (`.env`), `.torrent`/`.fastresume` state, Paperless documents, Obsidian vaults, static web apps (`web/fam`), Coder workspace volume, LaunchAgents, and media symlink trees** back up and running identically to the time of backup.
2. **Tier 2: Declarative Infrastructure Blueprint (`GitHub` `varungupta3009/Sol`):**
   - Tracks a zero-secret infrastructure-as-code blueprint (`docker-compose.yml`, `compose/*.yml`, `Caddyfile`, `ports.json`, `.env.example`, `config/glance/**`, `config/qui/tracker_registry.json`, `config/auth/users.json.example`, `config/backrest/*.example`, `config/rclone/filter.txt.example`, `coder/main.tf`, `scripts/**`, and `docs/**`).

### Running Backups ([`scripts/backup.sh`](scripts/backup.sh), [`scripts/stage_db_backups.sh`](scripts/stage_db_backups.sh) & `https://backrest.vrg.rocks`)

```bash
# Run full staged backup to both PANOPTICON and OneDrive (Restic via Backrest)
./scripts/backup.sh

# Run local-only Restic snapshot to /Volumes/PANOPTICON/backups/sol-restic
./scripts/backup.sh --local-only

# Run pre-backup database & symlink staging independently
./scripts/stage_db_backups.sh
```

Pipeline:

1. **Pre-Backup Staging ([`scripts/stage_db_backups.sh`](scripts/stage_db_backups.sh)):**
   - Dumps `paperless-db` (`paperless` and `airtrail` databases) and `coder` (embedded PostgreSQL, with PG 17 `SET transaction_timeout` stripped for PG 16 compatibility) with `pg_dump` to `data/backups/{paperless_db,airtrail_db,coder_db}.sql.gz`.
   - Wipes `data/backups/sqlite/*`, copies each active and standby SQLite database (`29` databases, skipping ephemeral `logs.db`, `cache.db`, `auxiliary.db`, `up2k.db`, and `MediaCover*`) and its `-wal` file (without `-shm`) to a local temp directory, runs `sqlite3 .backup`, sets `PRAGMA journal_mode=DELETE;`, and removes `-wal`/`-shm` sidecars.
   - Runs an ephemeral `redis:8-alpine` container through OrbStack VirtioFS to scan and export all relative media and cross-seed symlinks in `data/media`, `data/torrents/{cross-seed-links,qui-links}`, and `/Volumes/PANOPTICON/{media,torrents}` to `data/backups/symlinks_manifest.tsv` in ~12 seconds without triggering macOS removable-volume TCC prompts.
   - Records the active Coder workspace volume name in `data/backups/coder_volume_name.txt` and archives `/home/coder` to `data/backups/coder_home.tar.gz`.
2. **Restic Deduplicated Snapshot (Backrest Plans `sol-local-daily` at `03:30 IST` & `sol-onedrive-cloud` at `04:00 IST`, or [`scripts/backup.sh`](scripts/backup.sh)):**
   - Snapshots `/userdata/sol` into `/repos/local-panopticon` (`/Volumes/PANOPTICON/backups/sol-restic`) and `rclone:OneDrive:Sol-Restic` using [`config/backrest/excludes.txt.example`](config/backrest/excludes.txt.example), retaining `7 daily / 4 weekly / 6 monthly` snapshots with weekly prune and integrity checks.

### Restoring on a Fresh Machine ([`scripts/restore.sh`](scripts/restore.sh))

```bash
# 1. Clone the repository
git clone https://github.com/varungupta3009/Sol.git /Users/vrg/Documents/Sol && cd /Users/vrg/Documents/Sol

# 2. Preview available Restic snapshots (no changes)
./scripts/restore.sh --dry-run

# 3. Restore latest snapshot from PANOPTICON (or --from-cloud for OneDrive), rebuild DBs, symlinks, Coder volume, LaunchAgents, and start stack
./scripts/restore.sh --restore-dbs --start-stack
```

| Flag | Effect |
| :--- | :--- |
| `--dry-run` | Lists Restic snapshots and previews the restore plan without mutating files (`docker run --entrypoint restic` works before `.env` exists on disk). |
| `--from-cloud` | Pulls the Restic snapshot from `rclone:OneDrive:Sol-Restic` instead of local `/Volumes/PANOPTICON/backups/sol-restic`. |
| `--skip-cloud-pull` | Uses already-extracted local files under `data/backups/` without running `restic restore`. |
| `--restore-dbs` | Imports PostgreSQL `.sql.gz` dumps (`paperless_db.sql.gz` and `airtrail_db.sql.gz` with `vacuumdb --all --analyze-only`, plus `coder_db.sql.gz`), restores all 29 SQLite snapshots, and restores `coder_home.tar.gz` into the named volume from `coder_volume_name.txt`. |
| `--start-stack` | Recreates media symlinks from `symlinks_manifest.tsv`, runs `scripts/sync_static_tools.sh`, installs `scripts/launchd/com.vrg.sol.*.plist` into `~/Library/LaunchAgents/`, and starts all 29 active containers. |

---

## Secrets and Security

- **Environment:** All passwords, tokens, API keys, and host paths live in `.env`, which git ignores. [`.env.example`](.env.example) is the tracked template. Values with spaces or JSON are quoted so that both Compose and bash parse them.
- **Forward auth & OIDC:** Caddy verifies sessions at `tinyauth:3000/api/auth/caddy` before routing to protected web UIs and static apps, and wraps static file serving in `route { ... }` inside `(static_site)` so `forward_auth` always executes before `try_files`. Seven apps (`paperless-ngx`, `arcane`, `homebox`, `airtrail`, `coder`, `readeck`, `jellyfin`) use Tinyauth's built-in OIDC provider, with `arcane` and `coder` OIDC consents restricted strictly to admin user `vrg`.
- **Per-app Admin ACLs:** Infrastructure and personal knowledge domains (`code`, `backrest`, `qui`, `radarr`, `sonarr`, `lidarr`, `prowlarr`, `bazarr`, `cs`, `byparr`, `pb`, `router`, `ldap`, `ignis`, `mind`, `scan`, `aysynbm`) enforce `TINYAUTH_APPS_<APP>_OAUTH_WHITELIST=${TINYAUTH_ADMIN_EMAILS:?}` so non-admin users in `friends_and_family` receive `HTTP 403`.
- **Route-specific security controls:**
  - `qb.vrg.rocks` uses qBittorrent native auth for Android mobile client compatibility.
  - `ntfy.vrg.rocks` allows mobile push subscriptions directly while gating unauthenticated external `POST`/`PUT` requests (`not header Authorization *`) behind Tinyauth forward-auth.
  - `send.vrg.rocks` (`enclosed`) gates note creation (`/`, `/api/notes`) behind Tinyauth forward-auth while keeping recipient view links (`/@*`) public for client-side E2EE decryption.
  - `inv.vrg.rocks` (`homebox`) restricts CORS `Access-Control-Allow-Origin` to `https://scan.vrg.rocks`.

---

## Documentation Index

| Document | Content |
| :--- | :--- |
| [`docs/SERVER_HISTORY_AND_EVOLUTION.md`](docs/SERVER_HISTORY_AND_EVOLUTION.md) | Complete 2018 to 2026 4-Era archaeological server history, forensic DB/filesystem ledgers, and legacy Authentik reconstruction blueprint |
| [`docs/STORAGE_RESTRUCTURING_AND_VERIFICATION_HISTORY.md`](docs/STORAGE_RESTRUCTURING_AND_VERIFICATION_HISTORY.md) | `PANOPTICON` ExFAT restructuring, Option A `torrent_finished.py` + `arr_symlink_dedupe.sh` per-file relative symlinks, and 2-Tier Backrest + Restic DR |
| [`docs/system_state/00` to `08`](docs/system_state) | Executive topology, service catalog, storage & volumes, ingress & routing, standby/legacy registry, improvement plan, config taxonomy, media stack deep dive, performance telemetry |
| [`09_ARCHITECTURAL_AUDIT_AND_UPGRADE_PLAN.md`](docs/system_state/09_ARCHITECTURAL_AUDIT_AND_UPGRADE_PLAN.md) | October 17, 2026 `/double-agent` review and five upgrade phases |
| [`10_MEGA_OPTIMIZATION_AND_CONTAINER_ROADMAP.md`](docs/system_state/10_MEGA_OPTIMIZATION_AND_CONTAINER_ROADMAP.md) | Wave 1 to 3 container optimizations, `qui` deployment, and October 20, 2026 31-Agent Swarm Audit summary |
| [`11_AUTHENTICATION_AND_SSO_STRATEGY.md`](docs/system_state/11_AUTHENTICATION_AND_SSO_STRATEGY.md) | Zero-click Google SSO, Tinyauth v5 OIDC & forward-auth architecture, LLDAP + `<50ms` `identity_sync.py` reconciler, and per-app admin ACLs |
| [`docs/archive/FLASH_LOCAL_VERIFICATION_RUNBOOK.md`](docs/archive/FLASH_LOCAL_VERIFICATION_RUNBOOK.md) | Archived October 18, 2026 live host verification playbook |
| [`TODO.md`](TODO.md) | Active roadmap and completed milestone ledger |
| [`coder/README.md`](coder/README.md) | Coder `sol-workspace` Terraform template architecture and operations |
