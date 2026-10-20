# 01. Service Catalog & Specification Registry

> **Scope:** Complete specification breakdown of all **29 active containers (`29/29 healthy`)**, the **16 standby/ops containers** managed through Docker Compose V2 profiles, the **10 Caddy-served static web applications**, the standby native `jellyfin-metal` specification, and the operational automation scripts/LaunchAgents on `Sol`.  
> **Host Environment:** macOS (OrbStack / Docker Engine), Apple Silicon M1 Pro (`16 GB` unified memory)  
> **Environment Variables File:** `.env` (single source, template `.env.example`).  
> **Path Variables:** `DOCKER_BASE_DIR=/Users/vrg/Documents/Sol`, `DOCKER_CONFIG_DIR=${DOCKER_BASE_DIR}/config`, `DOCKER_DATA_DIR=${DOCKER_BASE_DIR}/data`, `DOCKER_LOGS_DIR=${DOCKER_BASE_DIR}/logs`, `EXTERNAL_DRIVE_00=/Volumes/PANOPTICON`, `EXTERNAL_DRIVE_01=/Volumes/PHOENIX`  
> **Security Notice:** All passwords, tokens, private keys, and encryption secrets are sanitized and redacted.  
> **Last Synced to Ground Truth:** 2026-10-20  

---

## Table of Contents
1. [Core Infrastructure & Identity Spine (`compose/core.yml`)](#1-core-infrastructure--identity-spine-composecoreyml)
   - [`caddy`](#caddy)
   - [`tinyauth`](#tinyauth)
   - [`lldap`](#lldap)
   - [`arcane`](#arcane)
2. [Dashboard & Monitoring (`compose/monitoring.yml`)](#2-dashboard--monitoring-composemonitoringyml)
   - [`glance`](#glance)
3. [Media Streaming & *arr PVR Suite (`compose/media.yml`)](#3-media-streaming--arr-pvr-suite-composemediayml)
   - [`jellyfin`](#jellyfin)
   - [`seerr`](#seerr)
   - [`radarr`](#radarr)
   - [`sonarr`](#sonarr)
   - [`bazarr`](#bazarr)
   - [`lidarr`](#lidarr)
   - [`prowlarr`](#prowlarr)
   - [`byparr`](#byparr)
4. [Download, Cross-Seeding & FUP Governance (`compose/download.yml`)](#4-download-cross-seeding--fup-governance-composedownloadyml)
   - [`qbittorrent`](#qbittorrent)
   - [`qui`](#qui)
5. [Document Management & OCR Archival (`compose/paperless.yml`)](#5-document-management--ocr-archival-composepaperlessyml)
   - [`paperless-webserver`](#paperless-webserver)
   - [`paperless-broker`](#paperless-broker)
   - [`paperless-db`](#paperless-db)
6. [Knowledge Management & Digital Notes (`compose/knowledge.yml`)](#6-knowledge-management--digital-notes-composeknowledgeyml)
   - [`ignis`](#ignis)
   - [`readeck`](#readeck)
7. [Developer Workspaces & Backend Sandboxes (`compose/coding.yml`)](#7-developer-workspaces--backend-sandboxes-composecodingyml)
   - [`code-server`](#code-server)
   - [`coder`](#coder)
   - [`pocketbase`](#pocketbase)
8. [Storage Logistics, Inventory, Backups & Utilities (`compose/utilities.yml`)](#8-storage-logistics-inventory-backups--utilities-composeutilitiesyml)
   - [`copyparty`](#copyparty)
   - [`ntfy`](#ntfy)
   - [`homebox`](#homebox)
   - [`backrest`](#backrest)
   - [`enclosed`](#enclosed)
   - [`airtrail`](#airtrail)
9. [Static Web Applications (10 Caddy-Served Apps)](#9-static-web-applications-10-caddy-served-apps)
10. [Standby & Ops Profile Registry (16 Containers + 1 Native App)](#10-standby--ops-profile-registry-16-containers--1-native-app)
11. [Operational Scripts, LaunchAgents & Terraform](#11-operational-scripts-launchagents--terraform)

---

## 1. Core Infrastructure & Identity Spine (`compose/core.yml`)

### `caddy`
*The primary edge ingress reverse proxy, automatic Let's Encrypt TLS termination manager, HTTP/3 QUIC gateway, and static web server.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `caddy` |
| **Base Image** | `caddy:latest` (Caddy `v2.11.7`) |
| **Restart Policy** | `unless-stopped` |
| **Capabilities** | `NET_ADMIN` (Required for HTTP/3 QUIC UDP socket buffer tuning) |
| **Host Ports** | `80:80` (HTTP), `443:443` (HTTPS), `443:443/udp` (HTTP/3 QUIC) |
| **Healthcheck** | `wget --no-verbose --tries=1 --spider http://127.0.0.1:2019/config/ \|\| exit 1` (Interval: 30s, Timeout: 5s, Retries: 3, Start: 10s) |
| **Compose File** | `compose/core.yml` |

```yaml
volumes:
  - ${DOCKER_BASE_DIR}/Caddyfile:/etc/caddy/Caddyfile:ro
  - ${DOCKER_DATA_DIR}/caddy:/data
  - ${DOCKER_CONFIG_DIR}/caddy:/config
  # Static Frontends & Digital Garden
  - ${DOCKER_BASE_DIR}/quartz/public:/mind:ro
  - ${DOCKER_BASE_DIR}/web/fam:/fam:ro
  - ${DOCKER_BASE_DIR}/web/scan:/scan:ro
  - ${DOCKER_BASE_DIR}/web/aysynbm:/aysynbm:ro
  # Wave 1: Zero-Container Static Developer & Media Suite (0 MiB RAM)
  - ${DOCKER_BASE_DIR}/web/tools:/tools:ro
  - ${DOCKER_BASE_DIR}/web/chef:/chef:ro
  - ${DOCKER_BASE_DIR}/web/pdf:/pdf:ro
  - ${DOCKER_BASE_DIR}/web/speed:/speed:ro
  - ${DOCKER_BASE_DIR}/web/draw:/draw:ro
  - ${DOCKER_BASE_DIR}/web/mi:/mi:ro
```
* **Glance Metadata:** ID: `caddy`, Name: `Caddy`, Icon: `sh:caddy`, URL: `https://dash.vrg.rocks`, Description: `Reverse Proxy & Ingress Gateway`

---

### `tinyauth`
*Primary Forward-Auth and OpenID Connect (OIDC) provider (`v5.2.0`), enforcing zero-click Google OAuth 2.0 SSO, email allowlisting, and per-subdomain ACLs in ~25 MiB RAM.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `tinyauth` |
| **Base Image** | `ghcr.io/tinyauthapp/tinyauth:v5` (`v5.2.0`) |
| **Restart Policy** | `unless-stopped` |
| **Internal Port** | `3000/tcp` (Routed via Caddy at `https://auth.vrg.rocks`; built-in `/api/healthz` healthcheck) |
| **OIDC Clients (7)** | `paperless`, `arcane`, `homebox`, `airtrail`, `coder`, `readeck`, `jellyfin` (RS256 signing keys persisted at `/data/oidc/key.pem`) |
| **Admin-Locked Forward-Auth Apps (17)** | `code`, `backrest`, `qui`, `radarr`, `sonarr`, `lidarr`, `prowlarr`, `bazarr`, `cs`, `byparr`, `pb`, `ldap`, `router`, `ignis`, `mind`, `scan`, `aysynbm` (`TINYAUTH_APPS_<APP>_OAUTH_WHITELIST: ${TINYAUTH_ADMIN_EMAILS:?}`) |

```yaml
volumes:
  - ${DOCKER_DATA_DIR}/tinyauth:/data # tinyauth.db (sessions & pre-seeded oidc_consents), whitelist.txt, oidc/key.pem
```
* **Glance Metadata:** ID: `tinyauth`, Name: `Tinyauth`, Icon: `di:tinyauth`, URL: `https://auth.vrg.rocks`, Description: `Forward-Auth & OIDC Provider`

---

### `lldap`
*Ultra-lightweight Rust LDAP directory (`v0.6.2`, ~5 MiB RAM) serving as the single source of truth for Sol user accounts, groups, and multi-email aliases.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `lldap` |
| **Base Image** | `ghcr.io/lldap/lldap:${LLDAP_TAG:-stable}` (`v0.6.2`) |
| **Restart Policy** | `unless-stopped` |
| **Internal Ports** | `3890/tcp` (LDAP protocol for Jellyfin/Seerr), `17170/tcp` (Web UI routed via Caddy at `https://ldap.vrg.rocks` behind admin-only `forward_auth`) |
| **Base DN** | `dc=vrg,dc=rocks` |

```yaml
volumes:
  - ${DOCKER_DATA_DIR}/lldap:/data # users.db (watched by com.vrg.sol.identity-sync.plist)
```
* **Glance Metadata:** ID: `lldap`, Name: `LLDAP`, Icon: `sh:lldap`, URL: `https://ldap.vrg.rocks`, Description: `Lightweight Rust LDAP Directory (~5 MiB RAM)`

---

### `arcane`
*Modern web-based Docker and Compose stack manager with native Tinyauth OIDC integration.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `arcane` |
| **Base Image** | `ghcr.io/getarcaneapp/arcane:latest` (`v1.17.2`) |
| **Restart Policy** | `unless-stopped` |
| **Internal Port** | `3552/tcp` (Routed via Caddy at `https://arcane.vrg.rocks` with native OIDC + `OIDC_AUTO_REDIRECT_TO_PROVIDER: "true"`) |
| **Healthcheck** | `["CMD", "curl", "-fsS", "http://127.0.0.1:3552/api/health"]` (Interval: 30s, Timeout: 5s, Retries: 3, Start: 15s) |

```yaml
volumes:
  - /var/run/docker.sock:/var/run/docker.sock
  - ${DOCKER_DATA_DIR}/arcane:/app/data # arcane.db (SQLite WAL mode)
```
* **Glance Metadata:** ID: `arcane`, Name: `Arcane`, Icon: `sh:arcane`, URL: `https://arcane.vrg.rocks`, Description: `Modern Docker Management`

---

## 2. Dashboard & Monitoring (`compose/monitoring.yml`)

### `glance`
*Fast, lightweight Go server homepage, live telemetry dashboard, and release/feed aggregator (`v0.8.7`).*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `glance` |
| **Base Image** | `glanceapp/glance:latest` (`v0.8.7`) |
| **Restart Policy** | `unless-stopped` |
| **Internal Port** | `8080/tcp` (Routed via Caddy at `https://dash.vrg.rocks` with `import forward_auth`; `sol.vrg.rocks` redirects 302 to `https://dash.vrg.rocks/sol`) |
| **Healthcheck** | `wget -q --spider http://127.0.0.1:8080/api/healthz \|\| exit 1` (Interval: 30s, Timeout: 5s, Retries: 3, Start: 10s) |

```yaml
volumes:
  - ${DOCKER_CONFIG_DIR}/glance/config:/app/config     # glance.yml (tracked in Git)
  - ${DOCKER_CONFIG_DIR}/glance/assets:/app/assets     # user.css & sol.svg (tracked in Git)
  - ${EXTERNAL_DRIVE_00}:/media/panopticon:ro          # External USB drive capacity telemetry
  - /var/run/docker.sock:/var/run/docker.sock:ro       # Read-only container status inspection
  - /etc/localtime:/etc/localtime:ro
```
* **Glance Metadata:** ID: `glance`, Name: `Glance`, Icon: `sh:glance`, URL: `https://dash.vrg.rocks`, Description: `Sol Server Homepage`

---

## 3. Media Streaming & *arr PVR Suite (`compose/media.yml`)

### `jellyfin`
*Central containerized media server (`10.11.x` / `v12.2.0` LSIO) for streaming movies, television, music, and home videos.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `jellyfin` |
| **Base Image** | `lscr.io/linuxserver/jellyfin:latest` |
| **Restart Policy** | `unless-stopped` |
| **Internal Port** | `8096/tcp` (Routed via Caddy at `https://watch.vrg.rocks` and `https://jellyfin.vrg.rocks`) |
| **RAM Tmpfs** | `/tmp/jellyfin:size=2g,uid=501,gid=20,mode=0755` (Keeps Trickplay & transcode buffers in RAM off the APFS SSD) |
| **Database Locking** | `<LockingBehavior>Optimistic</LockingBehavior>` in `config/jellyfin/database.xml` |
| **Healthcheck** | `curl -fsS http://127.0.0.1:8096/health >/dev/null \|\| exit 1` (Interval: 30s, Timeout: 10s, Retries: 3, Start: 40s) |

```yaml
volumes:
  - ${DOCKER_CONFIG_DIR}/jellyfin:/config
  - ${DOCKER_DATA_DIR}/media:/media/internal
  - ${EXTERNAL_DRIVE_00}:/media/external
```
* **Authentication:** Supports both 1-click Google SSO (via ` Jellyfin-Plugin-SSO` + Tinyauth OIDC) and LDAP username/email + password login (via `LDAP-Auth` plugin -> `lldap:3890`), plus Quick Connect for TVs and Seerr.
* **Glance Metadata:** ID: `jellyfin`, Name: `Jellyfin`, Icon: `sh:jellyfin`, URL: `https://watch.vrg.rocks`, Description: `Media Streaming Server`

---

### `seerr`
*Unified media request and discovery platform (`v3.5.0`), combining historical Overseerr and Jellyseerr requests.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `seerr` |
| **Base Image** | `ghcr.io/seerr-team/seerr:latest` (`v3.5.0`) |
| **Init Process** | `init: true` |
| **Restart Policy** | `unless-stopped` |
| **DNS Overrides** | `8.8.8.8`, `1.1.1.1` (Prevents ISP DNS blocking on TMDb API lookups) |
| **Network Aliases** | `jellyseerr` |
| **Healthcheck** | `wget --no-verbose --tries=1 --spider http://localhost:5055/api/v1/settings/public \|\| exit 1` |
| **Internal Port** | `5055/tcp` (Routed via Caddy at `https://request.vrg.rocks`, `https://seerr.vrg.rocks`, `https://jellyseerr.vrg.rocks` behind `import forward_auth`) |

```yaml
volumes:
  - ${DOCKER_CONFIG_DIR}/seerr:/app/config # db/db.sqlite3 (43 merged requests) & settings.json
```
* **Glance Metadata:** ID: `seerr`, Name: `Seerr`, Icon: `sh:seerr`, URL: `https://request.vrg.rocks`, Description: `Media Requests & Discovery`

---

### `radarr`
*Automated movie collection manager, release monitor, and file organizer.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `radarr` |
| **Base Image** | `lscr.io/linuxserver/radarr:latest` |
| **Restart Policy** | `unless-stopped` |
| **DNS Overrides** | `1.1.1.1`, `9.9.9.9` |
| **Internal Port** | `7878/tcp` (Routed via Caddy at `https://radarr.vrg.rocks` behind admin-only `forward_auth`) |
| **Healthcheck** | `curl -fsS http://127.0.0.1:7878/ping >/dev/null \|\| exit 1` |

```yaml
volumes:
  - ${DOCKER_CONFIG_DIR}/radarr:/config
  - ${DOCKER_DATA_DIR}:/data
  - ${EXTERNAL_DRIVE_00}:/external
```
* **Glance Metadata:** ID: `radarr`, Name: `Radarr`, Icon: `sh:radarr`, URL: `https://radarr.vrg.rocks`, Description: `Movie Collection Manager`

---

### `sonarr`
*Automated television series tracker, episode monitor, and file organizer.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `sonarr` |
| **Base Image** | `lscr.io/linuxserver/sonarr:latest` |
| **Restart Policy** | `unless-stopped` |
| **DNS Overrides** | `1.1.1.1`, `9.9.9.9` |
| **Internal Port** | `8989/tcp` (Routed via Caddy at `https://sonarr.vrg.rocks` behind admin-only `forward_auth`) |
| **Healthcheck** | `curl -fsS http://127.0.0.1:8989/ping >/dev/null \|\| exit 1` |

```yaml
volumes:
  - ${DOCKER_CONFIG_DIR}/sonarr:/config
  - ${DOCKER_DATA_DIR}:/data
  - ${EXTERNAL_DRIVE_00}:/external
```
* **Glance Metadata:** ID: `sonarr`, Name: `Sonarr`, Icon: `sh:sonarr`, URL: `https://sonarr.vrg.rocks`, Description: `TV Series Tracker & Downloader`

---

### `bazarr`
*Companion subtitle automation manager (`v1.6.2`) for Radarr and Sonarr.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `bazarr` |
| **Base Image** | `lscr.io/linuxserver/bazarr:latest` (`v1.6.2`) |
| **Restart Policy** | `unless-stopped` |
| **DNS Overrides** | `1.1.1.1`, `9.9.9.9` |
| **Internal Port** | `6767/tcp` (Routed via Caddy at `https://bazarr.vrg.rocks` behind admin-only `forward_auth`) |
| **Healthcheck** | `curl -fsS http://127.0.0.1:6767/ping >/dev/null \|\| exit 1` |

```yaml
volumes:
  - ${DOCKER_CONFIG_DIR}/bazarr:/config
  - ${DOCKER_DATA_DIR}:/data
  - ${EXTERNAL_DRIVE_00}:/external
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
| **Internal Port** | `8686/tcp` (Routed via Caddy at `https://lidarr.vrg.rocks` behind admin-only `forward_auth`) |
| **Healthcheck** | `curl -fsS http://127.0.0.1:8686/ping >/dev/null \|\| exit 1` |

```yaml
volumes:
  - ${DOCKER_CONFIG_DIR}/lidarr:/config
  - ${DOCKER_DATA_DIR}:/data
  - ${EXTERNAL_DRIVE_00}:/external
```
* **Glance Metadata:** ID: `lidarr`, Name: `Lidarr`, Icon: `sh:lidarr`, URL: `https://lidarr.vrg.rocks`, Description: `Music Discography Manager`

---

### `prowlarr`
*Centralized indexer management proxy for BitTorrent trackers (syncing to Radarr, Sonarr, Lidarr, and QUI).*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `prowlarr` |
| **Base Image** | `lscr.io/linuxserver/prowlarr:latest` |
| **Restart Policy** | `unless-stopped` |
| **DNS Overrides** | `1.1.1.1`, `9.9.9.9` |
| **Internal Port** | `9696/tcp` (Routed via Caddy at `https://prowlarr.vrg.rocks` behind admin-only `forward_auth`) |
| **Challenge Solver** | `http://flaresolverr:8191` (`requestTimeout: 90s`, resolved via Docker alias to `byparr`) |
| **Healthcheck** | `curl -fsS http://127.0.0.1:9696/ping >/dev/null \|\| exit 1` |

```yaml
volumes:
  - ${DOCKER_CONFIG_DIR}/prowlarr:/config
```
* **Glance Metadata:** ID: `prowlarr`, Name: `Prowlarr`, Icon: `sh:prowlarr`, URL: `https://prowlarr.vrg.rocks`, Description: `Torrent & Usenet Indexer Proxy`

---

### `byparr`
*Cloudflare Turnstile bypass service (`v3.0.4`) for Prowlarr, aliasing `flaresolverr` on port `8191`.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `byparr` |
| **Base Image** | `ghcr.io/thephaseless/byparr:latest` (`v3.0.4`) |
| **Restart Policy** | `unless-stopped` |
| **Shared Memory & Tmpfs** | `shm_size: 1gb`, `tmpfs: ["/tmp:size=512m,exec,mode=1777"]` |
| **Environment** | `TZ: ${TZ}`, `LOG_LEVEL: info`, `BLOCK_MEDIA: "true"` |
| **Network Aliases** | `flaresolverr` |
| **Healthcheck** | `curl -fsS http://127.0.0.1:8191/openapi.json >/dev/null \|\| exit 1` (Lightweight FastAPI probe that does not spawn headless Firefox) |
| **Internal Port** | `8191/tcp` (Routed via Caddy at `https://byparr.vrg.rocks` behind admin-only `forward_auth`; `flaresolverr.vrg.rocks` redirects 301 to `byparr.vrg.rocks`) |

* **Glance Metadata:** ID: `byparr`, Name: `Byparr`, Icon: `sh:flaresolverr`, URL: `https://byparr.vrg.rocks`, Description: `Cloudflare Turnstile Solver`

---

## 4. Download, Cross-Seeding & FUP Governance (`compose/download.yml`)

### `qbittorrent`
*Primary BitTorrent download client with dedicated WAN peer port `42069` and automated Option A post-download symlink creation.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `qbittorrent` |
| **Base Image** | `lscr.io/linuxserver/qbittorrent:latest` |
| **Restart Policy** | `unless-stopped` |
| **Host Ports** | `42069:42069`, `42069:42069/udp` (WAN Peer Port) |
| **Internal Web Port**| `8080/tcp` (Routed via Caddy at `https://qb.vrg.rocks` and `https://qbittorrent.vrg.rocks` using qBittorrent Native Auth for mobile client compatibility) |
| **Healthcheck** | `curl -fsS http://127.0.0.1:8080/ >/dev/null \|\| exit 1` |

```yaml
volumes:
  - ${DOCKER_CONFIG_DIR}/qbittorrent:/config
  - ${DOCKER_DATA_DIR}:/data
  - ${EXTERNAL_DRIVE_00}:/external
```
* **Post-Download Hook:** Executes `/config/scripts/torrent_finished.py`, which pre-creates relative symlinks on `/external/media/{movies,tv}`, triggers Radarr/Sonarr `RescanMovie`/`RescanSeries` + `DownloadedMoviesScan`/`DownloadedEpisodesScan`, refreshes Jellyfin, and sends rich push notifications to `ntfy`.
* **Glance Metadata:** ID: `qbittorrent`, Name: `qBittorrent`, Icon: `sh:qbittorrent`, URL: `https://qb.vrg.rocks`, Description: `BitTorrent Client`

---

### `qui`
*Ultra-lean Go WebUI (`v1.32.0`, ~34 MiB RAM), native cross-seeding engine, tracker categorizer, and Airtel 3,333 GB FUP bandwidth governor for qBittorrent.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `qui` |
| **Base Image** | `ghcr.io/autobrr/qui:latest` (`v1.32.0`) |
| **User** | `501:20` (`${PUID}:${PGID}`) |
| **Restart Policy** | `unless-stopped` |
| **Internal Port** | `7476/tcp` (Routed via Caddy at `https://qui.vrg.rocks` behind admin-only `forward_auth` with `QUI__AUTH_DISABLED: "true"`) |

```yaml
volumes:
  - ${DOCKER_CONFIG_DIR}/qui:/config  # qui.db + tracked tracker_registry.json
  - ${DOCKER_DATA_DIR}:/data          # /data/torrents/qui-links
  - ${EXTERNAL_DRIVE_00}:/external    # /external/torrents/qui-links
```
* **Native Automation & FUP Governance:** Replaces standalone `cross-seed`, `qbit_manage`, and `flood`. Runs 10 native automation rules in `config/qui/qui.db` (backed by `config/qui/tracker_registry.json`), including 4 tracker auto-tagging rules (`Private-Exempt`, `Private-Buffer`, `Private-Ratio`, `Private-LongTail`) and 6 FUP seeding/upload governance tiers.
* **Glance Metadata:** ID: `qui`, Name: `QUI`, Icon: `sh:qui`, URL: `https://qui.vrg.rocks`, Description: `Modern Go Web UI, Cross-Seed & Automation Engine for qBittorrent`

---

## 5. Document Management & OCR Archival (`compose/paperless.yml`)

### `paperless-webserver`
*Document management system (`v3.3.2` LSIO / Paperless-ngx) with multi-language OCR (`eng+hin+kan+pan`), PDF password sanitization, and native Tinyauth OIDC.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `paperless-webserver` |
| **Base Image** | `ghcr.io/paperless-ngx/paperless-ngx:latest` |
| **Restart Policy** | `unless-stopped` |
| **Internal Port** | `8000/tcp` (Routed via Caddy at `https://docs.vrg.rocks` and `https://paperless.vrg.rocks`, native OIDC with `PAPERLESS_REDIRECT_LOGIN_TO_SSO: "true"`) |
| **Dependencies** | `paperless-db` (`service_healthy`), `paperless-broker` (`service_healthy`) |
| **OCR Languages** | `PAPERLESS_OCR_LANGUAGE: ${PAPERLESS_OCR_LANGUAGE:-eng+hin+kan+pan}`, `PAPERLESS_OCR_LANGUAGES: "hin kan pan"` |

```yaml
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
*Redis 8 task broker (`redis:8-alpine`) for Paperless Celery queues.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `paperless-broker` |
| **Base Image** | `docker.io/library/redis:8-alpine` |
| **Command** | `["redis-server", "--save", "60", "1", "--loglevel", "warning", "--maxmemory", "256mb", "--maxmemory-policy", "volatile-lru"]` |
| **Healthcheck** | `["CMD", "redis-cli", "ping"]` |
| **Internal Port** | `6379/tcp` |

```yaml
volumes:
  - ${DOCKER_DATA_DIR}/paperless/redis:/data
```

---

### `paperless-db`
*Shared PostgreSQL 17 Alpine (`musl`) relational cluster hosting both the `paperless` and `airtrail` databases.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `paperless-db` |
| **Base Image** | `docker.io/library/postgres:17-alpine` (`PG 17.11` musl) |
| **Command Tuning** | `shared_buffers=256MB`, `work_mem=16MB`, `effective_cache_size=1GB`, `maintenance_work_mem=64MB`, `wal_buffers=16MB`, `checkpoint_completion_target=0.9` |
| **Healthcheck** | `pg_isready -d ${PAPERLESS_DB_NAME:-paperless} -U ${PAPERLESS_DB_USER:-paperless}` |
| **Internal Port** | `5432/tcp` |

```yaml
volumes:
  - ${DOCKER_DATA_DIR}/paperless/db:/var/lib/postgresql/data
```
* **Backup:** Live cluster excluded from Restic (`data/paperless/db`). Both `paperless` and `airtrail` databases are dumped by `scripts/stage_db_backups.sh` into `data/backups/paperless_db.sql.gz` and `data/backups/airtrail_db.sql.gz`.

---

## 6. Knowledge Management & Digital Notes (`compose/knowledge.yml`)

### `ignis`
*Obsidian vault manager and web synchronizer.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `ignis` |
| **Base Image** | `nobbe/ignis:latest` |
| **Restart Policy** | `unless-stopped` |
| **Internal Port** | `8080/tcp` (Routed via Caddy at `https://ignis.vrg.rocks` behind admin-only `forward_auth`; `notes.vrg.rocks` redirects 301 to `ignis.vrg.rocks`) |
| **Healthcheck** | `curl -fsS http://127.0.0.1:8080/api/version >/dev/null \|\| exit 1` |

```yaml
volumes:
  - ${DOCKER_DATA_DIR}/ignis/vaults:/vaults
  - ${DOCKER_DATA_DIR}/ignis/data:/app/data
  - ${DOCKER_DATA_DIR}/ignis/obsidian:/app/obsidian-app
```

---

### `readeck`
*Read-later article archiver and bookmark manager (`v0.23.4`, Go + SQLite) with native Tinyauth OIDC.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `readeck` |
| **Base Image** | `codeberg.org/readeck/readeck:${READECK_TAG:-latest}` (`v0.23.4`) |
| **Restart Policy** | `unless-stopped` |
| **Internal Port** | `8000/tcp` (Routed via Caddy at `https://links.vrg.rocks`, native OIDC without edge `forward_auth` so browser extension & mobile Bearer tokens work cleanly) |
| **Healthcheck** | `["CMD", "/bin/readeck", "healthcheck", "-config", "config.toml"]` |

```yaml
volumes:
  - ${DOCKER_DATA_DIR}/readeck:/readeck # config.toml & data/db.sqlite3 (users pre-seeded & protected by identity_sync.py trigger)
```

---

## 7. Developer Workspaces & Backend Sandboxes (`compose/coding.yml`)

### `code-server`
*Browser-accessible VS Code IDE on the Sol filesystem.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `code-server` |
| **Base Image** | `lscr.io/linuxserver/code-server:latest` |
| **Restart Policy** | `unless-stopped` |
| **Internal Port** | `8443/tcp` (Routed via Caddy at `https://code.vrg.rocks` behind admin-only `forward_auth`, with `AUTH: none` inside container for 0-click launch) |
| **Healthcheck** | `curl -fsS http://127.0.0.1:8443/healthz >/dev/null \|\| exit 1` |

```yaml
volumes:
  - ${DOCKER_CONFIG_DIR}/code-server:/config
  - ${DOCKER_BASE_DIR}:/Server
  - /Users/vrg/Documents:/Documents
```

---

### `coder`
*Cloud development environment (CDE) platform (`v2.32.0`) provisioning Docker workspaces from Terraform (`coder/main.tf`).*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `coder` |
| **Base Image** | `ghcr.io/coder/coder:latest` (`v2.32.0`) |
| **Group Add** | `["0"]` (Grants access to OrbStack `/var/run/docker.sock` `root:root 0660`) |
| **Internal Port** | `7080/tcp` (Routed via Caddy at `https://coder.vrg.rocks`, native Tinyauth OIDC with `CODER_OIDC_ALLOW_SIGNUPS: "false"`, admin-only consent in Tinyauth) |
| **Healthcheck** | `curl -fsS http://127.0.0.1:7080/healthz >/dev/null \|\| exit 1` |

```yaml
volumes:
  - /var/run/docker.sock:/var/run/docker.sock
  - ${DOCKER_CONFIG_DIR}/coder:/home/coder/.config # Embedded PostgreSQL 16 (dumped to coder_db.sql.gz)
  - ${DOCKER_BASE_DIR}:/Sol                        # Contains coder/main.tf ('sol-workspace' template)
```

---

### `pocketbase`
*Single-binary Go + SQLite realtime backend sandbox (`v0.39.0`).*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `pocketbase` |
| **Base Image** | `ghcr.io/muchobien/pocketbase:latest` (`v0.39.0`) |
| **User** | `501:20` (`${PUID}:${PGID}`) |
| **Internal Port** | `8090/tcp` (Routed via Caddy at `https://pb.vrg.rocks` behind admin-only `forward_auth`; `/` redirects 302 to `/_/`) |
| **Healthcheck** | `wget --spider -q http://127.0.0.1:8090/api/health \|\| exit 1` |

```yaml
volumes:
  - ${DOCKER_DATA_DIR}/pocketbase:/pb_data
```

---

## 8. Storage Logistics, Inventory, Backups & Utilities (`compose/utilities.yml`)

### `copyparty`
*High-speed file server, WebDAV provider, and media browser (`v1.20.13`) with Tinyauth `Remote-User` identity integration.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `copyparty` |
| **Base Image** | `copyparty/ac:latest` |
| **User** | `501:20` (`${PUID}:${PGID}`) |
| **Stop Grace Period** | `15s` |
| **Healthcheck** | `wget --spider -q 127.0.0.1:3923/?reset=/._` |
| **Internal Port** | `3923/tcp` (Routed via Caddy at `https://files.vrg.rocks` and `https://copyparty.vrg.rocks` behind `import forward_auth`) |

```yaml
volumes:
  - ${DOCKER_CONFIG_DIR}/copyparty:/cfg
  - ${DOCKER_DATA_DIR}/copyparty:/w/copyparty
  - ${DOCKER_DATA_DIR}/media:/w/media
  - ${DOCKER_DATA_DIR}/torrents:/w/torrents
  - ${EXTERNAL_DRIVE_00}:/w/external
```

---

### `ntfy`
*HTTP-based publish-subscribe push notification service.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `ntfy` |
| **Base Image** | `binwiederhier/ntfy:latest` |
| **User / Init** | `501:20` (`${PUID}:${PGID}`), `init: true` |
| **Internal Port** | `80/tcp` (Routed via Caddy at `https://ntfy.vrg.rocks`; external `POST`/`PUT` publishes without an `Authorization` header are gated by `import forward_auth`, while internal Docker containers publish directly to `http://ntfy:80`) |
| **Healthcheck** | `wget -q --tries=1 http://localhost:80/v1/health -O - \| grep -Eo '"healthy"\s*:\s*true' \|\| exit 1` |

```yaml
volumes:
  - ${DOCKER_DATA_DIR}/ntfy/var/cache/ntfy:/var/cache/ntfy
  - ${DOCKER_CONFIG_DIR}/ntfy/etc/ntfy:/etc/ntfy
```

---

### `homebox`
*Physical asset and home inventory tracking system (`v0.25.0`, Go + SQLite) with native Tinyauth OIDC and Scanner PWA CORS integration.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `homebox` |
| **Base Image** | `ghcr.io/sysadminsmedia/homebox:latest` (`v0.25.0`) |
| **Internal Port** | `7745/tcp` (Routed via Caddy at `https://inv.vrg.rocks` with native OIDC + `HBOX_OPTIONS_ALLOW_LOCAL_LOGIN: "true"` for `scan.vrg.rocks` API auth) |
| **Healthcheck** | Built-in image healthcheck (`/api/v1/status`) |

```yaml
volumes:
  - ${DOCKER_DATA_DIR}/homebox:/data/ # homebox.db (WAL mode)
```

---

### `backrest`
*Encrypted Restic backup orchestrator, scheduler, and Web UI (`v1.14.1` + Restic `0.19.1`).*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `backrest` |
| **Base Image** | `ghcr.io/garethgeorge/backrest:latest` (`v1.14.1`) |
| **Hostname** | `sol-backrest` |
| **Internal Port** | `9898/tcp` (Routed via Caddy at `https://backrest.vrg.rocks` behind admin-only `forward_auth`) |
| **Healthcheck** | `wget -q -O /dev/null http://127.0.0.1:9898/ \|\| exit 1` |

```yaml
volumes:
  - ${DOCKER_CONFIG_DIR}/backrest:/config
  - ${DOCKER_DATA_DIR}/backrest/data:/data
  - ${DOCKER_DATA_DIR}/backrest/cache:/cache
  - ${DOCKER_CONFIG_DIR}/rclone:/rclone
  - ${DOCKER_BASE_DIR}:/userdata/sol
  - ${EXTERNAL_DRIVE_00}/backups/sol-restic:/repos/local-panopticon
```

---

### `enclosed`
*Zero-knowledge client-side encrypted notes and file drop service.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `enclosed` |
| **Base Image** | `ghcr.io/corentinth/enclosed:latest` (`1.16.0`) |
| **User** | `501:20` (`${PUID}:${PGID}`) |
| **Internal Port** | `8787/tcp` (Routed via Caddy at `https://send.vrg.rocks`; note creation `/` and `/api/notes` require `import forward_auth`, while recipient note links remain public) |
| **Healthcheck** | `wget --no-verbose --tries=1 --spider http://127.0.0.1:8787/ \|\| exit 1` |

```yaml
volumes:
  - ${DOCKER_DATA_DIR}/enclosed:/app/.data
```

---

### `airtrail`
*Personal flight log, Airbus telemetry, and passport map (`v3.13.1`, SvelteKit + PostgreSQL) with native Tinyauth OIDC.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `airtrail` |
| **Base Image** | `johly/airtrail:latest` (`v3.13.1`) |
| **Dependencies** | `paperless-db` (`condition: service_healthy`, database `airtrail`) |
| **Internal Port** | `3000/tcp` (Routed via Caddy at `https://fly.vrg.rocks`, native OIDC with `OAUTH_AUTO_LOGIN: "true"`) |

```yaml
volumes:
  - ${DOCKER_DATA_DIR}/airtrail:/app/uploads
```

---

## 9. Static Web Applications (10 Caddy-Served Apps)

All 10 static applications are mounted read-only into `caddy` (`compose/core.yml`) and served via the `(static_site)` snippet (`route { try_files ...; file_server }`), executing `import forward_auth` before any filesystem lookup and consuming **0 MiB** of additional container RAM:

| Subdomain | Host Path | Caddy Mount | Auth Policy | Description |
| :--- | :--- | :--- | :--- | :--- |
| `mind.vrg.rocks` | `quartz/public` | `/mind:ro` | Tinyauth (Admin Only) | Quartz v4 Digital Garden (`Quettamind`) |
| `fam.vrg.rocks` | `web/fam` | `/fam:ro` | Tinyauth (Forward Auth) | Family Data Vault (`vault.enc` client-side AES-GCM) |
| `scan.vrg.rocks` | `web/scan` | `/scan:ro` | Tinyauth (Admin Only) | Homebox Barcode Scanner PWA (targets `https://inv.vrg.rocks`) |
| `aysynbm.vrg.rocks` | `web/aysynbm` | `/aysynbm:ro` | Tinyauth (Admin Only) | Async Bookmark Manager |
| `tools.vrg.rocks` | `web/tools` | `/tools:ro` | Tinyauth (Forward Auth) | IT-Tools (`v2024.10.22-7ca5933`, managed by `sync_static_tools.sh`) |
| `chef.vrg.rocks` | `web/chef` | `/chef:ro` | Tinyauth (Forward Auth) | CyberChef (`v10.19.4`, managed by `sync_static_tools.sh`) |
| `pdf.vrg.rocks` | `web/pdf` | `/pdf:ro` | Tinyauth (Forward Auth) | BentoPDF (`v1.16.4`, client-side WebAssembly PDF toolkit) |
| `speed.vrg.rocks` | `web/speed` | `/speed:ro` | Tinyauth (Forward Auth) | OpenSpeedTest (`v2.5.4`, with Caddy `POST /upload* -> 200` handler) |
| `draw.vrg.rocks` | `web/draw` | `/draw:ro` | Tinyauth (Forward Auth) | Excalidraw (`v0.17.6`, client-side whiteboard) |
| `mi.vrg.rocks` | `web/mi` | `/mi:ro` | Tinyauth (Forward Auth) | MediaInfo WebASM analyzer + `/mi/rom` NES easter egg |

---

## 10. Standby & Ops Profile Registry (16 Containers + 1 Native App)

Standby services are declared with `profiles: ["standby"]` (and `rclone` with `profiles: ["ops"]`). Start any standby service on demand with `docker compose --profile standby up -d <service>`. Full lifecycle history and reactivation instructions live in [`04_INACTIVE_AND_LEGACY_REGISTRY.md`](04_INACTIVE_AND_LEGACY_REGISTRY.md).

| Service | Compose File | Image | Profile | Internal Port | Caddy Vhost |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `gatus` | `monitoring.yml` | `twinproduction/gatus:latest` | `standby` | `8080` | `status.vrg.rocks` (commented) |
| `dozzle` | `monitoring.yml` | `amir20/dozzle:latest` | `standby` | `8080` | `dozzle.vrg.rocks` (commented) |
| `beszel` | `monitoring.yml` | `henrygd/beszel:latest` | `standby` | `8090` | `beszel.vrg.rocks` (commented) |
| `beszel-agent` | `monitoring.yml` | `henrygd/beszel-agent:latest` | `standby` | `45876` (bridge) | None |
| `recyclarr` | `media.yml` | `ghcr.io/recyclarr/recyclarr:latest` | `standby` | N/A (`@daily`) | None |
| `wizarr` | `media.yml` | `ghcr.io/wizarrrr/wizarr:latest` | `standby` | `5690` | `wizarr.vrg.rocks` (commented) |
| `unpackerr` | `download.yml` | `golift/unpackerr:latest` | `standby` | N/A | None |
| `paperless-gotenberg` | `paperless.yml` | `docker.io/gotenberg/gotenberg:latest` | `standby` | `3000` | None |
| `paperless-tika` | `paperless.yml` | `docker.io/apache/tika:latest` | `standby` | `9998` | None |
| `paperless-ai` | `paperless.yml` | `clusterzx/paperless-ai:latest` | `standby` | `3000` | `paperless-ai.vrg.rocks` (commented) |
| `leafwiki` | `knowledge.yml` | `ghcr.io/perber/leafwiki:latest` | `standby` | `8080` | `leaf.vrg.rocks` (commented) |
| `kavita` | `knowledge.yml` | `lscr.io/linuxserver/kavita:latest` | `standby` | `5000` | `kavita.vrg.rocks` (commented) |
| `vaultwarden` | `utilities.yml` | `vaultwarden/server:latest` | `standby` | `80` | `vault.vrg.rocks`, `pass.vrg.rocks` (commented) |
| `n8n` | `utilities.yml` | `docker.n8n.io/n8nio/n8n:latest` | `standby` | `5678` | `n8n.vrg.rocks` (commented) |
| `homeassistant` | `utilities.yml` | `ghcr.io/home-assistant/home-assistant:stable` | `standby` | `8123` (host mode) | `home.vrg.rocks` (commented) |
| `rclone` | `utilities.yml` | `rclone/rclone:latest` | `ops` | `127.0.0.1:53682` | None (CLI runner) |
| `jellyfin-metal` | *(Native macOS)* | `/Applications/Jellyfin.app` | `standby` | `8097` (host) | `metal.vrg.rocks` (commented) |

---

## 11. Operational Scripts, LaunchAgents & Terraform

| Path | Purpose | Key Design & Safety Guarantees |
| :--- | :--- | :--- |
| `scripts/stage_db_backups.sh` | Pre-backup staging (`paperless_db.sql.gz`, `airtrail_db.sql.gz`, `coder_db.sql.gz`, `coder_home.tar.gz`, `coder_volume_name.txt`, `symlinks_manifest.tsv`, and 29 SQLite snapshots in `data/backups/sqlite/`) | Wipes `data/backups/sqlite/*` before each run, copies `.db`+`-wal` to temp dir, runs `.backup` + `PRAGMA journal_mode=DELETE;` so zero `-wal`/`-shm` sidecars exist, strips `SET transaction_timeout` from `coder_db.sql.gz`, and scans symlinks via an OrbStack `redis:8-alpine` container to avoid macOS Removable Volume TCC blocks. |
| `scripts/backup.sh` | Manual CLI wrapper for `stage_db_backups.sh` + local/cloud Restic snapshots | Runs `stage_db_backups.sh`, then executes `restic backup /userdata/sol --exclude-file /config/excludes.txt` + `forget --prune` inside `backrest` against `/repos/local-panopticon` and `rclone:OneDrive:Sol-Restic` (with `--legacy-rclone` fallback). |
| `scripts/restore.sh` | Master bare-metal disaster recovery & restore script | Uses `docker run --rm ... ghcr.io/garethgeorge/backrest:latest` during Step 1 (so Restic restore works before `.env` exists on disk), creates directories, runs `sync_static_tools.sh`, installs `scripts/launchd/*.plist`, recreates symlinks from `symlinks_manifest.tsv`, restores SQLite DBs (skipping any `-wal`/`-shm`), imports `paperless_db.sql.gz`, `airtrail_db.sql.gz`, and `coder_db.sql.gz`, recreates the `coder-*-home` volume from `coder_volume_name.txt`, and starts the stack. |
| `scripts/identity_sync.py` | Unified identity reconciliation engine (`LLDAP` -> `users.json` -> `Tinyauth`, `Jellyfin`, `Seerr`, `Paperless`, `AirTrail`, `Homebox`, `Readeck`, `Copyparty`) | Reads `data/lldap/users.db?immutable=1` directly via SQLite with a SHA-256 fast-path check (`/tmp/sol_identity_sync.sha256`), exiting in `<50ms` with zero DB writes when unchanged (eliminating `WatchPaths` self-triggering loops). |
| `scripts/allowlist_user.sh` | CLI onboarding helper (`./scripts/allowlist_user.sh <email> [admin\|user]`) | Updates `config/auth/users.json` via `jq` and triggers `identity_sync.py`. |
| `scripts/torrent_finished.py` | qBittorrent completion hook (`/config/scripts/torrent_finished.py`) | Pre-creates relative symlinks (`../../../torrents/...`) on `/external/media/{movies,tv}`, triggers targeted Radarr/Sonarr disk scans, refreshes Jellyfin, and sends rich notifications to `ntfy`. |
| `scripts/arr_symlink_dedupe.sh` | Radarr/Sonarr `CustomScript` notification hook (`/config/custom_scripts/arr_symlink_dedupe.sh`) | Enforces `/external/media/*` + `/external/torrents/*` scope guards, checks `[ -L "$DEST" ]` and `REAL_SRC = REAL_DEST` idempotency, and replaces physical copies with relative symlinks (`realpath -m --relative-to="$DIR" "$REAL_SRC"`). |
| `scripts/sync_static_tools.sh` | Static web suite installer (`web/{tools,chef,pdf,speed,draw,mi}`) | Idempotent `.sol_version`-checked downloader/extractor for the 6 Wave 1 static web bundles. |
| `scripts/setup_jellyfin_metal.py` | Standby native macOS Jellyfin bootstrap (`:8097`) | Preserves `config/jellyfin_metal/data/data/jellyfin.db` unless `--reset` is passed. |
| `scripts/launchd/com.vrg.sol.db-stage.plist` | macOS LaunchAgent (`02:45` & `14:45` daily) | Invokes `stage_db_backups.sh` via `/opt/homebrew/bin/python3` (which holds macOS TCC permission for `~/Documents`) with no `WorkingDirectory`, achieving `Exit 0`. |
| `scripts/launchd/com.vrg.sol.identity-sync.plist` | macOS LaunchAgent (`WatchPaths` on `data/lldap/users.db*`) | Runs `/opt/homebrew/bin/python3 /Users/vrg/Documents/Sol/scripts/identity_sync.py --from-lldap --apply` with `ThrottleInterval: 15`. |
| `coder/main.tf` | Active `sol-workspace` Coder v2 Terraform template | Provisions Ubuntu Docker workspace with persistent `coder-<id>-home` volume, `code-server`, Bun, and prebuilt `jj` `v0.28.2` musl binary. |
