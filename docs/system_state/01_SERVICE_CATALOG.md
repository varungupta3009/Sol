# 01. Active Service Catalog & Specification Registry

> **Scope:** Complete specification breakdown of all active containerized services, databases, runners, and static frontends running on `Sol`.  
> **Host Environment:** macOS (OrbStack / Docker Engine)  
> **Environment Variables File:** `.env`, `paperless.env`  
> **Security Notice:** All passwords, tokens, private keys, and encryption secrets have been sanitized and redacted.

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
   - [jellyseerr](#jellyseerr)
   - [radarr](#radarr)
   - [sonarr](#sonarr)
   - [bazarr](#bazarr)
   - [lidarr](#lidarr)
   - [prowlarr](#prowlarr)
   - [flaresolverr](#flaresolverr)
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
   - [homebox](#homebox)
   - [ntfy](#ntfy)
7. [Static Web Applications (Caddy Served)](#7-static-web-applications-caddy-served)
   - [Quartz Digital Garden (Quettamind)](#quartz-digital-garden-quettamind)
   - [Family Data Vault](#family-data-vault)
   - [Homebox Barcode Scanner PWA](#homebox-barcode-scanner-pwa)
   - [Async Bookmark Manager](#async-bookmark-manager)

---

## 1. Core Infrastructure & Identity Management

### `caddy`
*The primary edge ingress reverse proxy, TLS termination manager, and static asset web server.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `caddy` |
| **Base Image** | `caddy:latest` |
| **Restart Policy** | `unless-stopped` |
| **Capabilities** | `NET_ADMIN` (Required for HTTP/3 and network optimizations) |
| **Host Ports** | `80:80` (HTTP), `443:443` (HTTPS), `443:443/udp` (HTTP/3 / QUIC) |
| **Networks** | `default` (Bridge) |
| **Dependencies** | None |

```yaml
# Mount Hierarchy
volumes:
  - ./Caddyfile:/etc/caddy/Caddyfile:ro              # Proxy configuration (Read-Only)
  - /Users/vrg/Documents/Sol/data/caddy:/data       # ACME certificates, runtime state, and locks
  - /Users/vrg/Documents/Sol/config/caddy:/config   # Autosaved runtime JSON configs
  - /Users/vrg/Documents/Sol/quartz/public:/mind:ro # Static Quartz HTML digital garden
  - /Users/vrg/Documents/Sol/vault:/fam:ro          # Static Family Data Vault web application
  - /Users/vrg/Documents/Sol/scan:/scan:ro          # Static Homebox mobile scanner PWA
  - /Users/vrg/Documents/Sol/aysynbm:/aysynbm:ro    # Static Async bookmark manager web app
```
* **Glance Metadata:** ID: `caddy`, Name: `Caddy`, Icon: `sh:caddy`, URL: `https://dash.vrg.rocks`, Category: `Proxy`

---

### `authentik-server`
*Core identity provider, single sign-on (SSO) gateway, OIDC authority, and forward authentication backend.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | Generated (`sol-authentik-server-1` / `authentik-server`) |
| **Base Image** | `ghcr.io/goauthentik/server:2026.5.3` |
| **Command** | `server` |
| **Restart Policy** | `unless-stopped` |
| **Shared Memory** | `shm_size: 512mb` |
| **Host Ports** | `9000:9000` (HTTP), `9443:9443` (HTTPS) |
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
  - /Users/vrg/Documents/Sol/config/authentik/data:/data             # Media, cache, and app state
  - /Users/vrg/Documents/Sol/config/authentik/custom-templates:/templates # Custom branding & HTML
```
* **Glance Metadata:** ID: `authentik`, Name: `Authentik`, Icon: `sh:authentik`, URL: `https://auth.vrg.rocks`, Category: `Authentication`

---

### `authentik-worker`
*Asynchronous task worker for background LDAP sync, token issuance, housekeeping, and Docker socket events.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | Generated (`sol-authentik-worker-1` / `authentik-worker`) |
| **Base Image** | `ghcr.io/goauthentik/server:2026.5.3` |
| **Command** | `worker` |
| **User** | `root` (Required for `/var/run/docker.sock` interaction) |
| **Restart Policy** | `unless-stopped` |
| **Shared Memory** | `shm_size: 512mb` |
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
  - /var/run/docker.sock:/var/run/docker.sock                       # Docker integration & outpost management
  - /Users/vrg/Documents/Sol/config/authentik/data:/data             # Media & cache
  - /Users/vrg/Documents/Sol/config/authentik/certs:/certs           # TLS certificates
  - /Users/vrg/Documents/Sol/config/authentik/custom-templates:/templates
```
* **Glance Metadata:** Name: `worker`, Parent: `authentik`

---

### `authentik-postgresql`
*Dedicated relational storage engine for Authentik users, flows, policies, and tokens.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | Generated (`sol-authentik-postgresql-1` / `authentik-postgresql`) |
| **Base Image** | `docker.io/library/postgres:16-alpine` |
| **Restart Policy** | `unless-stopped` |
| **Healthcheck** | `pg_isready -d $${POSTGRES_DB} -U $${POSTGRES_USER}` (Interval: 30s, Timeout: 5s, Retries: 5, Start Period: 20s) |
| **Internal Port** | `5432/tcp` |

```yaml
# Environment Configuration (.env)
POSTGRES_DB: ${PG_DB:-authentik}
POSTGRES_USER: ${PG_USER:-authentik}
POSTGRES_PASSWORD: [REDACTED_DB_SECRET]

# Mount Hierarchy
volumes:
  - /Users/vrg/Documents/Sol/data/authentik:/var/lib/postgresql/data # Persistent database cluster
```
* **Glance Metadata:** Name: `postgresql`, Parent: `authentik`

---

### `arcane`
*Modern web-based Docker and compose stack manager with native Authentik OIDC integration.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `arcane` |
| **Base Image** | `ghcr.io/getarcaneapp/arcane:latest` |
| **Restart Policy** | `unless-stopped` |
| **Internal Port** | `3552/tcp` (Routed via Caddy at `https://arcane.vrg.rocks`) |

```yaml
# Environment Configuration (.env & compose)
APP_URL: "https://arcane.vrg.rocks"
PUID: "501"
PGID: "20"
ENCRYPTION_KEY: [REDACTED_32_BYTE_HEX_KEY]
JWT_SECRET: [REDACTED_32_BYTE_HEX_SECRET]
LOG_LEVEL: "debug"
LOG_JSON: "false"
OIDC_ENABLED: "true"
OIDC_CLIENT_ID: [REDACTED_OIDC_CLIENT_ID]
OIDC_CLIENT_SECRET: [REDACTED_OIDC_CLIENT_SECRET]
OIDC_ISSUER_URL: "https://auth.vrg.rocks/application/o/arcane"
OIDC_PROVIDER_NAME: "authentik"
OIDC_SCOPES: "openid email profile"
OIDC_MERGE_ACCOUNTS: "true"
DATABASE_URL: "file:data/arcane.db?_pragma=journal_mode(WAL)&_pragma=busy_timeout(2500)&_txlock=immediate"

# Mount Hierarchy
volumes:
  - /var/run/docker.sock:/var/run/docker.sock                       # Host Docker daemon management
  - /Users/vrg/Documents/Sol/data/arcane:/app/data                  # SQLite database, project files & templates
```
* **Glance Metadata:** ID: `arcane`, Name: `Arcane`, Icon: `sh:arcane`, URL: `https://arcane.vrg.rocks`, Description: `Modern Docker Management`

---

## 2. Dashboard & Metrics

### `glance`
*Lightweight, highly customized homepage, bookmark hub, and Docker container monitoring dashboard.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `glance` |
| **Base Image** | `glanceapp/glance:latest` |
| **Restart Policy** | `unless-stopped` |
| **Internal Port** | `8080/tcp` (Routed via Caddy at `https://dash.vrg.rocks`) |

```yaml
# Mount Hierarchy
volumes:
  - /Users/vrg/Documents/Sol/config/glance/config:/app/config       # glance.yml configuration file
  - /Users/vrg/Documents/Sol/config/glance/assets:/app/assets       # sol.svg branding & icons
  - /var/run/docker.sock:/var/run/docker.sock:ro                    # Read-only container health inspection
  - /etc/timezone:/etc/timezone:ro                                  # Host timezone sync
  - /etc/localtime:/etc/localtime:ro                                # Host local time sync
```
* **Glance Metadata:** ID: `glance`, Name: `Glance`, Icon: `sh:glance`, URL: `https://dash.vrg.rocks`, Description: `Sol Dashboard`

---

## 3. Media Streaming & Automation Suite

### `jellyfin`
*Central media server for transcoding and streaming movies, television, and home videos.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `jellyfin` |
| **Base Image** | `lscr.io/linuxserver/jellyfin:latest` |
| **Restart Policy** | `unless-stopped` |
| **Internal Port** | `8096/tcp` (Routed via Caddy at `https://watch.vrg.rocks` and `https://jellyfin.vrg.rocks`) |
| **LAN Fallback Ports**| Commented out in compose: `8096:8096`, `1900/udp` (DLNA), `7359/udp` (UPnP) |

```yaml
# Environment Configuration
PUID: "501"
PGID: "20"
TZ: "Asia/Kolkata"

# Mount Hierarchy
volumes:
  - /Users/vrg/Documents/Sol/config/jellyfin:/config                # Library database, metadata, plugins
  - /Users/vrg/Documents/Sol/data/media:/media/internal             # Internal fast NVMe/SSD storage
  - /Volumes/PANOPTICON:/media/external                             # External mass storage drive (EXTERNAL_DRIVE_00)
```
* **Glance Metadata:** ID: `jellyfin`, Name: `Jellyfin`, Icon: `sh:jellyfin`, URL: `https://watch.vrg.rocks`, Description: `Watch Movies & Shows`
* **Jellyfin Metal (Native Host Instance):** Dedicated bare-metal macOS instance running directly on host port `8097` (`https://metal.vrg.rocks`) with Apple Silicon VideoToolbox and Metal hardware acceleration for near-zero CPU 4K HDR transcoding. Bootstrapped and managed via `scripts/setup_jellyfin_metal.py`.

---

### `jellyseerr`
*Request management and media discovery platform for Jellyfin.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `jellyseerr` |
| **Base Image** | `fallenbagel/jellyseerr:latest` |
| **Restart Policy** | `unless-stopped` |
| **DNS Overrides** | `8.8.8.8`, `1.1.1.1` (Prevents ISP DNS filtering on TMDb API endpoints) |
| **Internal Port** | `5055/tcp` (Routed via Caddy at `https://request.vrg.rocks` and `https://jellyseerr.vrg.rocks`) |

```yaml
# Environment Configuration
TZ: "Asia/Kolkata"
LOG_LEVEL: "info"

# Mount Hierarchy
volumes:
  - /Users/vrg/Documents/Sol/config/jellyseerr:/app/config          # SQLite database and settings
```
* **Glance Metadata:** ID: `jellyseerr`, Name: `Jellyseerr`, Icon: `sh:jellyseerr`, URL: `https://request.vrg.rocks`, Description: `Request Movies & Shows`

---

### `radarr`
*Automated movie collection manager, release monitor, and file renamer.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `radarr` |
| **Base Image** | `lscr.io/linuxserver/radarr:latest` |
| **Restart Policy** | `unless-stopped` |
| **Internal Port** | `7878/tcp` (Routed via Caddy at `https://radarr.vrg.rocks`) |

```yaml
# Environment Configuration
PUID: "501"
PGID: "20"
TZ: "Asia/Kolkata"

# Mount Hierarchy
volumes:
  - /Users/vrg/Documents/Sol/config/radarr:/config                  # Application DB and XML configs
  - /Users/vrg/Documents/Sol/data:/data                             # Unified data directory (Enables atomic moves)
  - /Volumes/PANOPTICON:/external                                   # External bulk movie repository
```
* **Glance Metadata:** ID: `radarr`, Name: `Radarr`, Icon: `sh:radarr`, URL: `https://radarr.vrg.rocks`, Description: `Request Movies`

---

### `sonarr`
*Automated television series tracker, episode monitor, and file renamer.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `sonarr` |
| **Base Image** | `lscr.io/linuxserver/sonarr:latest` |
| **Restart Policy** | `unless-stopped` |
| **Internal Port** | `8989/tcp` (Routed via Caddy at `https://sonarr.vrg.rocks`) |

```yaml
# Environment Configuration
PUID: "501"
PGID: "20"
TZ: "Asia/Kolkata"

# Mount Hierarchy
volumes:
  - /Users/vrg/Documents/Sol/config/sonarr:/config                  # Application DB and series metadata
  - /Users/vrg/Documents/Sol/data:/data                             # Unified data root for hardlinks
  - /Volumes/PANOPTICON:/external                                   # External TV series root
```
* **Glance Metadata:** ID: `sonarr`, Name: `Sonarr`, Icon: `sh:sonarr`, URL: `https://sonarr.vrg.rocks`, Description: `Request TV Shows`

---

### `bazarr`
*Companion subtitle automation manager for Radarr and Sonarr.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `bazarr` |
| **Base Image** | `lscr.io/linuxserver/bazarr:latest` |
| **Restart Policy** | `unless-stopped` |
| **Internal Port** | `6767/tcp` (Routed via Caddy at `https://bazarr.vrg.rocks`) |

```yaml
# Environment Configuration
PUID: "501"
PGID: "20"
TZ: "Asia/Kolkata"

# Mount Hierarchy
volumes:
  - /Users/vrg/Documents/Sol/config/bazarr:/config                  # Subtitle provider state & database
  - /Users/vrg/Documents/Sol/data:/data                             # Internal media library access
  - /Volumes/PANOPTICON:/external                                   # External media library access
```
* **Glance Metadata:** ID: `bazarr`, Name: `Bazarr`, Icon: `sh:bazarr`, URL: `https://bazarr.vrg.rocks`, Description: `Request Subtitles`

---

### `lidarr`
*Automated music library manager and discography tracker.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `lidarr` |
| **Base Image** | `lscr.io/linuxserver/lidarr:latest` |
| **Restart Policy** | `unless-stopped` |
| **Internal Port** | `8686/tcp` (Routed via Caddy at `https://lidarr.vrg.rocks`) |

```yaml
# Environment Configuration
PUID: "501"
PGID: "20"
TZ: "Asia/Kolkata"

# Mount Hierarchy
volumes:
  - /Users/vrg/Documents/Sol/config/lidarr:/config                  # Artist DB and settings
  - /Users/vrg/Documents/Sol/data:/data                             # Music directory & torrents
  - /Volumes/PANOPTICON:/external                                   # External music archive
```
* **Glance Metadata:** ID: `lidarr`, Name: `Lidarr`, Icon: `sh:lidarr`, URL: `https://lidarr.vrg.rocks`, Description: `Request Movies (Music)`

---

### `prowlarr`
*Centralized indexer management proxy for Usenet and BitTorrent trackers.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `prowlarr` |
| **Base Image** | `lscr.io/linuxserver/prowlarr:latest` |
| **Restart Policy** | `unless-stopped` |
| **Internal Port** | `9696/tcp` (Routed via Caddy at `https://prowlarr.vrg.rocks`) |

```yaml
# Environment Configuration
PUID: "501"
PGID: "20"
TZ: "Asia/Kolkata"

# Mount Hierarchy
volumes:
  - /Users/vrg/Documents/Sol/config/prowlarr:/config                # Tracker definitions and API keys
```
* **Glance Metadata:** ID: `prowlarr`, Name: `Prowlarr`, Icon: `sh:prowlarr`, URL: `https://prowlarr.vrg.rocks`, Description: `Request Movies (Indexer)`

---

### `flaresolverr`
*Proxy server to bypass Cloudflare and DDoS-GUARD protection for Prowlarr indexers.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `flaresolverr` |
| **Base Image** | `ghcr.io/flaresolverr/flaresolverr:latest` |
| **Restart Policy** | `unless-stopped` |
| **Internal Port** | `8191/tcp` (Direct container-to-container calls from Prowlarr) |

```yaml
# Environment Configuration
TZ: "Asia/Kolkata"
LOG_LEVEL: "info"
```
* **Glance Metadata:** ID: `flaresolverr`, Name: `FlareSolverr`, Icon: `sh:flaresolverr`, URL: `https://flaresolverr.vrg.rocks`, Description: `Solve Prowlarr Captchas`

---

## 4. Download & Cross-Seeding Pipeline

### `qbittorrent`
*Primary BitTorrent download client featuring Web UI management and dedicated WAN peer listening.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `qbittorrent` |
| **Base Image** | `lscr.io/linuxserver/qbittorrent:latest` |
| **Restart Policy** | `unless-stopped` |
| **Host Ports** | `42069:42069` (TCP), `42069:42069/udp` (UDP) |
| **Internal Web Port**| `8080/tcp` (Routed via Caddy at `https://qb.vrg.rocks` and `https://qbittorrent.vrg.rocks`) |

```yaml
# Environment Configuration (.env)
PUID: "501"
PGID: "20"
TZ: "Asia/Kolkata"
WEBUI_PORT: "8080"
TORRENTING_PORT: "42069"

# Mount Hierarchy
volumes:
  - /Users/vrg/Documents/Sol/config/qbittorrent:/config              # qBittorrent.conf, scripts, fastresume
  - /Users/vrg/Documents/Sol/data/torrents:/downloads               # Torrent payload destination
  - /Volumes/PANOPTICON:/external                                   # External seed directory
```
* **Post-Download Automation:** Runs `/config/scripts/ntfy_notify.sh` to broadcast download completion to ntfy topic `qBittorrent`.
* **Glance Metadata:** ID: `qbittorrent`, Name: `qBittorrent`, Icon: `sh:qbittorrent`, URL: `https://qbittorrent.vrg.rocks`, Description: `Torrent Client`

---

### `cross-seed`
*Fully automated cross-seeding daemon searching Prowlarr Torznab endpoints and injecting matches via symlinks.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `cross-seed` |
| **Base Image** | `ghcr.io/cross-seed/cross-seed:6` |
| **Command** | `daemon` |
| **User** | `501:20` (`${PUID}:${PGID}`) |
| **Restart Policy** | `unless-stopped` |
| **Internal Port** | `2468/tcp` (Routed via Caddy at `https://cs.vrg.rocks`) |

```yaml
# Mount Hierarchy
volumes:
  - /Users/vrg/Documents/Sol/config/cross-seed:/config              # config.js, cross-seed.db (SQLite)
  - /Users/vrg/Documents/Sol/data/torrents:/downloads               # Internal downloads
  - /Volumes/PANOPTICON:/external                                   # External downloads
```
* **Operational Mode:** `matchMode: "partial"`, `linkType: "symlink"`, `linkDirs: ["/downloads/cross-seed-links", "/external/cross-seed-links"]`, `action: "inject"`.
* **Glance Metadata:** ID: `cross-seed`, Name: `Cross-Seed`, Icon: `sh:cross-seed`, URL: `https://cs.vrg.rocks`, Description: `Torrent Cross Seeding App`

---

## 5. Document Management & OCR Archival

### `paperless-webserver`
*Document management system featuring OCR, tagging, automated consumption, and OIDC authentication.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `paperless-webserver` |
| **Base Image** | `ghcr.io/paperless-ngx/paperless-ngx:latest` |
| **Restart Policy** | `unless-stopped` |
| **Internal Port** | `8000/tcp` (Routed via Caddy at `https://docs.vrg.rocks` and `https://paperless.vrg.rocks`) |
| **Dependencies** | `paperless-db` (`condition: service_healthy`), `paperless-broker` (`condition: service_healthy`) |

```yaml
# Environment Configuration (paperless.env & compose)
USERMAP_UID: "501"
USERMAP_GID: "20"
PAPERLESS_URL: "https://docs.vrg.rocks"
PAPERLESS_TIME_ZONE: "Asia/Kolkata"
PAPERLESS_OCR_LANGUAGE: "eng"
PAPERLESS_OCR_LANGUAGES: "hin kan pan"
PAPERLESS_CONSUMER_RECURSIVE: "true"
PAPERLESS_CONSUMER_SUBDIRS_AS_TAGS: "true"
PAPERLESS_FILENAME_DATE_ORDER: "YMD"
PAPERLESS_REDIS: "redis://paperless-broker:6379"
PAPERLESS_DBHOST: "paperless-db"
PAPERLESS_PRE_CONSUME_SCRIPT: "/usr/src/paperless/scripts/pre-consumption.py"
PAPERLESS_POST_CONSUME_SCRIPT: "/usr/src/paperless/scripts/ntfy_notify.sh"
PAPERLESS_APPS: "allauth.socialaccount.providers.openid_connect"
PAPERLESS_SOCIALACCOUNT_PROVIDERS: [REDACTED_AUTHENTIK_OIDC_PAYLOAD]
PAPERLESS_LOGOUT_REDIRECT_URL: "https://auth.vrg.rocks/application/o/paperless-ngx/end-session/"

# Mount Hierarchy
volumes:
  - /Users/vrg/Documents/Sol/config/paperless:/usr/src/paperless/config
  - /Users/vrg/Documents/Sol/data/paperless/data:/usr/src/paperless/data
  - /Users/vrg/Documents/Sol/data/paperless/media:/usr/src/paperless/media
  - /Users/vrg/Documents/Sol/data/paperless/export:/usr/src/paperless/export
  - /Users/vrg/Documents/Sol/data/paperless/consume:/usr/src/paperless/consume
  - /Users/vrg/Documents/Sol/data/paperless/scripts:/usr/src/paperless/scripts
```
* **Glance Metadata:** ID: `paperless`, Name: `Paperless`, Icon: `sh:paperless-ngx`, URL: `https://docs.vrg.rocks`, Description: `Document Server`

---

### `paperless-broker`
*High-performance Redis instance handling Paperless task queues and celery worker jobs.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `paperless-broker` |
| **Base Image** | `docker.io/library/redis:8` |
| **Restart Policy** | `unless-stopped` |
| **Healthcheck** | `redis-cli ping` (Interval: 10s, Timeout: 5s, Retries: 5) |
| **Internal Port** | `6379/tcp` |

```yaml
# Mount Hierarchy
volumes:
  - /Users/vrg/Documents/Sol/data/paperless/redis:/data
```
* **Glance Metadata:** Name: `Broker`, Parent: `paperless`

---

### `paperless-db`
*PostgreSQL 17 database cluster storing metadata, OCR indexes, correspondents, and document tags.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `paperless-db` |
| **Base Image** | `docker.io/library/postgres:17` |
| **Restart Policy** | `unless-stopped` |
| **Healthcheck** | `pg_isready -d paperless -U paperless` (Interval: 10s, Timeout: 5s, Retries: 5) |
| **Internal Port** | `5432/tcp` |

```yaml
# Environment Configuration
POSTGRES_DB: "paperless"
POSTGRES_USER: "paperless"
POSTGRES_PASSWORD: [REDACTED_DB_PASSWORD]

# Mount Hierarchy
volumes:
  - /Users/vrg/Documents/Sol/data/paperless/db:/var/lib/postgresql/data
```
* **Glance Metadata:** Name: `DB`, Parent: `paperless`

---

### `ignis`
*Obsidian vault manager and web synchronizer for digital notes and markdown graphs.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | Generated (`sol-ignis-1` / `ignis`) |
| **Base Image** | `nobbe/ignis:latest` |
| **Restart Policy** | `unless-stopped` |
| **Internal Port** | `8080/tcp` (Routed via Caddy at `https://ignis.vrg.rocks`) |

```yaml
# Environment Configuration
PUID: "501"
PGID: "20"

# Mount Hierarchy
volumes:
  - /Users/vrg/Documents/Sol/data/ignis/vaults:/vaults
  - /Users/vrg/Documents/Sol/data/ignis/data:/app/data
  - /Users/vrg/Documents/Sol/data/ignis/obsidian:/app/obsidian-app
```

---

## 6. Developer Workspaces, Logistics & Utilities

### `code-server`
*Browser-accessible VSCode IDE running on the server filesystem.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `code-server` |
| **Base Image** | `lscr.io/linuxserver/code-server:latest` |
| **Restart Policy** | `unless-stopped` |
| **Internal Port** | `8443/tcp` (Routed via Caddy at `https://code.vrg.rocks`) |

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
  - /Users/vrg/Documents/Sol/config/code-server:/config              # Extensions, keybindings, history
  - /Users/vrg/Documents/Sol:/Server                                # Entire Sol repository root
```
* **Glance Metadata:** ID: `code`, Name: `Code`, Icon: `sh:visual-studio-code`, URL: `https://code.vrg.rocks`, Description: `VSCode Server`

---

### `coder`
*Cloud development environment platform creating on-demand Docker workspaces using Terraform.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `coder` |
| **Base Image** | `ghcr.io/coder/coder:latest` |
| **Restart Policy** | `unless-stopped` |
| **Group Add** | `20` (`${PGID}`) |
| **Internal Port** | `7080/tcp` (Routed via Caddy at `https://coder.vrg.rocks`) |

```yaml
# Mount Hierarchy
volumes:
  - /var/run/docker.sock:/var/run/docker.sock                       # Provisioning dynamic container workspaces
  - /Users/vrg/Documents/Sol/config/coder:/home/coder/.config       # Coder configuration & embedded state
  - /Users/vrg/Documents/Sol:/Sol                                   # Workspace source tree mount
```
* **Glance Metadata:** ID: `coder`, Name: `Coder`, Icon: `sh:visual-studio-code`, URL: `https://coder.vrg.rocks`, Description: `Coder Server`

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
  - /Users/vrg/Documents/Sol/config/copyparty:/cfg:z                # copyparty.conf, salts & sessions DB
  - /Users/vrg/Documents/Sol/data/copyparty:/w/copyparty:z          # Shared uploads root
  - /Users/vrg/Documents/Sol/data/media:/w/media:z                  # Internal media directories
  - /Users/vrg/Documents/Sol/data/torrents:/w/torrents:z            # Internal torrent directories
  - /Volumes/PANOPTICON:/w/external:z                               # External hard drive storage
```
* **Configured Endpoints (`copyparty.conf`):** Webroot `/`, Private vault `/priv`, listening internally on ports 3923, 8086, 3939.
* **Glance Metadata:** ID: `copyparty`, Name: `copyparty`, Icon: `sh:copyparty`, URL: `https://files.vrg.rocks`, Description: `File Server`

---

### `homebox`
*Asset and physical home inventory tracking database.*

| Specification | Configuration |
| :--- | :--- |
| **Container Name** | `homebox` |
| **Base Image** | `ghcr.io/sysadminsmedia/homebox:latest` |
| **Restart Policy** | `unless-stopped` |
| **Internal Port** | `7745/tcp` (Routed via Caddy at `https://inv.vrg.rocks` with full CORS headers) |

```yaml
# Environment Configuration
HBOX_LOG_LEVEL: "info"
HBOX_LOG_FORMAT: "text"
HBOX_WEB_MAX_FILE_UPLOAD: "10"
HBOX_OPTIONS_ALLOW_ANALYTICS: "false"

# Mount Hierarchy
volumes:
  - /Users/vrg/Documents/Sol/data/homebox:/data/                    # SQLite database (homebox.db) & item photos
```
* **Glance Metadata:** ID: `homebox`, Name: `Homebox`, Icon: `sh:homebox`, URL: `https://inv.vrg.rocks`, Description: `Home Inventory Management`

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
| **Healthcheck** | `wget -q --tries=1 http://localhost:80/v1/health -O - \| grep -Eo '"healthy"\s*:\s*true' \|\| exit 1` |
| **Internal Port** | `80/tcp` (Routed via Caddy at `https://ntfy.vrg.rocks`) |

```yaml
# Environment Configuration
TZ: "Asia/Kolkata"

# Mount Hierarchy
volumes:
  - /Users/vrg/Documents/Sol/data/ntfy/var/cache/ntfy:/var/cache/ntfy # Message queue cache & attachments
  - /Users/vrg/Documents/Sol/config/ntfy/etc/ntfy:/etc/ntfy           # server.yml configuration
```
* **Glance Metadata:** ID: `ntfy`, Name: `ntfy`, Icon: `sh:ntfy`, URL: `https://ntfy.vrg.rocks`, Description: `Notification Service`

---

## 7. Static Web Applications (Caddy Served)

These frontend applications do not run as standalone containers; they are directly mounted into the `caddy` container and served using Caddy's optimized static file server directives with custom error fallbacks and Authentik forward authentication.

### Quartz Digital Garden (`Quettamind`)
* **FQDN / Proxy Route:** `https://mind.vrg.rocks`
* **Host Source Directory:** `/Users/vrg/Documents/Sol/quartz/public`
* **Container Mount:** `/mind:ro`
* **Authentication:** Authentik Forward Auth (`import authentik`)
* **Routing Logic:** `try_files {path} {path}.html {path}/ =404` with custom 404 rewrite `/{err.status_code}.html`.

### Family Data Vault
* **FQDN / Proxy Route:** `https://fam.vrg.rocks`
* **Host Source Directory:** `/Users/vrg/Documents/Sol/vault`
* **Container Mount:** `/fam:ro`
* **Authentication:** Authentik Forward Auth (`import authentik`)
* **Routing Logic:** `try_files {path} {path}.html {path}/ =404` with custom error handler.

### Homebox Barcode Scanner PWA
* **FQDN / Proxy Route:** `https://scan.vrg.rocks`
* **Host Source Directory:** `/Users/vrg/Documents/Sol/scan`
* **Container Mount:** `/scan:ro`
* **Authentication:** Authentik Forward Auth (`import authentik`)
* **Routing Logic:** PWA manifest with `index.html`, `scanner.html`, `queue.html`, `settings.html`.

### Async Bookmark Manager
* **FQDN / Proxy Route:** `https://aysynbm.vrg.rocks`
* **Host Source Directory:** `/Users/vrg/Documents/Sol/aysynbm`
* **Container Mount:** `/aysynbm:ro`
* **Authentication:** Direct static access with compression
* **Routing Logic:** `try_files {path} {path}.html {path}/ =404`.
