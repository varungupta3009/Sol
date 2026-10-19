# 01. Service Catalog & Specification Registry

> **Scope:** Specification breakdown of all 24 active containers, the 26 standby/ops containers managed through Docker Compose V2 profiles, the native `jellyfin-metal` instance, and the Caddy-served static frontends on `Sol`.  
> **Host Environment:** macOS (OrbStack / Docker Engine), Apple Silicon M1 Pro  
> **Environment Variables File:** `.env` (single source, template `.env.example`). The legacy `paperless.env` is archived in `docs/archive/`.  
> **Path Variables:** `DOCKER_BASE_DIR=/Users/vrg/Documents/Sol`, `DOCKER_CONFIG_DIR=${DOCKER_BASE_DIR}/config`, `DOCKER_DATA_DIR=${DOCKER_BASE_DIR}/data`, `DOCKER_LOGS_DIR=${DOCKER_BASE_DIR}/logs`, `EXTERNAL_DRIVE_00=/Volumes/PANOPTICON`, `EXTERNAL_DRIVE_01=/Volumes/PHOENIX`  
> **Security Notice:** All passwords, tokens, private keys, and encryption secrets are sanitized and redacted.  
> **Last Synced to Ground Truth:** 2026-10-17  

---

## Table of Contents
1. [Core Infrastructure & Identity Management](#1-core-infrastructure--identity-management)
   - [caddy](#caddy)
   - [authentik-server](#authentik-server)
   - [authentik-worker](#authentik-worker)
   - [authentik-postgresql](#authentik-postgresql)
   - [arcane](#arcane)
2. [Dashboard & Metrics](#2-dashboard--metrics)
   - [glance](#glance)
3. [Media Streaming & Automation Suite](#3-media-streaming--automation-suite)
   - [jellyfin](#jellyfin)
   - [jellyfin-metal (Native macOS)](#jellyfin-metal-native-macos)
   - [seerr](#seerr)
   - [radarr](#radarr)
   - [sonarr](#sonarr)
   - [bazarr](#bazarr)
   - [lidarr](#lidarr)
   - [prowlarr](#prowlarr)
   - [byparr](#byparr)
4. [Download & Cross-Seeding Pipeline](#4-download--cross-seeding-pipeline)
   - [qbittorrent](#qbittorrent)
   - [cross-seed](#cross-seed)
5. [Document Management & OCR Archival](#5-document-management--ocr-archival)
   - [paperless-webserver](#paperless-webserver)
   - [paperless-broker](#paperless-broker)
   - [paperless-db](#paperless-db)
   - [ignis](#ignis)
6. [Developer Workspaces, Logistics & Utilities](#6-developer-workspaces-logistics--utilities)
   - [code-server](#code-server)
   - [coder](#coder)
   - [copyparty](#copyparty)
   - [ntfy](#ntfy)
7. [Static Web Applications (Caddy Served)](#7-static-web-applications-caddy-served)
   - [Quartz Digital Garden (Quettamind)](#quartz-digital-garden-quettamind)
   - [Family Data Vault](#family-data-vault)
   - [Homebox Barcode Scanner PWA](#homebox-barcode-scanner-pwa)
   - [Async Bookmark Manager](#async-bookmark-manager)
8. [Standby & Ops Profile Registry](#8-standby--ops-profile-registry)
   - [homebox (Standby)](#homebox-standby)
   - [flaresolverr (Standby)](#flaresolverr-standby)
9. [Maintenance Scripts & Terraform](#9-maintenance-scripts--terraform)

---

## 1. Core Infrastructure & Identity Management

### `caddy`
*The primary edge ingress reverse proxy, TLS termination manager, and static asset web server.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `caddy` |
| **Base Image** | `caddy:${CADDY_TAG:-2}` (`.env.example`: `CADDY_TAG=2`) |
| **Restart Policy** | `unless-stopped` |
| **Capabilities** | `NET_ADMIN` (Required for HTTP/3 and network optimizations) |
| **Host Ports** | `80:80` (HTTP), `443:443` (HTTPS), `443:443/udp` (HTTP/3 / QUIC) |
| **Networks** | `default` (Bridge, `sol_default`) |
| **Dependencies** | None |
| **Compose File** | `compose/core.yml` |

```yaml
# Mount Hierarchy
volumes:
  - ${DOCKER_BASE_DIR}/Caddyfile:/etc/caddy/Caddyfile:ro   # Proxy configuration (Read-Only)
  - ${DOCKER_DATA_DIR}/caddy:/data                         # ACME certificates, runtime state, and locks
  - ${DOCKER_CONFIG_DIR}/caddy:/config                     # Autosaved runtime JSON configs
  - ${DOCKER_BASE_DIR}/quartz/public:/mind:ro              # Static Quartz HTML digital garden
  - ${DOCKER_BASE_DIR}/web/fam:/fam:ro                     # Static Family Data Vault web application
  - ${DOCKER_BASE_DIR}/web/scan:/scan:ro                   # Static Homebox mobile scanner PWA
  - ${DOCKER_BASE_DIR}/web/aysynbm:/aysynbm:ro             # Static Async bookmark manager web app
```
* **Glance Metadata:** ID: `caddy`, Name: `Caddy`, Icon: `sh:caddy`, URL: `https://dash.vrg.rocks`, Description: `Reverse Proxy & Ingress Gateway`

---

### `authentik-server`
*Core identity provider, single sign-on (SSO) gateway, OIDC authority, and embedded forward authentication outpost.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `authentik-server` |
| **Base Image** | `${AUTHENTIK_IMAGE:-ghcr.io/goauthentik/server}:${AUTHENTIK_TAG:-2026.5.3}` |
| **Command** | `server` |
| **Restart Policy** | `unless-stopped` |
| **Shared Memory** | `shm_size: 512mb` (Prevents Python Gunicorn worker crashes during heavy SSO flows) |
| **Host Ports** | `127.0.0.1:${COMPOSE_PORT_HTTP:-9000}:9000` (HTTP), `127.0.0.1:${COMPOSE_PORT_HTTPS:-9443}:9443` (HTTPS). Loopback only. External and LAN traffic enters through Caddy (`auth.vrg.rocks`). |
| **Web Workers** | `AUTHENTIK_WEB__WORKERS: 2` (M1 Pro concurrency, upstream nested env var) |
| **Dependencies** | `authentik-postgresql` (`condition: service_healthy`) |

```yaml
# Environment Configuration (.env)
AUTHENTIK_POSTGRESQL__HOST: authentik-postgresql
AUTHENTIK_POSTGRESQL__NAME: ${PG_DB:-authentik}
AUTHENTIK_POSTGRESQL__USER: ${PG_USER:-authentik}
AUTHENTIK_POSTGRESQL__PASSWORD: [REDACTED_DB_SECRET]
AUTHENTIK_SECRET_KEY: [REDACTED_AUTHENTIK_SECRET_KEY]   # ${AUTHENTIK_SECRET_KEY:?secret key required}
AUTHENTIK_WEB__WORKERS: 2

# Mount Hierarchy
volumes:
  - ${DOCKER_CONFIG_DIR}/authentik/data:/data                          # Media, cache, and app state
  - ${DOCKER_CONFIG_DIR}/authentik/custom-templates:/templates         # Custom branding & HTML
```
* **Glance Metadata:** ID: `authentik`, Name: `Authentik`, Icon: `sh:authentik`, URL: `https://auth.vrg.rocks`, Description: `Identity & SSO Provider`

---

### `authentik-worker`
*Asynchronous task worker for background sync, token issuance, and housekeeping.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `authentik-worker` |
| **Base Image** | `${AUTHENTIK_IMAGE:-ghcr.io/goauthentik/server}:${AUTHENTIK_TAG:-2026.5.3}` |
| **Command** | `worker` |
| **User** | Image default (no `user: root` override) |
| **Docker Socket** | Not mounted. Caddy uses the embedded outpost on `authentik-server:9000`, so root and `/var/run/docker.sock` are omitted to avoid host-root privilege exposure. |
| **Restart Policy** | `unless-stopped` |
| **Shared Memory** | `shm_size: 512mb` (Prevents shared memory exhaustion during background sync tasks) |
| **Dependencies** | `authentik-postgresql` (`condition: service_healthy`) |

```yaml
# Environment Configuration (.env)
AUTHENTIK_POSTGRESQL__HOST: authentik-postgresql
AUTHENTIK_POSTGRESQL__NAME: ${PG_DB:-authentik}
AUTHENTIK_POSTGRESQL__USER: ${PG_USER:-authentik}
AUTHENTIK_POSTGRESQL__PASSWORD: [REDACTED_DB_SECRET]
AUTHENTIK_SECRET_KEY: [REDACTED_AUTHENTIK_SECRET_KEY]

# Mount Hierarchy
volumes:
  - ${DOCKER_CONFIG_DIR}/authentik/data:/data                          # Media & cache
  - ${DOCKER_CONFIG_DIR}/authentik/certs:/certs                        # TLS certificates
  - ${DOCKER_CONFIG_DIR}/authentik/custom-templates:/templates
```
* **Glance Metadata:** Name: `Worker`, Parent: `authentik`

---

### `authentik-postgresql`
*Dedicated relational storage engine for Authentik users, flows, policies, and tokens.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `authentik-postgresql` |
| **Base Image** | `docker.io/library/postgres:16-alpine` |
| **Restart Policy** | `unless-stopped` |
| **Command Tuning** | `shared_buffers=256MB`, `work_mem=16MB`, `effective_cache_size=1GB`, `maintenance_work_mem=64MB`, `wal_buffers=16MB`, `checkpoint_completion_target=0.9` |
| **Healthcheck** | `pg_isready -d $${POSTGRES_DB} -U $${POSTGRES_USER}` (Interval: 30s, Timeout: 5s, Retries: 5, Start Period: 20s) |
| **Internal Port** | `5432/tcp` |

```yaml
# Environment Configuration (.env)
POSTGRES_DB: ${PG_DB:-authentik}
POSTGRES_USER: ${PG_USER:-authentik}
POSTGRES_PASSWORD: [REDACTED_DB_SECRET]   # ${PG_PASS:?database password required}

# Mount Hierarchy
volumes:
  - ${DOCKER_DATA_DIR}/authentik:/var/lib/postgresql/data              # Persistent database cluster
```
* **Backup:** Live cluster excluded from rclone (`data/authentik/**`). Logical dump written by `scripts/backup.sh` to `data/backups/authentik_db.sql.gz`.
* **Glance Metadata:** Name: `PostgreSQL`, Parent: `authentik`

---

### `arcane`
*Modern web-based Docker and compose stack manager with native Authentik OIDC integration.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `arcane` |
| **Base Image** | `ghcr.io/getarcaneapp/arcane:${ARCANE_TAG:-latest}` |
| **Restart Policy** | `unless-stopped` |
| **Internal Port** | `3552/tcp` (Routed via Caddy at `https://arcane.vrg.rocks` with `import forward_auth`) |

```yaml
# Environment Configuration (.env & compose)
APP_URL: "https://arcane.vrg.rocks"
PUID: "501"
PGID: "20"
ENCRYPTION_KEY: [REDACTED_32_BYTE_HEX_KEY]
JWT_SECRET: [REDACTED_32_BYTE_HEX_SECRET]
LOG_LEVEL: "info"
LOG_JSON: "false"
OIDC_ENABLED: "true"
OIDC_CLIENT_ID: [REDACTED_OIDC_CLIENT_ID]
OIDC_CLIENT_SECRET: [REDACTED_OIDC_CLIENT_SECRET]
OIDC_ISSUER_URL: "https://auth.vrg.rocks/application/o/arcane"
OIDC_PROVIDER_NAME: "authentik"          # ${ARCANE_OIDC_PROVIDER_NAME:-authentik}
OIDC_SCOPES: "openid email profile"
OIDC_MERGE_ACCOUNTS: "true"
DATABASE_URL: "file:data/arcane.db?_pragma=journal_mode(WAL)&_pragma=busy_timeout(2500)&_txlock=immediate"

# Mount Hierarchy
volumes:
  - /var/run/docker.sock:/var/run/docker.sock                          # Host Docker daemon management
  - ${DOCKER_DATA_DIR}/arcane:/app/data                                # SQLite database, project files & templates
```
* **Glance Metadata:** ID: `arcane`, Name: `Arcane`, Icon: `sh:arcane`, URL: `https://arcane.vrg.rocks`, Description: `Modern Docker Management`

---

## 2. Dashboard & Metrics

### `glance`
*Lightweight homepage, bookmark hub, and Docker container monitoring dashboard.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `glance` |
| **Base Image** | `glanceapp/glance:latest` |
| **Restart Policy** | `unless-stopped` |
| **Internal Port** | `8080/tcp` (Routed via Caddy at `https://dash.vrg.rocks` with `import forward_auth`) |

```yaml
# Environment Configuration
TZ: ${TZ:-Asia/Kolkata}

# Mount Hierarchy
volumes:
  - ${DOCKER_CONFIG_DIR}/glance/config:/app/config                     # glance.yml configuration file
  - ${DOCKER_CONFIG_DIR}/glance/assets:/app/assets                     # sol.svg branding & icons
  - /var/run/docker.sock:/var/run/docker.sock:ro                       # Read-only container health inspection
  - /etc/localtime:/etc/localtime:ro                                   # Host local time sync
```
* **Glance Metadata:** ID: `glance`, Name: `Glance`, Icon: `sh:glance`, URL: `https://dash.vrg.rocks`, Description: `Sol Server Homepage`
* **Vanity Redirect:** `sol.vrg.rocks` returns `302` to `https://dash.vrg.rocks/sol`.

---

## 3. Media Streaming & Automation Suite

### `jellyfin`
*Central containerized media server for streaming movies, television, and home videos.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `jellyfin` |
| **Base Image** | `lscr.io/linuxserver/jellyfin:latest` |
| **Restart Policy** | `unless-stopped` |
| **Internal Port** | `8096/tcp` (Routed via Caddy at `https://watch.vrg.rocks` and `https://jellyfin.vrg.rocks`, no compression, `read_buffer 32768`, `write_buffer 32768`, `keepalive 120s`) |
| **LAN Fallback Ports**| None published (historic `8096:8096`, `1900/udp` DLNA, `7359/udp` discovery removed from compose) |

```yaml
# Environment Configuration
PUID: "501"
PGID: "20"
TZ: "Asia/Kolkata"

# Mount Hierarchy
volumes:
  - ${DOCKER_CONFIG_DIR}/jellyfin:/config                              # Library database, metadata, plugins
  - ${DOCKER_DATA_DIR}/media:/media/internal                           # Internal fast NVMe/SSD storage
  - ${EXTERNAL_DRIVE_00}:/media/external                               # /Volumes/PANOPTICON
  # - ${EXTERNAL_DRIVE_01}:/media/ext01                                # Commented: /Volumes/PHOENIX
  # - ${EXTERNAL_DRIVE_02}:/media/ext02                                # Commented: undefined in .env.example
```
* **Glance Metadata:** ID: `jellyfin`, Name: `Jellyfin`, Icon: `sh:jellyfin`, URL: `https://watch.vrg.rocks`, Description: `Media Streaming Server`

---

### `jellyfin-metal` (Native macOS)
*Bare-metal macOS Jellyfin instance with Apple VideoToolbox hardware transcoding. Not a container.*

| Specification | Configuration |
| :--- | :--- |
| **Binary** | `/Applications/Jellyfin.app/Contents/MacOS/jellyfin` (bundled `ffmpeg` at `/Applications/Jellyfin.app/Contents/MacOS/ffmpeg`) |
| **Host Port** | `8097` (HTTP), `8921` (HTTPS, written to `network.xml`) |
| **Proxy Route** | `https://metal.vrg.rocks` -> `http://host.docker.internal:8097` (same streaming transport tuning as `watch.vrg.rocks`, no Authentik) |
| **Config Root** | `/Users/vrg/Documents/Sol/config/jellyfin_metal` (`data/`, `cache/`, `log/`) |
| **Bootstrap Script** | `scripts/setup_jellyfin_metal.py` |
| **Registry Entry** | `ports.json` -> `jellyfin-metal` (`status: active`, `category: media`) |

* **Default Launch Mode:** If `config/jellyfin_metal/data/jellyfin.db` exists, the script preserves configuration, users, API keys, and watch history. It only relaunches the native process and polls `/System/Info/Public` for 30 seconds.
* **Destructive Reset:** `shutil.rmtree(CONFIG_DIR)` runs only behind `--reset`. The reset path rewrites `network.xml`, runs the `/Startup/*` wizard (admin `JELLYFIN_ADMIN_USER`, default `VRG`, password from `CORE_PASSWORD` or prompt), and sets VideoToolbox encoding (`HardwareAccelerationType: videotoolbox`, tonemapping, `EnableThrottling: true`, `ThrottleDelaySeconds: 120`, decode `h264`, `hevc`, `vc1`, `vp9`, `av1`, HEVC and AV1 encoding allowed).
* **Reset Path Extras:** Abyss CSS theme, `Movies` and `Shows` libraries (internal `data/media/movies`, `data/media/tv`, plus `/Volumes/PANOPTICON/Movies` and `/Volumes/PANOPTICON/TV Shows` if present), and API keys for `Jellyseerr` and `Bazarr`.
* **Backup Filter:** `config/jellyfin_metal/cache/**` and `config/jellyfin_metal/log/**` are excluded from rclone.

---

### `seerr`
*Request management and media discovery platform for Jellyfin.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `seerr` |
| **Base Image** | `ghcr.io/seerr-team/seerr:latest` |
| **Init Process** | `init: true` |
| **Restart Policy** | `unless-stopped` |
| **DNS Overrides** | `8.8.8.8`, `1.1.1.1` (Prevents ISP DNS filtering on TMDb API endpoints) |
| **Network Aliases**| `jellyseerr` (Internal backward-compatible routing) |
| **Healthcheck** | `wget --no-verbose --tries=1 --spider http://localhost:5055/api/v1/settings/public` (Interval: 15s, Timeout: 3s, Retries: 3, Start Period: 20s) |
| **Internal Port** | `5055/tcp` (Routed via Caddy at `https://request.vrg.rocks`, `https://seerr.vrg.rocks`, and `https://jellyseerr.vrg.rocks`) |

```yaml
# Environment Configuration
TZ: "Asia/Kolkata"
LOG_LEVEL: "info"

# Mount Hierarchy
volumes:
  - ${DOCKER_CONFIG_DIR}/seerr:/app/config                             # SQLite database and settings
```
* **Glance Metadata:** ID: `seerr`, Name: `Seerr`, Icon: `sh:seerr`, URL: `https://request.vrg.rocks`, Description: `Media Requests & Discovery`

---

### `radarr`
*Automated movie collection manager, release monitor, and file renamer.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `radarr` |
| **Base Image** | `lscr.io/linuxserver/radarr:latest` |
| **Restart Policy** | `unless-stopped` |
| **DNS Overrides** | `1.1.1.1` (Cloudflare), `9.9.9.9` (Quad9 fallback) |
| **Internal Port** | `7878/tcp` (Routed via Caddy at `https://radarr.vrg.rocks`) |

```yaml
# Environment Configuration
PUID: "501"
PGID: "20"
TZ: "Asia/Kolkata"

# Mount Hierarchy
volumes:
  - ${DOCKER_CONFIG_DIR}/radarr:/config                                # Application DB and XML configs
  - ${DOCKER_DATA_DIR}:/data                                           # Unified root mount for zero-copy APFS atomic hardlinks
  - ${EXTERNAL_DRIVE_00}:/external                                     # External bulk movie repository
  # - ${EXTERNAL_DRIVE_01}:/ext01                                      # Commented
```
* **Glance Metadata:** ID: `radarr`, Name: `Radarr`, Icon: `sh:radarr`, URL: `https://radarr.vrg.rocks`, Description: `Movie Collection Manager`

---

### `sonarr`
*Automated television series tracker, episode monitor, and file renamer.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `sonarr` |
| **Base Image** | `lscr.io/linuxserver/sonarr:latest` |
| **Restart Policy** | `unless-stopped` |
| **DNS Overrides** | `1.1.1.1`, `9.9.9.9` |
| **Internal Port** | `8989/tcp` (Routed via Caddy at `https://sonarr.vrg.rocks`) |

```yaml
# Environment Configuration
PUID: "501"
PGID: "20"
TZ: "Asia/Kolkata"

# Mount Hierarchy
volumes:
  - ${DOCKER_CONFIG_DIR}/sonarr:/config                                # Application DB and series metadata
  - ${DOCKER_DATA_DIR}:/data                                           # Unified data root for hardlinks
  - ${EXTERNAL_DRIVE_00}:/external                                     # External TV series root
  # - ${EXTERNAL_DRIVE_01}:/ext01                                      # Commented
```
* **Glance Metadata:** ID: `sonarr`, Name: `Sonarr`, Icon: `sh:sonarr`, URL: `https://sonarr.vrg.rocks`, Description: `TV Series Tracker & Downloader`

---

### `bazarr`
*Companion subtitle automation manager for Radarr and Sonarr.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `bazarr` |
| **Base Image** | `lscr.io/linuxserver/bazarr:latest` |
| **Restart Policy** | `unless-stopped` |
| **DNS Overrides** | `1.1.1.1`, `9.9.9.9` |
| **Internal Port** | `6767/tcp` (Routed via Caddy at `https://bazarr.vrg.rocks`) |

```yaml
# Environment Configuration
PUID: "501"
PGID: "20"
TZ: "Asia/Kolkata"

# Mount Hierarchy
volumes:
  - ${DOCKER_CONFIG_DIR}/bazarr:/config                                # Subtitle provider state & database
  - ${DOCKER_DATA_DIR}:/data                                           # Internal media library access
  - ${EXTERNAL_DRIVE_00}:/external                                     # External media library access
  # - ${EXTERNAL_DRIVE_01}:/ext01                                      # Commented
```
* **Glance Metadata:** ID: `bazarr`, Name: `Bazarr`, Icon: `sh:bazarr`, URL: `https://bazarr.vrg.rocks`, Description: `Subtitle Search & Sync`

---

### `lidarr`
*Automated music library manager and discography tracker.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `lidarr` |
| **Base Image** | `lscr.io/linuxserver/lidarr:latest` |
| **Restart Policy** | `unless-stopped` |
| **DNS Overrides** | `1.1.1.1`, `9.9.9.9` |
| **Internal Port** | `8686/tcp` (Routed via Caddy at `https://lidarr.vrg.rocks`) |

```yaml
# Environment Configuration
PUID: "501"
PGID: "20"
TZ: "Asia/Kolkata"

# Mount Hierarchy
volumes:
  - ${DOCKER_CONFIG_DIR}/lidarr:/config                                # Artist DB and settings
  - ${DOCKER_DATA_DIR}:/data                                           # Music directory & torrents
  - ${EXTERNAL_DRIVE_00}:/external                                     # External music archive
  # - ${EXTERNAL_DRIVE_01}:/ext01                                      # Commented
```
* **Glance Metadata:** ID: `lidarr`, Name: `Lidarr`, Icon: `sh:lidarr`, URL: `https://lidarr.vrg.rocks`, Description: `Music Discography Manager`

---

### `prowlarr`
*Centralized indexer management proxy for Usenet and BitTorrent trackers.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `prowlarr` |
| **Base Image** | `lscr.io/linuxserver/prowlarr:latest` |
| **Restart Policy** | `unless-stopped` |
| **DNS Overrides** | `1.1.1.1`, `9.9.9.9` (Bypasses ISP-level torrent site blocks and timeouts) |
| **Internal Port** | `9696/tcp` (Routed via Caddy at `https://prowlarr.vrg.rocks`) |
| **Challenge Solver** | `http://flaresolverr:8191`, which resolves to `byparr` through its network alias |

```yaml
# Environment Configuration
PUID: "501"
PGID: "20"
TZ: "Asia/Kolkata"

# Mount Hierarchy
volumes:
  - ${DOCKER_CONFIG_DIR}/prowlarr:/config                              # Tracker definitions and API keys
```
* **Glance Metadata:** ID: `prowlarr`, Name: `Prowlarr`, Icon: `sh:prowlarr`, URL: `https://prowlarr.vrg.rocks`, Description: `Torrent & Usenet Indexer Proxy`

---

### `byparr`
*Active Cloudflare Turnstile bypass service for Prowlarr. Drop-in replacement for FlareSolverr on port `8191`.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `byparr` |
| **Base Image** | `ghcr.io/thephaseless/byparr:latest` |
| **Restart Policy** | `unless-stopped` |
| **DNS Overrides** | `1.1.1.1`, `9.9.9.9` |
| **Network Aliases** | `flaresolverr` (existing Prowlarr indexer proxy settings work with zero changes) |
| **Internal Port** | `8191/tcp` (Prowlarr calls `http://flaresolverr:8191`. Caddy routes `https://byparr.vrg.rocks` and `https://flaresolverr.vrg.rocks` with `import forward_auth`.) |

```yaml
# Environment Configuration
TZ: "Asia/Kolkata"
LOG_LEVEL: "info"
```
* **Glance Metadata:** ID: `byparr`, Name: `Byparr`, Icon: `sh:flaresolverr`, URL: `https://byparr.vrg.rocks`, Description: `Cloudflare Turnstile Solver`

---

## 4. Download & Cross-Seeding Pipeline

### `qbittorrent`
*Primary BitTorrent download client with Web UI management and dedicated WAN peer listening.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `qbittorrent` |
| **Base Image** | `lscr.io/linuxserver/qbittorrent:latest` |
| **Restart Policy** | `unless-stopped` |
| **Host Ports** | `${QBITTORRENT_TORRENTING_PORT:-42069}` TCP and UDP (`42069:42069`, `42069:42069/udp`) |
| **DNS Overrides** | `1.1.1.1`, `9.9.9.9` (Fast tracker announces) |
| **Internal Web Port**| `${QBITTORRENT_WEBUI_PORT:-8080}/tcp` (Routed via Caddy at `https://qb.vrg.rocks` and `https://qbittorrent.vrg.rocks`) |
| **Edge Auth** | qBittorrent Native Auth only. `import forward_auth` is intentionally omitted so the Android mobile torrent client can connect directly to `qb.vrg.rocks`. |

```yaml
# Environment Configuration (.env)
PUID: "501"
PGID: "20"
TZ: "Asia/Kolkata"
WEBUI_PORT: "8080"
TORRENTING_PORT: "42069"

# Mount Hierarchy
volumes:
  - ${DOCKER_CONFIG_DIR}/qbittorrent:/config                           # qBittorrent.conf, scripts, fastresume
  - ${DOCKER_DATA_DIR}/torrents:/downloads                             # Current torrent payload destination
  - ${DOCKER_DATA_DIR}:/data                                           # Unified root staged alongside /downloads for zero-copy migration
  - ${EXTERNAL_DRIVE_00}:/external                                     # External seed directory
  # - ${EXTERNAL_DRIVE_01}:/ext01                                      # Commented
```
* **Dual Mount Staging:** `/downloads` and `/data/torrents` point to the same host directory. Save paths can move from `/downloads/...` to `/data/torrents/...` per torrent with no data copy and no downtime.
* **Post-Download Automation:** Runs `/config/scripts/ntfy_notify.sh` to broadcast download completion to ntfy topic `qBittorrent`.
* **Glance Metadata:** ID: `qbittorrent`, Name: `qBittorrent`, Icon: `sh:qbittorrent`, URL: `https://qb.vrg.rocks`, Description: `BitTorrent Client`

---

### `cross-seed`
*Automated cross-seeding daemon that searches Prowlarr Torznab endpoints and injects matches through symlinks.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `cross-seed` |
| **Base Image** | `ghcr.io/cross-seed/cross-seed:6` |
| **Command** | `daemon` |
| **User** | `501:20` (`${PUID}:${PGID}`) |
| **Restart Policy** | `unless-stopped` |
| **DNS Overrides** | `1.1.1.1`, `9.9.9.9` |
| **Internal Port** | `2468/tcp` (Routed via Caddy at `https://cs.vrg.rocks`) |

```yaml
# Mount Hierarchy
volumes:
  - ${DOCKER_CONFIG_DIR}/cross-seed:/config                            # config.js, cross-seed.db (SQLite)
  - ${DOCKER_DATA_DIR}/torrents:/downloads                             # Internal downloads (current linkDirs root)
  - ${DOCKER_DATA_DIR}:/data                                           # Exposes /data/torrents and /data/media for library-wide dataDirs scanning
  - ${EXTERNAL_DRIVE_00}:/external                                     # External downloads
  # - ${EXTERNAL_DRIVE_01}:/ext01                                      # Commented
```
* **Operational Mode:** `matchMode: "partial"`, `linkType: "symlink"`, `linkDirs: ["/downloads/cross-seed-links", "/external/cross-seed-links"]`, `action: "inject"`.
* **Dual Mount Staging:** Same layout as `qbittorrent`, staged for migration to unified `/data/torrents`.
* **Diagnostics:** `scripts/test_cross_seed.sh` runs `docker exec -u "${PUID:-501}:${PGID:-20}" cross-seed` to test write access and hardlinks on `/external`, `/downloads`, and `/data/torrents` <-> `/data/media` as the unprivileged user.
* **Glance Metadata:** ID: `cross-seed`, Name: `Cross-Seed`, Icon: `sh:cross-seed`, URL: `https://cs.vrg.rocks`, Description: `Automated Cross-Seeding Daemon`

---

## 5. Document Management & OCR Archival

### `paperless-webserver`
*Document management system with OCR, tagging, automated consumption, and OIDC authentication.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `paperless-webserver` |
| **Base Image** | `ghcr.io/paperless-ngx/paperless-ngx:${PAPERLESS_TAG:-2}` |
| **Restart Policy** | `unless-stopped` |
| **Internal Port** | `8000/tcp` (Routed via Caddy at `https://docs.vrg.rocks` and `https://paperless.vrg.rocks`, native OIDC, no `import forward_auth`) |
| **Dependencies** | `paperless-db` (`condition: service_healthy`), `paperless-broker` (`condition: service_healthy`). `paperless-gotenberg` and `paperless-tika` dependencies are commented. |
| **Concurrency** | `PAPERLESS_TASK_WORKERS: 2`, `PAPERLESS_THREADS_PER_WORKER: 2` (M1 Pro: 6 Performance + 2 Efficiency cores) |

```yaml
# Environment Configuration (.env & compose)
USERMAP_UID: "501"                     # ${USERMAP_UID:-501}
USERMAP_GID: "20"                      # ${USERMAP_GID:-20}
PAPERLESS_URL: "https://docs.vrg.rocks"
PAPERLESS_SECRET_KEY: [REDACTED_PAPERLESS_SECRET_KEY]
PAPERLESS_TIME_ZONE: "Asia/Kolkata"
PAPERLESS_OCR_LANGUAGE: "eng"
PAPERLESS_OCR_LANGUAGES: "hin kan pan"
PAPERLESS_CONSUMER_RECURSIVE: "true"
PAPERLESS_CONSUMER_SUBDIRS_AS_TAGS: "true"
PAPERLESS_FILENAME_DATE_ORDER: "YMD"
PAPERLESS_REDIS: "redis://paperless-broker:6379"
PAPERLESS_DBHOST: "paperless-db"
PAPERLESS_DBNAME: "paperless"          # ${PAPERLESS_DB_NAME:-paperless}
PAPERLESS_DBUSER: "paperless"          # ${PAPERLESS_DB_USER:-paperless}
PAPERLESS_DBPASS: [REDACTED_DB_PASSWORD]   # ${PAPERLESS_DB_PASS:-paperless}
PAPERLESS_TASK_WORKERS: 2
PAPERLESS_THREADS_PER_WORKER: 2
PAPERLESS_PRE_CONSUME_SCRIPT: "/usr/src/paperless/scripts/pre-consumption.py"
PAPERLESS_POST_CONSUME_SCRIPT: "/usr/src/paperless/scripts/ntfy_notify.sh"
PAPERLESS_APPS: "allauth.socialaccount.providers.openid_connect"
PAPERLESS_SOCIALACCOUNT_PROVIDERS: [REDACTED_AUTHENTIK_OIDC_PAYLOAD]   # single-quoted JSON in .env.example
PAPERLESS_LOGOUT_REDIRECT_URL: "https://auth.vrg.rocks/application/o/paperless-ngx/end-session/"
# PAPERLESS_TIKA_ENABLED: 1                                            # Commented (standby)
# PAPERLESS_TIKA_GOTENBERG_ENDPOINT: http://paperless-gotenberg:3000   # Commented (standby)
# PAPERLESS_TIKA_ENDPOINT: http://paperless-tika:9998                  # Commented (standby)

# Mount Hierarchy
volumes:
  - ${DOCKER_CONFIG_DIR}/paperless:/usr/src/paperless/config
  - ${DOCKER_DATA_DIR}/paperless/data:/usr/src/paperless/data
  - ${DOCKER_DATA_DIR}/paperless/media:/usr/src/paperless/media
  - ${DOCKER_DATA_DIR}/paperless/export:/usr/src/paperless/export
  - ${DOCKER_DATA_DIR}/paperless/consume:/usr/src/paperless/consume
  - ${DOCKER_DATA_DIR}/paperless/scripts:/usr/src/paperless/scripts
```
* **Glance Metadata:** ID: `paperless`, Name: `Paperless`, Icon: `sh:paperless-ngx`, URL: `https://docs.vrg.rocks`, Description: `Document Archival & OCR Engine`

---

### `paperless-broker`
*Redis instance that handles Paperless task queues and Celery worker jobs.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `paperless-broker` |
| **Base Image** | `docker.io/library/redis:8-alpine` |
| **Restart Policy** | `unless-stopped` |
| **Healthcheck** | `redis-cli ping` (Interval: 10s, Timeout: 5s, Retries: 5) |
| **Internal Port** | `6379/tcp` |

```yaml
# Mount Hierarchy
volumes:
  - ${DOCKER_DATA_DIR}/paperless/redis:/data
```
* **Backup:** Excluded from rclone (`data/paperless/redis/**`).
* **Glance Metadata:** Name: `Redis Queue`, Parent: `paperless`

---

### `paperless-db`
*PostgreSQL 17 database cluster storing metadata, OCR indexes, correspondents, and document tags.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `paperless-db` |
| **Base Image** | `docker.io/library/postgres:17` (Debian, `glibc`) |
| **Image Rationale** | Retained on Debian `postgres:17` rather than `postgres:17-alpine` (`musl`) to keep C-library collation compatibility with the existing `data/paperless/db` cluster. The `pg_dump` / `pg_restore` Alpine migration is documented as an optional local trial in `TODO.md` and `docs/FLASH_LOCAL_VERIFICATION_RUNBOOK.md`. |
| **Restart Policy** | `unless-stopped` |
| **Command Tuning** | `shared_buffers=256MB`, `work_mem=16MB`, `effective_cache_size=1GB`, `maintenance_work_mem=64MB`, `wal_buffers=16MB`, `checkpoint_completion_target=0.9` |
| **Healthcheck** | `pg_isready -d ${PAPERLESS_DB_NAME:-paperless} -U ${PAPERLESS_DB_USER:-paperless}` (Interval: 10s, Timeout: 5s, Retries: 5) |
| **Internal Port** | `5432/tcp` |

```yaml
# Environment Configuration
POSTGRES_DB: "paperless"               # ${PAPERLESS_DB_NAME:-paperless}
POSTGRES_USER: "paperless"             # ${PAPERLESS_DB_USER:-paperless}
POSTGRES_PASSWORD: [REDACTED_DB_PASSWORD]   # ${PAPERLESS_DB_PASS:-paperless}

# Mount Hierarchy
volumes:
  - ${DOCKER_DATA_DIR}/paperless/db:/var/lib/postgresql/data
```
* **Backup:** Live cluster excluded from rclone (`data/paperless/db/**`). Logical dump written to `data/backups/paperless_db.sql.gz`.
* **Glance Metadata:** Name: `PostgreSQL`, Parent: `paperless`

---

### `ignis`
*Obsidian vault manager and web synchronizer for digital notes and markdown graphs.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `ignis` |
| **Base Image** | `nobbe/ignis:latest` |
| **Restart Policy** | `unless-stopped` |
| **Internal Port** | `8080/tcp` (Routed via Caddy at `https://ignis.vrg.rocks`) |
| **Compose File** | `compose/knowledge.yml` |

```yaml
# Environment Configuration
PUID: "501"
PGID: "20"

# Mount Hierarchy
volumes:
  - ${DOCKER_DATA_DIR}/ignis/vaults:/vaults
  - ${DOCKER_DATA_DIR}/ignis/data:/app/data
  - ${DOCKER_DATA_DIR}/ignis/obsidian:/app/obsidian-app
```
* **Glance Metadata:** ID: `ignis`, Name: `Ignis`, Icon: `sh:obsidian`, URL: `https://ignis.vrg.rocks`, Description: `Obsidian Vault Synchronization`

---

## 6. Developer Workspaces, Logistics & Utilities

### `code-server`
*Browser-accessible VS Code IDE running on the server filesystem.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `code-server` |
| **Base Image** | `lscr.io/linuxserver/code-server:latest` |
| **Restart Policy** | `unless-stopped` |
| **Internal Port** | `8443/tcp` (Routed via Caddy at `https://code.vrg.rocks`) |
| **Edge Auth** | `import forward_auth` at Caddy, then code-server `AUTH: password` (Argon2 hash) |

```yaml
# Environment Configuration (.env)
PUID: "501"
PGID: "20"
TZ: "Asia/Kolkata"
AUTH: "password"
HASHED_PASSWORD: [REDACTED_ARGON2_HASH]
PROXY_DOMAIN: "code.vrg.rocks"
PWA_APPNAME: "VRGCode"

# Mount Hierarchy
volumes:
  - ${DOCKER_CONFIG_DIR}/code-server:/config                           # Extensions, keybindings, history
  - ${DOCKER_BASE_DIR}:/Server                                         # Entire Sol repository root
  - /Users/vrg/Documents:/Documents                                    # Host Documents tree (static absolute path)
```
* **Glance Metadata:** ID: `code-server`, Name: `Code Server`, Icon: `sh:visual-studio-code`, URL: `https://code.vrg.rocks`, Description: `Browser VS Code IDE`

---

### `coder`
*Cloud development environment platform that creates on-demand Docker workspaces from Terraform.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `coder` |
| **Base Image** | `ghcr.io/coder/coder:${CODER_TAG:-latest}` |
| **Restart Policy** | `unless-stopped` |
| **Group Add** | `20` (`${PGID}`) |
| **Internal Port** | `7080/tcp` (Routed via Caddy at `https://coder.vrg.rocks` with `import forward_auth`) |
| **Template** | `coder/main.tf` only. `coder/default.tf` is removed, which eliminates duplicate Terraform resource definitions. |

```yaml
# Environment Configuration
CODER_ACCESS_URL: ${CODER_ACCESS_URL:-https://coder.vrg.rocks}

# Mount Hierarchy
volumes:
  - /var/run/docker.sock:/var/run/docker.sock                          # Provisioning dynamic container workspaces
  - ${DOCKER_CONFIG_DIR}/coder:/home/coder/.config                     # Coder configuration & embedded state
  - ${DOCKER_BASE_DIR}:/Sol                                            # Workspace source tree mount
```
* **Workspace Template (`coder/main.tf`):** Providers `coder/coder` and `kreuzwerker/docker`. Image `codercom/enterprise-base:ubuntu`. Home volume `coder-<workspace_id>-home` (`ignore_changes = all`). `host.docker.internal` mapped to `host-gateway`. `code-server` module `registry.coder.com/coder/code-server/coder` `~> 1.0`.
* **Startup Script:** Installs `curl unzip git tar` through `apt-get` (no Rust toolchain), installs Bun from `https://bun.sh/install`, and downloads prebuilt `jj` `v0.28.2` (`aarch64-unknown-linux-musl` or `x86_64-unknown-linux-musl`) into `~/.local/bin`.
* **Agent Metadata:** CPU, RAM, Home Disk, Host CPU, Host Memory, Host Load Average, Host Swap.
* **Glance Metadata:** ID: `coder`, Name: `Coder`, Icon: `sh:visual-studio-code`, URL: `https://coder.vrg.rocks`, Description: `Cloud Development Environments`

---

### `copyparty`
*High-speed file server, WebDAV provider, and multimedia browser with granular ACL permissions.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `copyparty` |
| **Base Image** | `copyparty/ac:latest` |
| **User** | `501:20` (`${PUID}:${PGID}`) |
| **Restart Policy** | `unless-stopped` |
| **Stop Grace Period**| `15s` (Allows thumbnailer subprocesses to finish safely) |
| **Healthcheck** | `wget --spider -q 127.0.0.1:3923/?reset=/._` (Interval: 1m, Timeout: 2s, Retries: 5, Start: 15s) |
| **Internal Port** | `3923/tcp` (Routed via Caddy at `https://files.vrg.rocks` and `https://copyparty.vrg.rocks`) |

```yaml
# Environment Configuration
LD_PRELOAD: "/usr/lib/libmimalloc-secure.so.NOPE"
PYTHONUNBUFFERED: "1"

# Mount Hierarchy
volumes:
  - ${DOCKER_CONFIG_DIR}/copyparty:/cfg                                # copyparty.conf, salts & sessions DB
  - ${DOCKER_DATA_DIR}/copyparty:/w/copyparty                          # Shared uploads root
  - ${DOCKER_DATA_DIR}/media:/w/media                                  # Internal media directories
  - ${DOCKER_DATA_DIR}/torrents:/w/torrents                            # Internal torrent directories
  - ${EXTERNAL_DRIVE_00}:/w/external                                   # External hard drive storage
  # - ${EXTERNAL_DRIVE_01}:/w/ext01                                    # Commented
```
* **Configured Endpoints (`copyparty.conf`):** Webroot `/`, Private vault `/priv`, listening internally on ports 3923, 8086, 3939.
* **Glance Metadata:** ID: `copyparty`, Name: `Copyparty`, Icon: `sh:copyparty`, URL: `https://files.vrg.rocks`, Description: `File Server & WebDAV`

---

### `ntfy`
*Self-hosted HTTP-based publish-subscribe push notification service.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `ntfy` |
| **Base Image** | `binwiederhier/ntfy:latest` |
| **Command** | `serve` |
| **Init** | `true` (Enables tini init for signal reaping) |
| **User** | `501:20` (`${PUID}:${PGID}`) |
| **Restart Policy** | `unless-stopped` |
| **Healthcheck** | `wget -q --tries=1 http://localhost:80/v1/health -O - \| grep -Eo '"healthy"\s*:\s*true' \|\| exit 1` (Interval: 60s, Timeout: 10s, Retries: 3, Start: 40s) |
| **Internal Port** | `80/tcp` (Routed via Caddy at `https://ntfy.vrg.rocks`, no Authentik) |

```yaml
# Environment Configuration
TZ: "Asia/Kolkata"

# Mount Hierarchy
volumes:
  - ${DOCKER_DATA_DIR}/ntfy/var/cache/ntfy:/var/cache/ntfy             # Message queue cache & attachments
  - ${DOCKER_CONFIG_DIR}/ntfy/etc/ntfy:/etc/ntfy                       # server.yml configuration
```
* **Glance Metadata:** ID: `ntfy`, Name: `ntfy`, Icon: `sh:ntfy`, URL: `https://ntfy.vrg.rocks`, Description: `Push Notification Service`

---

## 7. Static Web Applications (Caddy Served)

These frontends do not run as standalone containers. They are mounted read-only into the `caddy` container and served through the `(static_site)` snippet (`optimize`, `security_headers`, `try_files {path} {path}.html {path}/ =404`, `file_server`, and `handle_errors` rewrite to `/{err.status_code}.html`).

### Quartz Digital Garden (`Quettamind`)
* **FQDN / Proxy Route:** `https://mind.vrg.rocks`
* **Host Source Directory:** `${DOCKER_BASE_DIR}/quartz/public`
* **Container Mount:** `/mind:ro`
* **Authentication:** Authentik Forward Auth (`import forward_auth`)
* **Routing Logic:** `try_files {path} {path}.html {path}/ =404` with custom 404 rewrite `/{err.status_code}.html`.

### Family Data Vault
* **FQDN / Proxy Route:** `https://fam.vrg.rocks`
* **Host Source Directory:** `${DOCKER_BASE_DIR}/web/fam` (pre-refactor path `/Users/vrg/Documents/Sol/vault` is retired)
* **Container Mount:** `/fam:ro`
* **Authentication:** Authentik Forward Auth (`import forward_auth`)
* **Routing Logic:** `try_files {path} {path}.html {path}/ =404` with custom error handler.

### Homebox Barcode Scanner PWA
* **FQDN / Proxy Route:** `https://scan.vrg.rocks`
* **Host Source Directory:** `${DOCKER_BASE_DIR}/web/scan` (pre-refactor path `/Users/vrg/Documents/Sol/scan` is retired)
* **Container Mount:** `/scan:ro`
* **Authentication:** Authentik Forward Auth (`import forward_auth`)
* **Routing Logic:** PWA manifest with `index.html`, `scanner.html`, `queue.html`, `settings.html`.
* **Backend Dependency:** Calls `https://inv.vrg.rocks` (Homebox). Homebox is in standby, so scanner API lookups fail until Homebox and its vhost are restored.

### Async Bookmark Manager
* **FQDN / Proxy Route:** `https://aysynbm.vrg.rocks`
* **Host Source Directory:** `${DOCKER_BASE_DIR}/web/aysynbm` (pre-refactor path `/Users/vrg/Documents/Sol/aysynbm` is retired)
* **Container Mount:** `/aysynbm:ro`
* **Authentication:** Direct static access with compression (no `import forward_auth`)
* **Routing Logic:** `try_files {path} {path}.html {path}/ =404`.

---

## 8. Standby & Ops Profile Registry

Standby services are full service blocks with `profiles: ["standby"]`. `docker compose up -d` skips them. Start one with `docker compose --profile standby up -d <service>`, then uncomment its vhost in `Caddyfile` if it has one. Full rationale and reactivation recipes live in [04_INACTIVE_AND_LEGACY_REGISTRY.md](04_INACTIVE_AND_LEGACY_REGISTRY.md).

| Service | Compose File | Image | Profile(s) | Internal Port | Caddy Vhost |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `flaresolverr` | `media.yml` | `ghcr.io/flaresolverr/flaresolverr:latest` | `standby` | `8191` | Served by `byparr` |
| `recyclarr` | `media.yml` | `ghcr.io/recyclarr/recyclarr:latest` | `standby` | N/A (`CRON_SCHEDULE: "@daily"`) | None |
| `wizarr` | `media.yml` | `ghcr.io/wizarrrr/wizarr:latest` | `standby` | `5690` | `wizarr.vrg.rocks` (commented) |
| `unpackerr` | `download.yml` | `golift/unpackerr:latest` | `standby` | N/A | None |
| `qbit_manage` | `download.yml` | `ghcr.io/stuffanthings/qbit_manage:latest` | `standby` | `8181` | `qbm.vrg.rocks`, `qbit_manage.vrg.rocks` (commented) |
| `flood` | `download.yml` | `jesec/flood:latest` | `standby` | `3000` | `flood.vrg.rocks` (commented) |
| `paperless-gotenberg` | `paperless.yml` | `docker.io/gotenberg/gotenberg:8.20` | `standby` | `3000` | None |
| `paperless-tika` | `paperless.yml` | `docker.io/apache/tika:latest` | `standby` | `9998` | None |
| `paperless-ai` | `paperless.yml` | `clusterzx/paperless-ai:latest` | `standby` | `3000` | `paperless-ai.vrg.rocks` (commented) |
| `gatus` | `monitoring.yml` | `twinproduction/gatus:latest` | `standby` | `8080` | `status.vrg.rocks` (commented) |
| `dozzle` | `monitoring.yml` | `amir20/dozzle:latest` | `standby` | `8080` | `dozzle.vrg.rocks` (commented) |
| `beszel` | `monitoring.yml` | `henrygd/beszel:latest` | `standby` | `8090` | `beszel.vrg.rocks` (commented) |
| `beszel-agent` | `monitoring.yml` | `henrygd/beszel-agent:latest` | `standby` | `45876` (host network) | None |
| `dockge` | `monitoring.yml` | `louislam/dockge:1` | `standby` | `5001` | `dockge.vrg.rocks` (commented) |
| `uptime-kuma` | `monitoring.yml` | `louislam/uptime-kuma:1` | `standby` | `3001` | `kuma.vrg.rocks` (commented) |
| `homarr` | `monitoring.yml` | `ghcr.io/homarr-labs/homarr:latest` | `standby` | `7575` | `homarr.vrg.rocks` (commented) |
| `leafwiki` | `knowledge.yml` | `ghcr.io/perber/leafwiki:latest` | `standby` | `8080` | `leaf.vrg.rocks` (commented) |
| `kavita` | `knowledge.yml` | `lscr.io/linuxserver/kavita:latest` | `standby` | `5000` | `kavita.vrg.rocks` (commented) |
| `calibre` | `knowledge.yml` | `lscr.io/linuxserver/calibre:latest` | `standby` | `8080` | `calibre.vrg.rocks` (commented) |
| `calibre-web` | `knowledge.yml` | `lscr.io/linuxserver/calibre-web:latest` | `standby` | `8083` | `calibre-web.vrg.rocks` (commented) |
| `homebox` | `utilities.yml` | `ghcr.io/sysadminsmedia/homebox:latest` | `standby` | `7745` | `inv.vrg.rocks` (commented) |
| `vaultwarden` | `utilities.yml` | `vaultwarden/server:latest` | `standby` | `80` | `vault.vrg.rocks`, `pass.vrg.rocks` (commented) |
| `n8n` | `utilities.yml` | `docker.n8n.io/n8nio/n8n` | `standby` | `5678` | `n8n.vrg.rocks` (commented) |
| `homeassistant` | `utilities.yml` | `ghcr.io/home-assistant/home-assistant:stable` | `standby` | `8123` (host network, `privileged: true`) | `home.vrg.rocks` (active, upstream `host.docker.internal:8123`) |
| `rclone` | `utilities.yml` | `rclone/rclone:latest` | `ops`, `standby` | `127.0.0.1:53682` | None |
| `rclone-gui` | `utilities.yml` | `rclone/rclone:latest` | `standby` | `5572` | `rclone.vrg.rocks` (commented) |

### `homebox` (Standby)
*Asset and physical home inventory tracking database. Moved to standby pending local SQLite database repair.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `homebox` |
| **Base Image** | `ghcr.io/sysadminsmedia/homebox:latest` |
| **Profile** | `standby` (`compose/utilities.yml`) |
| **Restart Policy** | `unless-stopped` |
| **Internal Port** | `7745/tcp` (`inv.vrg.rocks` vhost commented out in `Caddyfile`) |
| **CORS Policy** | Restricted to `Origin https://scan.vrg.rocks` with `Vary Origin` and `204` preflight. Wildcard origin reflection is removed. |
| **Registry Entry** | `ports.json` -> `homebox` (`status: standby`, `profile: standby`) |

```yaml
# Environment Configuration
HBOX_LOG_LEVEL: "info"
HBOX_LOG_FORMAT: "text"
HBOX_WEB_MAX_FILE_UPLOAD: "10"
HBOX_OPTIONS_ALLOW_ANALYTICS: "false"

# Mount Hierarchy
volumes:
  - ${DOCKER_DATA_DIR}/homebox:/data/                                  # SQLite database (homebox.db) & item photos
```
* **Glance Metadata:** ID: `homebox`, Name: `Homebox`, Icon: `sh:homebox`, URL: `https://inv.vrg.rocks`, Description: `Home Inventory Management (Standby - Pending DB Repair)`

### `flaresolverr` (Standby)
*Legacy Cloudflare challenge solver, preserved as a fallback for `byparr`.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `flaresolverr` |
| **Base Image** | `ghcr.io/flaresolverr/flaresolverr:latest` |
| **Profile** | `standby` (`compose/media.yml`) |
| **Restart Policy** | `unless-stopped` |
| **DNS Overrides** | `1.1.1.1`, `9.9.9.9` |
| **Internal Port** | `8191/tcp` |

```yaml
# Environment Configuration
TZ: "Asia/Kolkata"
LOG_LEVEL: "info"
```
* **Alias Collision Warning:** `byparr` already answers to the network alias `flaresolverr`. If both run, Docker DNS returns two addresses for `flaresolverr`. Stop `byparr` before you start this container as a fallback.
* **Glance Metadata:** ID: `flaresolverr`, Name: `FlareSolverr`, Icon: `sh:flaresolverr`, URL: `https://flaresolverr.vrg.rocks`, Description: `Legacy Cloudflare Challenge Solver (Standby)`

---

## 9. Maintenance Scripts & Terraform

| Path | Purpose | Key Safety Behavior |
| :--- | :--- | :--- |
| `scripts/backup.sh` | PostgreSQL dumps (`authentik_db.sql.gz`, `paperless_db.sql.gz`), atomic online SQLite `.backup` snapshots to `data/backups/sqlite/`, then `rclone sync . OneDrive:Sol` | `set -euo pipefail`, safe `load_env` `.env` parser (no raw `source`), `.tmp` dump then `mv`, `--backup-dir OneDrive:Sol-archive/<TIMESTAMP>`, host rclone with `docker compose --profile ops run --rm rclone` fallback, 30-day log pruning |
| `scripts/restore.sh` | Pull `OneDrive:Sol`, rebuild directory tree, restore missing SQLite snapshots, import PostgreSQL dumps | Flags `--dry-run`, `--skip-cloud-pull`, `--restore-dbs`, `--start-stack`. Imports with `gunzip -c ... \| docker exec -i <db> psql`. Bash 3.2 `set -u` safe array expansion `${arr[@]+"${arr[@]}"}`. Validates `docker compose -f docker-compose.yml config`. |
| `scripts/setup_jellyfin_metal.py` | Launch or bootstrap native Jellyfin Metal on `8097` | `shutil.rmtree(CONFIG_DIR)` only behind `--reset`. Default mode preserves `jellyfin.db`. |
| `scripts/test_cross_seed.sh` | Permission and hardlink diagnostic inside `cross-seed` | Runs `docker exec -u "${PUID:-501}:${PGID:-20}"` instead of root. Uses safe `load_env`. |
| `coder/main.tf` | Single Coder v2 Docker workspace template | `coder/default.tf` removed. Prebuilt `jj` `v0.28.2` musl download replaces `cargo install`. |
