<div align="center">

# ☀️ Sol

**A modular home server running on an Apple Silicon M1 Pro Mac.**

[![Host](https://img.shields.io/badge/Host-macOS%20Apple%20Silicon%20(M1%20Pro)-000000?style=for-the-badge&logo=apple&logoColor=white)](#)
[![Docker](https://img.shields.io/badge/Docker-Compose%20V2%20(Native%20Include)-2496ED?style=for-the-badge&logo=docker&logoColor=white)](#)
[![Reverse Proxy](https://img.shields.io/badge/Ingress-Caddy%20v2%20(HTTP%2F3%20%2B%20TLS)-1F88C0?style=for-the-badge&logo=caddy&logoColor=white)](#)
[![Identity](https://img.shields.io/badge/Auth-Authentik%20SSO%20%26%20OIDC-FD4B2D?style=for-the-badge&logo=authentik&logoColor=white)](#)
[![Filesystem](https://img.shields.io/badge/Storage-APFS%20Zero--Copy%20Hardlinks-34D058?style=for-the-badge)](#)
[![Backup](https://img.shields.io/badge/Backup-Rclone%20to%20OneDrive-0078D4?style=for-the-badge&logo=microsoftonedrive&logoColor=white)](#)

---

</div>

## Table of Contents
1. [Overview](#overview)
2. [Architecture Topology](#architecture-topology)
3. [Domain Stacks](#domain-stacks)
4. [Storage and Hardlinks](#storage-and-hardlinks)
5. [Repository Structure](#repository-structure)
6. [Port and Ingress Matrix](#port-and-ingress-matrix)
7. [Operational Commands](#operational-commands)
8. [Backup and Disaster Recovery](#backup-and-disaster-recovery)
9. [Secrets and Security](#secrets-and-security)

---

## Overview

Sol is a single-node home server running on an 8-core Apple Silicon M1 Pro Mac. It handles reverse proxy routing with auto-HTTPS, identity and SSO, automated media downloads, document archiving with OCR, browser workspaces, and local file storage with low power draw and quiet operation.

### Key Principles
* **Apple Silicon Concurrency Tuning:** Configured for the M1 Pro (6 Performance + 2 Efficiency cores) and unified memory. Concurrency is tuned per service (Paperless OCR threads, Authentik workers, PostgreSQL buffer sizes, Caddy streaming buffers) so background tasks stay fast without hogging host resources.
* **Modular Compose Stacks (`include:`):** Organized into 8 domain compose files under `compose/`. Containers communicate over the shared `sol_default` bridge network with internal DNS resolution (`http://radarr:7878`, `http://authentik-server:9000`, etc.).
* **Zero-Copy File Moves:** Uses a unified `/data` mount across the media stack on APFS, enabling instant zero-copy hardlinks between torrent downloads and library directories.
* **Edge Security:** Caddy terminates TLS and handles HTTP/3 at the edge, checking user sessions against Authentik forward-auth before requests hit internal dashboards.
* **State vs Configuration:** Infrastructure files are tracked cleanly in version control, while application state, databases, and configuration directories are backed up to Microsoft OneDrive via Rclone.

---

## Architecture Topology

```
                                  [ Internet / WAN ]
                                           |
                                           v
                             +---------------------------+
                             |       Caddy Reverse       |
                             |      Proxy (:80, :443)    |
                             +-------------+-------------+
                                           |
                   +-----------------------+-----------------------+
                   | (Forward Auth / TLS)  |                       |
                   v                       v                       v
     +--------------------------+  +---------------+  +--------------------------+
     |     Authentik Server     |  | Glance Hub    |  | Static Web Endpoints     |
     |   (:9000, :9443 / auth)  |  | (dash.)       |  |  - /mind (Digital Garden)|
     +-------------+------------+  +---------------+  |  - /fam (Family Vault)   |
                   |                                  |  - /scan (Homebox PWA)   |
                   v                                  |  - /aysynbm (Bookmarks)  |
     +--------------------------+                     +--------------------------+
     | PostgreSQL 16 (Auth DB)  |
     +--------------------------+
                   |
  +----------------+----------------+----------------+----------------+
  |                                 |                                 |
  v                                 v                                 v
+----------------------+  +----------------------+  +----------------------+
| Media & Automation   |  | Docs & Knowledge     |  | Workspaces & Storage |
| - Jellyfin (:8096)   |  | - Paperless (:8000)  |  | - Code-Server (:8443)|
| - Seerr (:5055)      |  | - Redis Broker (:6379|  | - Coder Server(:7080)|
| - Radarr (:7878)     |  | - PostgreSQL 17 (DB) |  | - Copyparty (:3923)  |
| - Sonarr (:8989)     |  | - Homebox (:7745)    |  | - ntfy Push (:80)    |
| - Bazarr (:6767)     |  | - Ignis (:8080)      |  | - Arcane (:3552)     |
| - Lidarr (:8686)     |  +----------------------+  +----------------------+
| - Prowlarr (:9696)   |
| - qBittorrent (:8080)|
| - Cross-Seed (:2468) |
| - FlareSolverr(:8191)|
+----------------------+
```

---

## Domain Stacks

The server is split into 8 focused compose files in [`compose/`](compose):

### 1. Ingress & Identity (`compose/core.yml`)
* **[Caddy v2](https://caddyserver.com/):** Edge reverse proxy with Let's Encrypt TLS certificates, HTTP/3 support, response compression, and static file hosting.
* **[Authentik](https://goauthentik.io/):** Identity provider backed by PostgreSQL 16. Provides forward-auth middleware for admin panels and OIDC SSO.
* **[Arcane](https://github.com/getarcaneapp/arcane):** Docker stack and container management interface.

### 2. Monitoring & Dashboards (`compose/monitoring.yml`)
* **[Glance](https://github.com/glanceapp/glance):** Home dashboard displaying container statuses, weather, feeds, and quick links.
* *Standby Services:* Beszel (metrics), Uptime Kuma (uptime monitoring), Dozzle (log viewer), Homarr.

### 3. Media & Servarr (`compose/media.yml`)
* **[Jellyfin (Containerized)](https://jellyfin.org/):** Main media streaming server for movies, shows, and music (`watch.vrg.rocks`, port 8096).
* **[Jellyfin Metal (Native macOS)](https://jellyfin.org/):** Native host instance with Apple Silicon VideoToolbox acceleration for hardware 4K transcoding and HDR tone mapping (`metal.vrg.rocks`, port 8097).
* **[Seerr](https://github.com/seerr-team/seerr):** Request management and discovery portal connected to Sonarr/Radarr.
* **[Radarr](https://radarr.video/):** Movie collection manager and downloader coordinator.
* **[Sonarr](https://sonarr.tv/):** TV series tracker and downloader coordinator.
* **[Bazarr](https://www.bazarr.media/):** Subtitle downloader for movies and TV shows.
* **[Lidarr](https://lidarr.audio/):** Music collection manager.
* **[Prowlarr](https://prowlarr.com/):** Indexer manager for torrent trackers.
* **[FlareSolverr](https://github.com/FlareSolverr/FlareSolverr):** Cloudflare bypass proxy for tracker queries.

### 4. Downloads & Cross-Seeding (`compose/download.yml`)
* **[qBittorrent](https://www.qbittorrent.org/):** Torrent client with forwarded WAN port (`42069`) and remote WebUI.
* **[Cross-Seed](https://cross-seed.org/):** Searches and injects matching cross-seeded torrents across trackers.

### 5. Document Management & OCR (`compose/paperless.yml`)
* **[Paperless-ngx](https://docs.paperless-ngx.com/):** Document archiving system with OCR, backed by PostgreSQL 17 and Redis.
* **Pre-Consumption Hook (`pre-consumption.py`):** Custom script using `pikepdf` to decrypt statement PDFs and extract embedded attachments during ingestion.
* **Push Notifications (`ntfy_notify.sh`):** Sends push alerts via ntfy when documents finish processing.

### 6. Knowledge & Notes (`compose/knowledge.yml`)
* **[Ignis](https://github.com/nobbe/ignis):** Markdown vault synchronization for Obsidian notes.

### 7. Developer Workspaces (`compose/coding.yml`)
* **[code-server](https://github.com/coder/code-server):** Web-based VS Code environment for direct file editing.
* **[Coder](https://coder.com/):** Developer workspace provisioning via local Terraform templates.

### 8. Storage & Utilities (`compose/utilities.yml`)
* **[Copyparty](https://github.com/9001/copyparty):** Fast multi-user file server, media streamer, and WebDAV server.
* **[Homebox](https://homebox.software/):** Inventory and asset tracking.
* **[ntfy](https://ntfy.sh/):** Local pub/sub push notification server.

---

## Storage and Hardlinks

### Instant File Moves (APFS Hardlinks)
To prevent disk churn and duplicated space during downloads, `${DOCKER_DATA_DIR}` (`/Users/vrg/Documents/Sol/data`) is mounted into Radarr, Sonarr, Lidarr, and Bazarr at `/data`:
* Downloads path: `/data/torrents/...`
* Media library path: `/data/media/...`

Because both paths live on the same APFS container mount, moving or hardlinking downloaded releases into media libraries happens instantly with zero duplicate disk usage.

### Mass Storage Layout
* **Internal SSD (`/Users/vrg/Documents/Sol/data`):** Transactional state, active downloads, document databases, and cinema preshows.
* **External Drives (`/Volumes/PANOPTICON`):** Bulk movie and TV archives.
* **Cross-Seeding:** Cross-Seed creates symlinks across filesystem boundaries so multiple trackers can seed the same file without duplicating data.

---

## Repository Structure

```
/Users/vrg/Documents/Sol/
├── .env.example                          # Environment template with placeholders
├── .gitignore                            # Git ignore rules for data, secrets, and caches
├── Caddyfile                             # Caddy reverse proxy routes and forward-auth
├── ports.json                            # Port and routing reference
├── docker-compose.yml                    # Root Compose file using 'include:'
├── Sol.code-workspace                    # VS Code workspace settings
├── README.md                             # Documentation
├── TODO.md                               # Roadmap and pending tasks
├── sol.svg                               # Server logo graphic
│
├── compose/                              # Domain Compose stacks
│   ├── core.yml                          # Caddy, Authentik, Arcane
│   ├── monitoring.yml                    # Glance, metrics
│   ├── media.yml                         # Jellyfin, Seerr, Servarr suite
│   ├── download.yml                      # qBittorrent, Cross-Seed
│   ├── paperless.yml                     # Paperless-ngx, Redis, Postgres 17
│   ├── knowledge.yml                     # Ignis notes sync
│   ├── coding.yml                        # code-server, Coder
│   └── utilities.yml                     # Copyparty, Homebox, ntfy
│
├── scripts/                              # Automation scripts
│   ├── backup.sh                         # Rclone backup script with database dumps
│   ├── restore.sh                        # Disaster recovery restore script
│   ├── setup_jellyfin_metal.py           # Native Jellyfin bootstrap and API setup
│   └── test_cross_seed.sh                # Cross-seed permission checker
│
├── coder/                                # Terraform workspace templates
│   ├── main.tf, default.tf, README.md
│
├── docs/                                 # Audits and system documentation
│   └── system_state/                     # System state reports
│
│   # --- Runtime Data (Ignored by Git, Backed up to OneDrive) ---
├── .env                                  # Active credentials and secrets
├── config/                               # Application configurations and SQLite databases
├── data/                                 # Persistent media, databases, and torrents
├── web/                                  # Static web applications
├── quartz/                               # Digital garden source and build output
└── logs/                                 # Backup and execution logs
```

---

## Port and Ingress Matrix

| Host Port | Service | Internal Port | Protocol | Proxy Route / FQDN | Auth Enforcement | Stack Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`80`** | `caddy` | `80` | TCP | `*.vrg.rocks` | HTTP -> HTTPS Redirect | **Active (Edge)** |
| **`443`** | `caddy` | `443` | TCP/UDP | `*.vrg.rocks` | Edge TLS / HTTP/3 | **Active (Edge)** |
| **`9000`** | `authentik-server` | `9000` | TCP | `auth.vrg.rocks` | Authentik Native | **Active** |
| **`9443`** | `authentik-server` | `9443` | TCP | `auth.vrg.rocks` | Authentik Native TLS | **Active** |
| **`42069`** | `qbittorrent` | `42069` | TCP/UDP | *(Direct Peer Wire)* | None (WAN Torrenting) | **Active** |
| *Bridge Only* | `authentik-postgresql`| `5432` | TCP | `authentik-postgresql:5432` | Internal DB Password | **Active** |
| *Bridge Only* | `glance` | `8080` | TCP | `dash.vrg.rocks` | Direct / Application | **Active** |
| *Bridge Only* | `arcane` | `3552` | TCP | `arcane.vrg.rocks` | Authentik (Forward & OIDC)| **Active** |
| *Bridge Only* | `jellyfin` | `8096` | TCP | `watch.vrg.rocks`, `jellyfin.vrg.rocks`| Jellyfin Native Auth | **Active (Container)** |
| **`8097`** | `jellyfin (Metal)` | `8097` | TCP | `metal.vrg.rocks` | Jellyfin Native Auth | **Active (Native Metal)** |
| *Bridge Only* | `seerr` | `5055` | TCP | `request.vrg.rocks` | Authentik (Forward Auth) | **Active** |
| *Bridge Only* | `radarr` | `7878` | TCP | `radarr.vrg.rocks` | Authentik (Forward Auth) | **Active** |
| *Bridge Only* | `sonarr` | `8989` | TCP | `sonarr.vrg.rocks` | Authentik (Forward Auth) | **Active** |
| *Bridge Only* | `bazarr` | `6767` | TCP | `bazarr.vrg.rocks` | Authentik (Forward Auth) | **Active** |
| *Bridge Only* | `lidarr` | `8686` | TCP | `lidarr.vrg.rocks` | Authentik (Forward Auth) | **Active** |
| *Bridge Only* | `prowlarr` | `9696` | TCP | `prowlarr.vrg.rocks` | Authentik (Forward Auth) | **Active** |
| *Bridge Only* | `flaresolverr` | `8191` | TCP | `flaresolverr.vrg.rocks` | Direct Internal API | **Active** |
| *Bridge Only* | `qbittorrent` | `8080` | TCP | `qb.vrg.rocks`, `qbittorrent.vrg.rocks`| qBittorrent Native | **Active** |
| *Bridge Only* | `cross-seed` | `2468` | TCP | `cs.vrg.rocks` | Authentik (Forward Auth) | **Active** |
| *Bridge Only* | `paperless-webserver` | `8000` | TCP | `docs.vrg.rocks`, `paperless.vrg.rocks`| Paperless OIDC (Authentik)| **Active** |
| *Bridge Only* | `paperless-broker` | `6379` | TCP | `paperless-broker:6379` | Internal Redis Protocol | **Active** |
| *Bridge Only* | `paperless-db` | `5432` | TCP | `paperless-db:5432` | Internal DB Password | **Active** |
| *Bridge Only* | `ntfy` | `80` | TCP | `ntfy.vrg.rocks` | Direct / Token / Open | **Active** |
| *Bridge Only* | `code-server` | `8443` | TCP | `code.vrg.rocks` | code-server Password | **Active** |
| *Bridge Only* | `coder` | `7080` | TCP | `coder.vrg.rocks` | Authentik (Forward Auth) | **Active** |
| *Bridge Only* | `copyparty` | `3923` | TCP | `files.vrg.rocks`, `copyparty.vrg.rocks`| Authentik + Copyparty ACL | **Active** |
| *Bridge Only* | `homebox` | `7745` | TCP | `inv.vrg.rocks` | Authentik (Forward Auth) | **Active** |
| *Bridge Only* | `ignis` | `8080` | TCP | `ignis.vrg.rocks` | Authentik (Forward Auth) | **Active** |

---

## Operational Commands

### Docker Lifecycle
```bash
# Start all stacks
docker compose up -d

# View container status
docker compose ps

# Follow logs across all containers
docker compose logs -f

# Follow logs for a specific service
docker compose logs -f caddy
docker compose logs -f paperless-webserver
docker compose logs -f qbittorrent

# Validate compose configuration
docker compose config

# Stop all containers
docker compose down
```

### Domain Stack Operations
```bash
# Restart a specific domain stack
docker compose -f compose/media.yml restart
docker compose -f compose/core.yml restart

# Recreate a single service
docker compose up -d --force-recreate radarr
```

### Pulling Updates
```bash
# Pull latest container images
docker compose pull

# Apply updates cleanly
docker compose up -d --remove-orphans
```

### Native Jellyfin Metal (macOS Hardware Transcoding)
```bash
# Start Native Jellyfin in background
nohup /Applications/Jellyfin.app/Contents/MacOS/jellyfin \
  --configdir /Users/vrg/Documents/Sol/config/jellyfin_metal \
  --datadir /Users/vrg/Documents/Sol/config/jellyfin_metal/data \
  --cachedir /Users/vrg/Documents/Sol/config/jellyfin_metal/cache \
  --logdir /Users/vrg/Documents/Sol/config/jellyfin_metal/log \
  --webdir /Applications/Jellyfin.app/Contents/Resources/jellyfin-web \
  --ffmpeg /Applications/Jellyfin.app/Contents/MacOS/ffmpeg > /dev/null 2>&1 &

# Check status
curl -s http://localhost:8097/System/Info/Public | jq .

# Stop process
killall jellyfin

# Automated setup from scratch via API
python3 scripts/setup_jellyfin_metal.py
```

---

## Backup and Disaster Recovery

### Running Backups (`scripts/backup.sh`)
Dumps PostgreSQL databases (`authentik-postgresql`, `paperless-db`) to `data/backups/*.sql.gz`, filters out bulk media and cache folders via `config/rclone/filter.txt`, and syncs state to OneDrive:

```bash
./scripts/backup.sh
```

### Restoring on a Fresh Machine (`scripts/restore.sh`)
Restores configurations, database dumps, and state onto a fresh machine:

```bash
# 1. Create and enter directory
mkdir -p /Users/vrg/Documents/Sol && cd /Users/vrg/Documents/Sol

# 2. Preview files to be pulled
./scripts/restore.sh --dry-run

# 3. Pull backup, restore databases, and start the stack
./scripts/restore.sh --start-stack
```

---

## Secrets and Security

* **Environment Configuration:** All passwords, tokens, API keys, and host paths reside in [`.env`](.env), which is ignored by version control. A clean template with placeholders is tracked in [`.env.example`](.env.example).
* **Explicit Variables:** Services declare only their required variables under their `environment:` blocks in compose files, avoiding blanket credential leakage between containers.
* **Forward Authentication:** Caddy checks active user sessions against Authentik at `http://authentik-server:9000/outpost.goauthentik.io/auth/caddy` before routing requests to internal management panels.
