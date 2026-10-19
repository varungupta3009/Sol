<div align="center">

# ☀️ Sol

**A modular home server on an Apple Silicon M1 Pro Mac.**

[![Host](https://img.shields.io/badge/Host-macOS%20Apple%20Silicon%20(M1%20Pro)-000000?style=for-the-badge&logo=apple&logoColor=white)](#)
[![Docker](https://img.shields.io/badge/Docker-Compose%20V2%20(include%20%2B%20profiles)-2496ED?style=for-the-badge&logo=docker&logoColor=white)](#)
[![Reverse Proxy](https://img.shields.io/badge/Ingress-Caddy%20v2%20(HTTP%2F3%20%2B%20TLS)-1F88C0?style=for-the-badge&logo=caddy&logoColor=white)](#)
[![Identity](https://img.shields.io/badge/Auth-Tinyauth%20v5%20SSO%20%26%20OIDC-10B981?style=for-the-badge)](#)
[![Filesystem](https://img.shields.io/badge/Storage-APFS%20Zero--Copy%20Hardlinks-34D058?style=for-the-badge)](#)
[![Backup](https://img.shields.io/badge/Backup-Backrest%20%2B%20Restic-0078D4?style=for-the-badge)](#)

---

</div>

## Table of Contents

1. [Overview](#overview)
2. [Architecture Topology](#architecture-topology)
3. [Domain Stacks](#domain-stacks)
4. [Active and Standby Services](#active-and-standby-services)
5. [Storage and Hardlinks](#storage-and-hardlinks)
6. [Repository Structure](#repository-structure)
7. [Port and Ingress Matrix](#port-and-ingress-matrix)
8. [Operational Commands](#operational-commands)
9. [Backup and Disaster Recovery](#backup-and-disaster-recovery)
10. [Secrets and Security](#secrets-and-security)
11. [Documentation Index](#documentation-index)

---

## Overview

Sol is a single-node home server on an 8-core Apple Silicon M1 Pro Mac (6 performance and 2 efficiency cores, 16 GB unified memory) running OrbStack. It provides:

- Reverse proxy routing with automatic HTTPS and HTTP/3
- Zero-click Google SSO, native OpenID Connect (OIDC), and email allowlisting through Tinyauth v5 (`~29 MiB` RAM)
- Automated media requests, downloads, and cross-seeding
- Document archiving with OCR
- Browser IDEs and Coder workspaces
- File serving, WebDAV, and push notifications

At a glance:

| Item | Value |
| :--- | :--- |
| Active containers (default `docker compose up -d`) | 29 |
| Profile-gated containers (`standby`, plus `ops` for `rclone`) | 21 (includes `authentik-postgresql`, `authentik-server`, `authentik-worker`, `cross-seed`) |
| Zero-container static web apps (served directly by `caddy`) | 10 (`mind.`, `fam.`, `scan.`, `aysynbm.`, `tools.`, `chef.`, `pdf.`, `speed.`, `draw.`, `mi.vrg.rocks`) |
| Native host processes | 1 (`jellyfin-metal` on port `8097`) |
| Compose project and network | `sol`, `sol_default` |
| Public domain | `*.vrg.rocks` |

### Key Principles

- **Apple Silicon tuning:** Concurrency is set per service. Paperless runs `PAPERLESS_TASK_WORKERS: 2` and `PAPERLESS_THREADS_PER_WORKER: 2`. PostgreSQL 17 (`paperless-db`) uses `shared_buffers=256MB`, `work_mem=16MB`, and `effective_cache_size=1GB`. Caddy uses 32 KB streaming buffers on the Jellyfin routes.
- **Modular Compose:** The root `docker-compose.yml` loads 8 domain files under `compose/` with Compose V2 `include:` and `x-logging` JSON log rotation (`max-size: 10m`, `max-file: 3`). Containers reach each other by name on `sol_default` (for example `http://radarr:7878` or `http://tinyauth:3000`).
- **Profiles, not comments:** Inactive services are full definitions with `profiles: ["standby"]`. `docker compose config` validates all 50, and only the 29 active ones start by default.
- **Zero-copy file moves:** A unified `/data` mount on APFS lets downloads hardlink into the media library with no second copy.
- **Zero-click edge, OIDC & Unified LDAP (`lldap`) identity:** Caddy, Tinyauth v5 (`auth.vrg.rocks`), and `lldap` (`ldap.vrg.rocks`) connect every user's single email across all interfaces (`config/auth/users.json` + `scripts/identity_sync.py`), enforcing zero-click Google OAuth, pre-seeded OIDC consent for 7 native OIDC clients (`paperless-ngx`, `arcane`, `homebox`, `airtrail`, `coder`, `readeck`, `jellyfin`), unified LDAP login (`email`, `alias`, or `username`) for Jellyfin and Seerr, trusted-header / external auth on `copyparty`, `qui`, `code-server`, `backrest`, `radarr`, `sonarr`, `lidarr`, `prowlarr`, and `bazarr`, and per-app admin ACLs (`VRG` only). See [`11_AUTHENTICATION_AND_SSO_STRATEGY.md`](docs/system_state/11_AUTHENTICATION_AND_SSO_STRATEGY.md).
- **State vs configuration:** Version control tracks declarative infrastructure only. Application state is backed up through `scripts/backup.sh` and `backrest` (`backrest.vrg.rocks`) as encrypted, deduplicated Restic snapshots (containing PostgreSQL dumps, WAL-complete SQLite snapshots, media symlink manifests, and Coder workspace archives) to `/Volumes/PANOPTICON/backups/sol-restic` and `rclone:OneDrive:Sol-Restic`.

---

## Architecture Topology

```
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
       +---------------+----------------+---------------------------+
       | forward_auth                   |                           |
       v                                v                           v
+-----------------------------+  +--------------------+  +--------------------------+
| Authentik Server            |  | Glance (dash.)     |  | Static Web Endpoints     |
| :9000/:9443 on 127.0.0.1    |  | behind Authentik   |  |  - /mind (Quartz garden) |
| embedded outpost            |  +--------------------+  |  - /fam  (Family vault)  |
+--------------+--------------+                          |  - /scan (Homebox PWA)   |
               |                                         |  - /aysynbm (Bookmarks)  |
               v                                         +--------------------------+
+-----------------------------+
| PostgreSQL 16 (Auth DB)     |
| Authentik Worker (no socket)|
+-----------------------------+
               |
  +------------+-----------------+------------------------------+
  |                              |                              |
  v                              v                              v
+------------------------+  +------------------------+  +--------------------------+
| Media and Automation   |  | Docs and Knowledge     |  | Workspaces and Storage   |
| - Jellyfin (:8096)     |  | - Paperless (:8000)    |  | - code-server (:8443)    |
| - Jellyfin Metal(:8097)|  | - Redis 8 (:6379)      |  | - Coder (:7080)          |
| - Seerr (:5055)        |  | - PostgreSQL 17 (:5432)|  | - Copyparty (:3923)      |
| - Radarr (:7878)       |  | - Ignis (:8080)        |  | - ntfy (:80)             |
| - Sonarr (:8989)       |  +------------------------+  | - Arcane (:3552)         |
| - Bazarr (:6767)       |                              +--------------------------+
| - Lidarr (:8686)       |
| - Prowlarr (:9696)     |
| - Byparr (:8191)       |
| - qBittorrent (:8080)  |
| - QUI (:7476)          |
| - Cross-Seed (:2468)   |
+------------------------+
```

---

## Domain Stacks

The server is split into 8 compose files in [`compose/`](compose). Standby services in each file start only with `--profile standby`.

### 1. Ingress and Identity ([`compose/core.yml`](compose/core.yml))

- **[Caddy v2](https://caddyserver.com/)** (`caddy:${CADDY_TAG:-2}`): Edge reverse proxy with Let's Encrypt TLS, HTTP/3, `zstd`/`gzip` compression, security headers, provider-agnostic `(forward_auth)` snippet, and static file hosting for 10 zero-container web apps (`/mind`, `/fam`, `/scan`, `/aysynbm`, `/tools`, `/chef`, `/pdf`, `/speed`, `/draw`, `/mi`).
- **[Tinyauth v5](https://tinyauth.app/)** (`ghcr.io/tinyauthapp/tinyauth:${TINYAUTH_TAG:-v5}`): Primary forward-auth and OpenID Connect (OIDC) provider (`auth.vrg.rocks`, `~29 MiB` RAM) with silent zero-click Google OAuth (`TINYAUTH_OAUTH_AUTOREDIRECT=google`), strict email allowlisting (`config/auth/users.json` -> `data/tinyauth/whitelist.txt` managed via [`scripts/allowlist_user.sh`](scripts/allowlist_user.sh)), 7 built-in OIDC clients (`paperless-ngx`, `arcane`, `homebox`, `airtrail`, `coder`, `readeck`, `jellyfin`), and per-app admin ACLs (`VRG` only).
- **[lldap](https://github.com/lldap/lldap)** (`lldap/lldap:${LLDAP_TAG:-stable}`): Lightweight Rust + SQLite LDAP directory (`ldap://lldap:3890` and `https://ldap.vrg.rocks`, `~12 MiB` RAM) synchronizing `config/auth/users.json` via [`scripts/identity_sync.py`](scripts/identity_sync.py) so Jellyfin (`LDAP-Auth` + `SSO-Auth`) and Seerr authenticate users seamlessly by primary email, email alias, or username.
- **[Arcane](https://github.com/getarcaneapp/arcane)** (`arcane:${ARCANE_TAG:-latest}`): Docker stack manager with zero-click Tinyauth OIDC (`OIDC_AUTO_REDIRECT_TO_PROVIDER: "true"`), SQLite in WAL mode, and `LOG_LEVEL: info`.
- *Standby:* Authentik (`authentik-server`, `authentik-worker`, `authentik-postgresql` preserved intact in `profiles: ["standby"]`).

### 2. Monitoring and Dashboards ([`compose/monitoring.yml`](compose/monitoring.yml))

- **[Glance](https://github.com/glanceapp/glance):** Declarative 3-page command center ([`config/glance/config/glance.yml`](config/glance/config/glance.yml)) with `Sol` (`/sol`), `Stats & Ops` (`/stats`), and `Radar` (`/radar`), custom Catppuccin Mocha / GM3 theme presets ([`config/glance/assets/user.css`](config/glance/assets/user.css)), internal Docker bridge health monitors across 25 services, `custom-api` telemetry for Jellyfin, Seerr, Radarr, Sonarr, Prowlarr, and Paperless-ngx, live Docker socket container status, and `/media/panopticon` 2TB ExFAT drive telemetry (`dash.vrg.rocks`, `sol.vrg.rocks`).
- *Standby:* Gatus, Dozzle, Beszel, Beszel Agent.

### 3. Media and Servarr ([`compose/media.yml`](compose/media.yml))

- **[Jellyfin](https://jellyfin.org/) (container):** Main streaming server (`watch.vrg.rocks`, `jellyfin.vrg.rocks`, port `8096`).
- **Jellyfin Metal (native macOS):** Host process with Apple VideoToolbox hardware transcoding and HDR tone mapping (`metal.vrg.rocks`, port `8097`). Managed by [`scripts/setup_jellyfin_metal.py`](scripts/setup_jellyfin_metal.py).
- **[Seerr](https://github.com/seerr-team/seerr):** Request and discovery portal (`request.vrg.rocks`). Keeps the network alias `jellyseerr`.
- **[Radarr](https://radarr.video/), [Sonarr](https://sonarr.tv/), [Lidarr](https://lidarr.audio/), [Bazarr](https://www.bazarr.media/):** Movie, TV, music, and subtitle managers on the unified `/data` and `/external` mounts with `/external/media/.recycle` 14-day recycle bin protection.
- **[Prowlarr](https://prowlarr.com/):** Indexer manager.
- **[Byparr](https://github.com/ThePhaseless/Byparr)** (`ghcr.io/thephaseless/byparr:latest`): Cloudflare Turnstile solver on port `8191`. It holds the network alias `flaresolverr`, so Prowlarr's proxy URL `http://flaresolverr:8191` is unchanged.
- *Standby:* FlareSolverr (legacy solver), Recyclarr, Wizarr.

### 4. Downloads and Cross-Seeding ([`compose/download.yml`](compose/download.yml))

- **[qBittorrent](https://www.qbittorrent.org/):** Torrent client with WAN peer port `42069` TCP/UDP and the WebUI on `8080`, paired with the hardened `config/qbittorrent/scripts/torrent_finished.py` Option A completion hook.
- **[QUI](https://github.com/autobrr/qui)** (`ghcr.io/autobrr/qui:v1.32.0`): Single-binary Go WebUI, Cross-Seed engine, and tracker automation manager for qBittorrent on port `7476` (`qui.vrg.rocks`, `~24 MiB` RAM). Replaces both `cross-seed` and `qbit_manage` with 25 tracker customizations ([`config/qui/tracker_registry.json`](config/qui/tracker_registry.json)), 10 FUP/health automation rules (stopping public torrents at `ratio >= 1.0` or immediately on completion if `size > 25 GiB` unless tagged `INF`, capping private torrents at `100 GiB` uploaded, and enforcing tiered upload speed limits), Prowlarr Torznab cross-seeding, Radarr/Sonarr integration, library scan, and orphan scan.
- Both mount `${DOCKER_DATA_DIR}:/data` and `${EXTERNAL_DRIVE_00}:/external` (the legacy `/downloads` mount has been retired after migrating all 289 `.fastresume` files to `/data/torrents` and `/external/torrents`).
- *Standby:* Cross-Seed (`cross-seed:6`), Unpackerr.

### 5. Document Management and OCR ([`compose/paperless.yml`](compose/paperless.yml))

- **[Paperless-ngx](https://docs.paperless-ngx.com/)** (`paperless-ngx:${PAPERLESS_TAG:-3.3}`): Document archive with OCR (`eng`, plus `hin kan pan`) and Authentik OIDC.
- **Redis broker:** `redis:8-alpine`.
- **PostgreSQL 17:** `postgres:17-alpine` (migrated via `pg_dump` and `pg_restore` in October 2026; also hosts the `airtrail` database).
- **Pre-consumption hook (`pre-consumption.py`):** Uses `pikepdf` to decrypt statement PDFs and extract embedded attachments.
- **Push notifications (`ntfy_notify.sh`):** Sends an ntfy alert when a document finishes processing.
- *Standby:* Gotenberg, Apache Tika, Paperless-AI.

### 6. Knowledge and Bookmarks ([`compose/knowledge.yml`](compose/knowledge.yml))

- **[Ignis](https://github.com/nobbe/ignis):** Obsidian vault sync (`ignis.vrg.rocks`).
- **[Readeck](https://codeberg.org/readeck/readeck)** (`codeberg.org/readeck/readeck:${READECK_TAG:-latest}`): Single-binary Go + SQLite bookmark and read-later article archiver (`links.vrg.rocks`, port `8000`) with full-text reader mode, highlights, and EPUB export.
- *Standby:* LeafWiki, Kavita.

### 7. Developer Workspaces & Backend Sandboxes ([`compose/coding.yml`](compose/coding.yml))

- **[code-server](https://github.com/coder/code-server):** Browser VS Code with the Sol repo at `/Server` and `/Users/vrg/Documents` at `/Documents`. Gated by Authentik and the code-server password.
- **[Coder](https://coder.com/)** (`coder:${CODER_TAG:-latest}`): Workspace platform at `https://coder.vrg.rocks`. The Docker template lives in [`coder/main.tf`](coder/main.tf). See [coder/README.md](coder/README.md).
- **[PocketBase](https://pocketbase.io/)** (`ghcr.io/muchobien/pocketbase:${POCKETBASE_TAG:-latest}`): Single-binary Go + SQLite backend sandbox (`pb.vrg.rocks`, port `8090`) with real-time subscriptions, auth, and admin UI (`/_/`) for rapid Svelte 5 / Datastar / HTMX prototyping.

### 8. Storage, Aviation & Utilities ([`compose/utilities.yml`](compose/utilities.yml))

- **[Copyparty](https://github.com/9001/copyparty):** File server and WebDAV for `data/copyparty`, `data/media`, `data/torrents`, and the external drive.
- **[Homebox](https://github.com/sysadminsmedia/homebox):** Physical asset and home inventory manager (`inv.vrg.rocks`, gated by Tinyauth v5), paired with the mobile barcode scanner PWA (`scan.vrg.rocks`).
- **[Backrest](https://github.com/garethgeorge/backrest)** (`ghcr.io/garethgeorge/backrest:latest`): Single-binary Go WebUI and scheduler for encrypted, deduplicated Restic backups on port `9898` (`backrest.vrg.rocks`) to `/Volumes/PANOPTICON/backups/sol-restic` and `rclone:OneDrive:Sol-Restic`.
- **[Enclosed](https://github.com/CorentinTh/enclosed)** (`ghcr.io/corentinth/enclosed:${ENCLOSED_TAG:-latest}`): Zero-knowledge client-side encrypted notes and self-destructing file drops built on Hono (`send.vrg.rocks`, port `8787`).
- **[AirTrail](https://github.com/johanohly/AirTrail)** (`johly/airtrail:${AIRTRAIL_TAG:-latest}`): Personal flight log and aircraft registry built with SvelteKit (`fly.vrg.rocks`, port `3000`, sharing `paperless-db` PostgreSQL 17).
- **[ntfy](https://ntfy.sh/):** Local pub/sub push notifications.
- *Standby:* Vaultwarden, n8n, Home Assistant, Rclone (`ops` and `standby`).

---

## Active and Standby Services

| Set | Count | Services |
| :--- | :--- | :--- |
| Active | 29 | `caddy`, `tinyauth`, `lldap`, `arcane`, `glance`, `jellyfin`, `seerr`, `radarr`, `sonarr`, `bazarr`, `lidarr`, `prowlarr`, `byparr`, `qbittorrent`, `qui`, `paperless-webserver`, `paperless-broker`, `paperless-db`, `ignis`, `readeck`, `code-server`, `coder`, `pocketbase`, `copyparty`, `homebox`, `backrest`, `enclosed`, `airtrail`, `ntfy` |
| Standby | 21 | `authentik-postgresql`, `authentik-server`, `authentik-worker`, `cross-seed`, `gatus`, `dozzle`, `beszel`, `beszel-agent`, `flaresolverr`, `recyclarr`, `wizarr`, `unpackerr`, `paperless-gotenberg`, `paperless-tika`, `paperless-ai`, `leafwiki`, `kavita`, `vaultwarden`, `n8n`, `homeassistant`, `rclone` (`ops`, `standby`) |
| Static Web | 10 | `mind.vrg.rocks`, `fam.vrg.rocks`, `scan.vrg.rocks`, `aysynbm.vrg.rocks`, `tools.vrg.rocks` (IT-Tools), `chef.vrg.rocks` (CyberChef), `pdf.vrg.rocks` (BentoPDF), `speed.vrg.rocks` (OpenSpeedTest), `draw.vrg.rocks` (Excalidraw), `mi.vrg.rocks` (MediaInfo Web WASM) |
| Native | 1 | `jellyfin-metal` |

Each standby service has a matching commented vhost in the [`Caddyfile`](Caddyfile) under a `--- Standby ... Routes ---` header. To bring one online:

1. Start it: `docker compose --profile standby up -d <service>`.
2. Uncomment its vhost block in `Caddyfile`.
3. Recreate Caddy so the new file is loaded: `docker compose up -d --force-recreate caddy`.
4. Change its `status` in [`ports.json`](ports.json) to `active`.

---

## Storage and Hardlinks

### Instant File Moves (APFS Hardlinks)

`${DOCKER_DATA_DIR}` (`/Users/vrg/Documents/Sol/data`) is mounted at `/data` in Radarr, Sonarr, Lidarr, Bazarr, qBittorrent, Cross-Seed, and Unpackerr:

- Downloads: `/data/torrents/...`
- Media library: `/data/media/...`

Both paths sit on one bind mount on the same APFS volume, so an import is a hardlink with no extra disk use.

Linux `link(2)` fails with `EXDEV` across two different mount points, even when both point to the same host disk. A hardlink from `/downloads/...` to `/data/media/...` therefore fails inside a container. New torrents must save under `/data/torrents`. The live cutover steps are in [Task 5 of the runbook](docs/FLASH_LOCAL_VERIFICATION_RUNBOOK.md#task-5-unifying-downloads-and-data-qbittorrent-cross-seed-arr).

### Mass Storage Layout

- **Internal SSD (`/Users/vrg/Documents/Sol/data`):** Databases, active downloads, document archive, and cinema preshows.
- **`EXTERNAL_DRIVE_00` (`/Volumes/PANOPTICON`):** Bulk movie and TV archive, mounted at `/external` (and `/media/external` in Jellyfin).
- **`EXTERNAL_DRIVE_01` (`/Volumes/PHOENIX`):** Defined in `.env`. Mounted only by `qbit_manage` (standby) at `/ext01`.
- **Cross-Seed on ExFAT:** Hardlinks do not work on ExFAT. Cross-seeds of files on the external drive use symlinks.

---

## Repository Structure

```
/Users/vrg/Documents/Sol/
├── .env.example                          # Environment template (placeholders, tag pins)
├── .gitignore                            # Ignores secrets, data, config (except rclone filter template)
├── Caddyfile                             # Caddy routes, forward auth, standby vhosts (commented)
├── ports.json                            # Port, route, status, and profile registry
├── docker-compose.yml                    # Root Compose file ('name: sol', 'include:')
├── Sol.code-workspace                    # VS Code workspace settings
├── README.md                             # This file
├── TODO.md                               # Roadmap and open tasks
├── sol.svg                               # Server logo
│
├── compose/                              # Domain Compose stacks (active + standby profiles)
│   ├── core.yml                          # Caddy, Authentik (server, worker, PostgreSQL 16), Arcane
│   ├── monitoring.yml                    # Glance | standby: Gatus, Dozzle, Beszel, Dockge, Kuma, Homarr
│   ├── media.yml                         # Jellyfin, Seerr, *arr, Prowlarr, Byparr | standby: FlareSolverr, Recyclarr, Wizarr
│   ├── download.yml                      # qBittorrent, QUI, Cross-Seed | standby: Unpackerr, qbit_manage, Flood
│   ├── paperless.yml                     # Paperless-ngx, Redis 8, PostgreSQL 17 | standby: Gotenberg, Tika, AI
│   ├── knowledge.yml                     # Ignis | standby: LeafWiki, Kavita, Calibre, Calibre-Web
│   ├── coding.yml                        # code-server, Coder
│   └── utilities.yml                     # Copyparty, Homebox, Backrest, ntfy | standby: Vaultwarden, n8n, HA, Rclone
│
├── config/
│   ├── auth/
│   │   └── users.json                    # Tracked single-email identity manifest (Tinyauth, lldap, Jellyfin, Seerr, Copyparty)
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
│   │   └── tracker_registry.json         # Tracked registry of 26 official short tracker tags, names, URLs, and announce domains
│   └── rclone/
│       └── filter.txt.example            # Tracked rclone filter template
│
├── scripts/                              # Automation scripts
│   ├── allowlist_user.sh                 # Single-command user allowlist & 5-target identity sync front-door
│   ├── identity_sync.py                  # Unified reconciler across Tinyauth, lldap, Jellyfin, Seerr, and Copyparty
│   ├── stage_db_backups.sh               # Pre-backup hook: pg_dump, WAL-complete SQLite snapshots, symlink manifest, Coder tar
│   ├── backup.sh                         # Staging + encrypted Restic snapshots to PANOPTICON and OneDrive
│   ├── restore.sh                        # Full Mac reset recovery: Restic pull, DB restore, symlink rebuild, Coder volume restore
│   ├── merge_overseerr_history.py        # Idempotent historical Overseerr -> Seerr media_request merge utility
│   ├── setup_jellyfin_metal.py           # Native Jellyfin launcher (--reset re-runs the setup wizard)
│   └── test_cross_seed.sh                # Cross-Seed permission and hardlink test as PUID:PGID
│
├── coder/                                # Coder Docker workspace template
│   ├── main.tf                           # Terraform template (prebuilt jj v0.28.2, Bun, /home/coder volume)
│   └── README.md                         # Template usage and 'coder templates push'
│
├── docs/
│   ├── FLASH_LOCAL_VERIFICATION_RUNBOOK.md   # Step-by-step live host verification playbook
│   └── system_state/                         # System state reports 00 to 09
│       └── 09_ARCHITECTURAL_AUDIT_AND_UPGRADE_PLAN.md
│
│   # --- Runtime data (ignored by git, backed up to OneDrive) ---
├── .env                                  # Live credentials and secrets
├── config/*                              # App configs and SQLite databases (incl. config/rclone/filter.txt)
├── data/                                 # Media, PostgreSQL clusters, torrents, backups
├── web/                                  # Static web apps (fam, scan, aysynbm)
├── quartz/                               # Digital garden source and public/ build
└── logs/                                 # Backup logs (backup_YYYY-MM-DD_HH-MM-SS.log)
```

---

## Port and Ingress Matrix

Active routes only. Standby routes are commented in the `Caddyfile` and listed in [`ports.json`](ports.json).

| Host Port | Service | Internal Port | Protocol | Route / FQDN | Auth | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`80`** | `caddy` | `80` | TCP | `*.vrg.rocks` | HTTP to HTTPS redirect | **Active (Edge)** |
| **`443`** | `caddy` | `443` | TCP/UDP | `*.vrg.rocks` | Edge TLS / HTTP/3 | **Active (Edge)** |
| **`127.0.0.1:9000`** | `authentik-server` | `9000` | TCP | `auth.vrg.rocks` | Authentik native | **Active (loopback)** |
| **`127.0.0.1:9443`** | `authentik-server` | `9443` | TCP | *(local debugging only)* | Authentik native TLS | **Active (loopback)** |
| **`42069`** | `qbittorrent` | `42069` | TCP/UDP | *(peer wire)* | None (WAN torrenting) | **Active** |
| **`8097`** | `jellyfin-metal` (native) | `8097` | TCP | `metal.vrg.rocks` | Jellyfin native | **Active (Native)** |
| *Bridge only* | `authentik-postgresql` | `5432` | TCP | `authentik-postgresql:5432` | DB password | **Active** |
| *Bridge only* | `authentik-worker` | none | n/a | none | n/a | **Active** |
| *Bridge only* | `arcane` | `3552` | TCP | `arcane.vrg.rocks` | Authentik forward auth + OIDC | **Active** |
| *External LAN* | Physical router | `80` | TCP | `router.vrg.rocks` (`http://192.168.50.1`) | Authentik forward auth | **Active** |
| *Bridge only* | `glance` | `8080` | TCP | `dash.vrg.rocks` | Authentik forward auth | **Active** |
| n/a | Redirect | n/a | HTTPS | `sol.vrg.rocks` to `https://dash.vrg.rocks/sol` (302) | via `dash.` | **Active** |
| *Bridge only* | `jellyfin` | `8096` | TCP | `watch.vrg.rocks`, `jellyfin.vrg.rocks` | Jellyfin native | **Active** |
| *Bridge only* | `seerr` | `5055` | TCP | `request.vrg.rocks`, `seerr.vrg.rocks`, `jellyseerr.vrg.rocks` | Authentik forward auth | **Active** |
| *Bridge only* | `radarr` | `7878` | TCP | `radarr.vrg.rocks` | Authentik forward auth | **Active** |
| *Bridge only* | `sonarr` | `8989` | TCP | `sonarr.vrg.rocks` | Authentik forward auth | **Active** |
| *Bridge only* | `bazarr` | `6767` | TCP | `bazarr.vrg.rocks` | Authentik forward auth | **Active** |
| *Bridge only* | `lidarr` | `8686` | TCP | `lidarr.vrg.rocks` | Authentik forward auth | **Active** |
| *Bridge only* | `prowlarr` | `9696` | TCP | `prowlarr.vrg.rocks` | Authentik forward auth | **Active** |
| *Bridge only* | `byparr` | `8191` | TCP | `byparr.vrg.rocks`, `flaresolverr.vrg.rocks` (alias `flaresolverr`) | Authentik forward auth | **Active** |
| *Bridge only* | `qbittorrent` | `8080` | TCP | `qb.vrg.rocks`, `qbittorrent.vrg.rocks` | qBittorrent native (Android app) | **Active** |
| *Bridge only* | `qui` | `7476` | TCP | `qui.vrg.rocks` | Authentik forward auth + QUI login | **Active** |
| *Bridge only* | `cross-seed` | `2468` | TCP | `cs.vrg.rocks` | Authentik forward auth | **Active** |
| *Bridge only* | `paperless-webserver` | `8000` | TCP | `docs.vrg.rocks`, `paperless.vrg.rocks` | Paperless OIDC (Authentik) | **Active** |
| *Bridge only* | `paperless-broker` | `6379` | TCP | `paperless-broker:6379` | Internal | **Active** |
| *Bridge only* | `paperless-db` | `5432` | TCP | `paperless-db:5432` | DB password | **Active** |
| *Bridge only* | `ignis` | `8080` | TCP | `ignis.vrg.rocks` | Authentik forward auth | **Active** |
| *Bridge only* | `code-server` | `8443` | TCP | `code.vrg.rocks` | Authentik forward auth + code-server password | **Active** |
| *Bridge only* | `coder` | `7080` | TCP | `coder.vrg.rocks` | Authentik forward auth | **Active** |
| *Bridge only* | `copyparty` | `3923` | TCP | `files.vrg.rocks`, `copyparty.vrg.rocks` | Authentik + Copyparty ACL | **Active** |
| *Bridge only* | `homebox` | `7745` | TCP | `inv.vrg.rocks` | Authentik forward auth + Homebox ACL | **Active** |
| *Bridge only* | `backrest` | `9898` | TCP | `backrest.vrg.rocks` | Authentik forward auth | **Active** |
| *Bridge only* | `ntfy` | `80` | TCP | `ntfy.vrg.rocks` | ntfy token / open | **Active** |
| *Static* | `caddy` (`/mind`) | n/a | HTTPS | `mind.vrg.rocks` | Authentik forward auth | **Active** |
| *Static* | `caddy` (`/fam`) | n/a | HTTPS | `fam.vrg.rocks` | Authentik forward auth | **Active** |
| *Static* | `caddy` (`/scan`) | n/a | HTTPS | `scan.vrg.rocks` | Authentik forward auth | **Active** |
| *Static* | `caddy` (`/aysynbm`) | n/a | HTTPS | `aysynbm.vrg.rocks` | Public | **Active** |

Known drift: `home.vrg.rocks` is still an active vhost to `http://host.docker.internal:8123` with forward auth, but `homeassistant` is on the standby profile. It returns `502` until Home Assistant runs.

---

## Operational Commands

Run every command from the repository root. Compose reads `.env` from the project directory.

### Docker Lifecycle

```bash
# Start the 25 active services
docker compose up -d

# Status and logs
docker compose ps
docker compose logs -f caddy
docker compose logs -f paperless-webserver

# Validate the full model (all 50 service definitions)
docker compose config -q

# List services that start by default (expect 25)
docker compose config --services | wc -l

# Stop all containers
docker compose down
```

### Standby and Ops Profiles

```bash
# Start one standby service
docker compose --profile standby up -d homebox

# Stop it again
docker compose stop homebox

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

# Reload Caddy after a Caddyfile edit (recreate if the in-container file hash differs)
docker exec caddy caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
docker compose up -d --force-recreate caddy
```

Do not run `docker compose -f compose/media.yml ...`. That makes `compose/` the project directory, so Compose does not find the root `.env` and every `${DOCKER_*}` path resolves to empty.

### Pulling Updates

```bash
docker compose pull
docker compose up -d
```

Image tags for `caddy`, `paperless-ngx`, `arcane`, `coder`, and `authentik` come from `.env` (`CADDY_TAG`, `PAPERLESS_TAG`, `ARCANE_TAG`, `CODER_TAG`, `AUTHENTIK_TAG`). Check the release notes before you raise a major version.

### Native Jellyfin Metal (macOS Hardware Transcoding)

```bash
# Launch (keeps config/jellyfin_metal/data/jellyfin.db, users, and watch history)
python3 scripts/setup_jellyfin_metal.py

# Wipe config/jellyfin_metal and re-run the first-time setup wizard (destructive)
python3 scripts/setup_jellyfin_metal.py --reset

# Health check
curl -s http://localhost:8097/System/Info/Public | jq .

# Stop
killall jellyfin
```

`--reset` reads the admin password from `CORE_PASSWORD` (environment or `.env`), or prompts for it. It sets VideoToolbox acceleration, the Abyss theme, the Movies and Shows libraries (internal SSD plus `/Volumes/PANOPTICON` when present), and API keys for Jellyseerr and Bazarr.

### Diagnostics

```bash
# Cross-Seed write permission and hardlink test as PUID:PGID (501:20)
./scripts/test_cross_seed.sh
```

---

## Backup and Disaster Recovery

### Two-Tier Backup Architecture

Sol uses a two-tier backup architecture designed for zero-bloat version control and 100% deterministic bare-metal state recovery:

1. **Tier 1 — Full Server State Backup (Backrest + Restic to `/Volumes/PANOPTICON` and `OneDrive`):**
   - Managed via **Backrest (`https://backrest.vrg.rocks`)** and [`scripts/backup.sh`](scripts/backup.sh), paired with the pre-backup staging hook [`scripts/stage_db_backups.sh`](scripts/stage_db_backups.sh) (scheduled via macOS `launchd` `com.vrg.sol.db-stage.plist`).
   - Backs up the entire `/Users/vrg/Documents/Sol` directory **except** bulk media files (`data/media/{movies,tv,music,books,home-videos}`), raw torrent downloads (`data/torrents/{movies,tv,books,music,temp,incomplete}`), live database binary clusters (which are dumped cleanly into `data/backups/*.sql.gz` and `data/backups/sqlite/*`), logs, and regenerable caches/bundles (`excludes.txt.example`).
   - **Recovery Guarantee:** After a complete Mac wipe and reset, restoring the Restic snapshot (`./scripts/restore.sh --restore-dbs --start-stack`) with media files in their respective folders brings **100% of the server, databases, secrets (`.env`), `.torrent`/`.fastresume` state, Paperless documents, Obsidian vaults, Coder workspace volume, and media symlink trees** back up and running identically to the time of backup.
2. **Tier 2 — Declarative Infrastructure Blueprint (`GitHub` `varungupta3009/Sol`):**
   - Tracks a lean, zero-secret infrastructure-as-code blueprint (`docker-compose.yml`, `compose/*.yml`, `Caddyfile`, `ports.json`, `.env.example`, `config/glance/**`, `config/qui/tracker_registry.json`, `config/auth/users.json.example`, `config/backrest/*.example`, `config/rclone/filter.txt.example`, `coder/main.tf`, `scripts/*`, and `docs/*`).
   - Allows provisioning and configuring the entire container topology, routing layer, dashboards, and automation scripts from scratch as of the latest commit without requiring runtime data volumes.

### Running Backups ([`scripts/backup.sh`](scripts/backup.sh), [`scripts/stage_db_backups.sh`](scripts/stage_db_backups.sh) & `https://backrest.vrg.rocks`)

```bash
# Run full staged backup to both PANOPTICON and OneDrive (Restic via Backrest)
./scripts/backup.sh

# Run local-only Restic snapshot to /Volumes/PANOPTICON/backups/sol-restic
./scripts/backup.sh --local-only

# Run pre-backup database & symlink staging independently (also triggered by launchd before Backrest schedules)
./scripts/stage_db_backups.sh
```

Pipeline:

1. **Pre-Backup Staging ([`scripts/stage_db_backups.sh`](scripts/stage_db_backups.sh)):**
   - Dumps `paperless-db` (`paperless` and `airtrail` databases) and `coder` (embedded PostgreSQL) with `pg_dump` to `data/backups/{paperless_db,airtrail_db,coder_db}.sql.gz` (atomic temp file, then rename).
   - Copies each SQLite database (`*.db`, `*.sqlite`, `*.sqlite3`, including `data/lldap/users.db`, `data/tinyauth/tinyauth.db`, `config/qui/qui.db`, and all `*arr` DBs) and its `-wal` file (without `-shm`) to a local temp directory and runs `sqlite3 .backup` into `data/backups/sqlite/`, capturing all un-checkpointed WAL transactions without touching guest Linux VM `-shm` mmap files.
   - Exports all library and cross-seed symlinks in `data/media`, `data/torrents/{cross-seed-links,qui-links}`, and `/Volumes/PANOPTICON/{media,torrents}` to `data/backups/symlinks_manifest.tsv` so relative media symlinks can be reconstructed after a Mac reset.
   - Archives the persistent Coder workspace Docker volume (`coder-*-home`) to `data/backups/coder_home.tar.gz`.
2. **Restic Deduplicated Snapshot (Backrest Plans `sol-local-daily` & `sol-onedrive-cloud`, or [`scripts/backup.sh`](scripts/backup.sh)):**
   - Snapshots `/userdata/sol` into `/repos/local-panopticon` (`/Volumes/PANOPTICON/backups/sol-restic`) and `rclone:OneDrive:Sol-Restic` using [`config/backrest/excludes.txt.example`](config/backrest/excludes.txt.example), retaining `7 daily / 4 weekly / 6 monthly` snapshots with automated weekly prune and integrity checks.

### Restoring on a Fresh Machine ([`scripts/restore.sh`](scripts/restore.sh))

```bash
# 1. Clone the repository
git clone https://github.com/varungupta3009/Sol.git /Users/vrg/Documents/Sol && cd /Users/vrg/Documents/Sol

# 2. Preview available Restic snapshots (no changes)
./scripts/restore.sh --dry-run

# 3. Restore latest snapshot from PANOPTICON (or --from-cloud for OneDrive), rebuild DBs, symlinks, Coder volume, and start stack
./scripts/restore.sh --restore-dbs --start-stack
```

| Flag | Effect |
| :--- | :--- |
| `--dry-run` | Lists Restic snapshots and previews restore plan without mutating files. |
| `--from-cloud` | Pulls the Restic snapshot from `rclone:OneDrive:Sol-Restic` instead of local `/Volumes/PANOPTICON/backups/sol-restic`. |
| `--skip-cloud-pull` | Uses already-extracted local files under `data/backups/` without running `restic restore`. |
| `--restore-dbs` | Imports PostgreSQL `.sql.gz` dumps (`paperless_db.sql.gz`, `airtrail_db.sql.gz`, `authentik_db.sql.gz`), restores WAL-complete SQLite snapshots, and restores `coder_home.tar.gz`. |
| `--start-stack` | Recreates media symlinks from `symlinks_manifest.tsv`, repopulates static web tools if missing, and starts all 29 active containers. |

---

## Secrets and Security

- **Environment:** All passwords, tokens, API keys, and host paths live in `.env`, which git ignores. [`.env.example`](.env.example) is the tracked template. Values with spaces or JSON are quoted so that both Compose and bash parse them.
- **Explicit variables:** Each service declares only the variables it needs under `environment:`.
- **Forward auth:** Caddy checks sessions at `authentik-server:9000/outpost.goauthentik.io/auth/caddy` (embedded outpost) before it routes to admin panels. This covers `dash.vrg.rocks` and `code.vrg.rocks`.
- **Exceptions:** `qb.vrg.rocks` uses qBittorrent native auth for the Android client. `auth.vrg.rocks`, `watch.`/`jellyfin.`, `metal.`, `docs.`/`paperless.`, `ntfy.`, and `aysynbm.` handle auth in the app or are public by design.
- **Loopback only:** `authentik-server` binds `127.0.0.1:9000` and `127.0.0.1:9443`. `rclone` (ops) binds `127.0.0.1:53682` for the OAuth callback.
- **Least privilege:** `authentik-worker` runs without root and without `/var/run/docker.sock`. `arcane` logs at `info`.
- **CORS:** When `inv.vrg.rocks` is re-enabled, it allows only the origin `https://scan.vrg.rocks`.

---

## Documentation Index

| Document | Content |
| :--- | :--- |
| [`docs/system_state/00` to `08`](docs/system_state) | Topology, service catalog, storage, ingress, legacy registry, migration plan, config taxonomy, media stack, performance |
| [`09_ARCHITECTURAL_AUDIT_AND_UPGRADE_PLAN.md`](docs/system_state/09_ARCHITECTURAL_AUDIT_AND_UPGRADE_PLAN.md) | October 2026 `/double-agent` review, five upgrade phases, open live-host checks |
| [`10_MEGA_OPTIMIZATION_AND_CONTAINER_ROADMAP.md`](docs/system_state/10_MEGA_OPTIMIZATION_AND_CONTAINER_ROADMAP.md) | Live infrastructure audit, SQLite/Servarr/Cross-Seed repairs, `qui` deployment, "Lean is Sexy" 2026 container replacement matrix, and dossier-inspired passion projects |
| [`11_AUTHENTICATION_AND_SSO_STRATEGY.md`](docs/system_state/11_AUTHENTICATION_AND_SSO_STRATEGY.md) | Zero-click Google SSO, Tinyauth v5 OIDC & forward-auth architecture, per-app admin ACLs, and `scripts/allowlist_user.sh` approval workflow |
| [`FLASH_LOCAL_VERIFICATION_RUNBOOK.md`](docs/FLASH_LOCAL_VERIFICATION_RUNBOOK.md) | Live host playbook: `.env` reconciliation, backups, Authentik, Byparr, `/data` cutover, Alpine trial, Homebox repair |
| [`TODO.md`](TODO.md) | Roadmap and open tasks |
| [`coder/README.md`](coder/README.md) | Coder workspace template |
