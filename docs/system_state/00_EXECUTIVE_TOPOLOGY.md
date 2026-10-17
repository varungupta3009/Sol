# 00. Executive Topology: Sol Server Infrastructure

> **Environment:** `Sol` (macOS-based Home Server on OrbStack / Docker Engine)  
> **Base Workspace Path:** `/Users/vrg/Documents/Sol` (`DOCKER_BASE_DIR`)  
> **Primary Domain:** `*.vrg.rocks`  
> **Network Ingress:** Caddy v2 (`caddy:${CADDY_TAG:-2}`, Edge Reverse Proxy with Automatic TLS & HTTP/3)  
> **Authentication Engine:** Authentik Server `2026.5.3` (Forward Auth & OIDC Provider)  
> **Orchestration:** Docker Compose V2 `include:` with `profiles: ["standby"]` and `profiles: ["ops"]`  
> **Original Audit Date:** August 2026  
> **Last Synced to Ground Truth:** 2026-10-17 (`docker-compose.yml`, `compose/*.yml`, `Caddyfile`, `ports.json`, `.env.example`, `scripts/*`, `coder/main.tf`)  

---

## 1. System Overview & Architecture

**Sol** is a self-hosted home server built from modular container stacks. The root `docker-compose.yml` (project `name: sol`) loads 8 domain files under `compose/` through Docker Compose V2 `include:`. The stack delivers edge routing with forward authentication, central identity, media streaming and PVR automation, document OCR with pre-consumption sanitization, developer workspaces, and versioned cloud backup.

### Container Inventory Summary

| Tier | Count | Activation | Members |
| :--- | :---: | :--- | :--- |
| **Active (Default Profile)** | `24` | `docker compose up -d` | `caddy`, `authentik-postgresql`, `authentik-server`, `authentik-worker`, `arcane`, `glance`, `jellyfin`, `seerr`, `radarr`, `sonarr`, `bazarr`, `lidarr`, `prowlarr`, `byparr`, `qbittorrent`, `cross-seed`, `paperless-webserver`, `paperless-broker`, `paperless-db`, `ignis`, `code-server`, `coder`, `copyparty`, `ntfy` |
| **Standby / Ops (Profiled)** | `26` | `docker compose --profile standby up -d <service>` | `flaresolverr`, `recyclarr`, `wizarr`, `unpackerr`, `qbit_manage`, `flood`, `paperless-gotenberg`, `paperless-tika`, `paperless-ai`, `gatus`, `dozzle`, `beszel`, `beszel-agent`, `dockge`, `uptime-kuma`, `homarr`, `leafwiki`, `kavita`, `calibre`, `calibre-web`, `homebox`, `vaultwarden`, `n8n`, `homeassistant`, `rclone` (`ops`, `standby`), `rclone-gui` |
| **Native macOS (Non-Container)** | `1` | `python3 scripts/setup_jellyfin_metal.py` | `jellyfin-metal` (host port `8097`, `https://metal.vrg.rocks`) |

> [!NOTE]
> Standby services are declared as full YAML service blocks with `profiles: ["standby"]`. This replaces the earlier commented-out YAML blocks. `rclone` carries both `ops` and `standby` profiles, so `scripts/backup.sh` can launch it with `docker compose --profile ops run --rm rclone ...`.

```
                                  [ Internet / WAN ]
                                           |
                                           v
                             +---------------------------+
                             |       Caddy Reverse       |
                             | Proxy (:80, :443 TCP/UDP) |
                             +-------------+-------------+
                                           |
                   +-----------------------+-----------------------+
                   | (Forward Auth / TLS)  |                       |
                   v                       v                       v
     +--------------------------+  +---------------+  +--------------------------+
     |     Authentik Server     |  | Glance Hub    |  | Static Web Endpoints     |
     | (127.0.0.1:9000, :9443)  |  | (dash.) [SSO] |  |  - /mind (Quartz Garden) |
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
| - Seerr (:5055)      |  | - Redis 8 (:6379)    |  | - Coder Server(:7080)|
| - Radarr (:7878)     |  | - PostgreSQL 17 (DB) |  | - Copyparty (:3923)  |
| - Sonarr (:8989)     |  | - Ignis (:8080)      |  | - ntfy Push (:80)    |
| - Bazarr (:6767)     |  +----------------------+  | - Arcane (:3552)     |
| - Lidarr (:8686)     |                            +----------------------+
| - Prowlarr (:9696)   |
| - Byparr (:8191)     |   [ Native macOS Host ]
|   alias flaresolverr |   - Jellyfin Metal (:8097, VideoToolbox)
| - qBittorrent (:8080)|     via host.docker.internal
| - Cross-Seed (:2468) |
+----------------------+
```

### Core Architecture Pillars

1. **Edge Routing & Ingress (`Caddy`):**
   - Serves as the sole public gateway (`80/tcp`, `443/tcp`, `443/udp` for HTTP/3).
   - Issues Let's Encrypt TLS certificates per subdomain under `vrg.rocks` (no wildcard certificate).
   - Enforces forward authentication against the Authentik embedded outpost through the `(authentik)` snippet.
   - Applies the `(security_headers)` snippet (`nosniff`, `SAMEORIGIN`, `strict-origin-when-cross-origin`, HSTS `max-age=31536000; includeSubDomains; preload`, `-Server`).
   - Hosts static web applications (`Quartz`, `Family Vault`, `Scan`, `Aysynbm`) through the `(static_site)` snippet and `file_server`.
   - Runs 27 active site blocks. The 18 standby vhosts stay commented out until the matching `--profile standby` container starts.

2. **Unified Identity & Access Management (`Authentik`):**
   - Centralizes authentication across administrative dashboards and backend utilities.
   - Runs the embedded forward-auth outpost (`/outpost.goauthentik.io/auth/caddy`) on `authentik-server:9000` for web interfaces that lack native OIDC.
   - Supplies native OIDC single sign-on (SSO) to **Arcane** and **Paperless-ngx**.
   - `authentik-server` binds host ports to loopback only (`127.0.0.1:9000:9000`, `127.0.0.1:9443:9443`) and runs `AUTHENTIK_WEB__WORKERS: 2`.
   - `authentik-worker` runs without `user: root` and without `/var/run/docker.sock`, because Caddy uses the embedded outpost.

3. **Media Orchestration & Ingestion Pipeline:**
   - **qBittorrent** is the core BitTorrent daemon with incoming port `42069` (TCP/UDP) forwarded on WAN. Its Web UI at `qb.vrg.rocks` uses qBittorrent Native Auth without Authentik so the Android mobile torrent client can connect directly.
   - **Cross-Seed** monitors client torrents and injects matches through symlinks to raise ratio across trackers.
   - **Prowlarr** manages indexer health and sends Cloudflare Turnstile challenges to **Byparr** (`ghcr.io/thephaseless/byparr:latest`, port `8191`, network alias `flaresolverr`). Legacy **FlareSolverr** stays under `profiles: ["standby"]`.
   - **Radarr**, **Sonarr**, **Lidarr**, and **Bazarr** coordinate metadata, downloads, subtitle sync, and file renaming.
   - **Jellyfin** (container) serves streams to LAN TVs and remote clients. **Jellyfin Metal** (native macOS, port `8097`) provides Apple VideoToolbox hardware transcoding.
   - **Seerr** handles user requests, TMDb discovery, and automated *arr ingestion.

4. **Document Archival & Information Capture (`Paperless-ngx`):**
   - Dedicated document pipeline with Redis broker (`paperless-broker`, `redis:8-alpine`) and PostgreSQL 17 database (`paperless-db`, Debian `postgres:17` on `glibc`).
   - `paperless-webserver` receives `PAPERLESS_DBNAME`, `PAPERLESS_DBUSER`, `PAPERLESS_DBPASS`, `PAPERLESS_TASK_WORKERS: 2`, and `PAPERLESS_THREADS_PER_WORKER: 2`.
   - Python pre-consumption hook (`pre-consumption.py` with `pikepdf`) decrypts password-protected PDFs and extracts embedded attachments.
   - Post-consumption hook (`ntfy_notify.sh`) sends structured push notifications through **ntfy**.

5. **Developer Workspaces & File Logistics:**
   - **code-server** provides browser VS Code with `/Users/vrg/Documents/Sol` at `/Server` and `/Users/vrg/Documents` at `/Documents`. `code.vrg.rocks` enforces `import authentik` in front of the code-server Argon2 password.
   - **Coder v2** provisions container workspaces from local Terraform (`coder/main.tf`). The duplicate `coder/default.tf` is removed. Workspaces download the prebuilt `jj` `v0.28.2` musl binary instead of compiling with `cargo install`.
   - **Copyparty** provides multi-user, authenticated WebDAV and file sharing across the internal SSD and external media drives.
   - **Homebox** (physical inventory) is in `profiles: ["standby"]` pending local SQLite database repair. Its `inv.vrg.rocks` vhost is commented out, and its CORS rule is restricted to `Origin https://scan.vrg.rocks`.
   - **Arcane** manages local Docker containers and compose stacks with OIDC authentication (`LOG_LEVEL: info`).

6. **Storage Hierarchy & Disaster Recovery:**
   - Base server directory splits into `./config` (persistent service state), `./data` (databases, caches, media root), and `./logs` (audit traces).
   - `scripts/backup.sh` dumps both PostgreSQL clusters, takes atomic online SQLite `.backup` snapshots into `data/backups/sqlite/`, and runs `rclone sync` to `OneDrive:Sol` with `--backup-dir OneDrive:Sol-archive/<TIMESTAMP>` for point-in-time archiving.
   - Rclone filter rules come from `config/rclone/filter.txt` (fallback: tracked `config/rclone/filter.txt.example`). They exclude live database clusters (`data/authentik/**`, `data/paperless/db/**`, `data/paperless/redis/**`), SQLite `**/*-wal` and `**/*-shm` files, bulk media, and transient caches.
   - `scripts/restore.sh` pulls from `OneDrive:Sol`, restores missing SQLite snapshots, and imports PostgreSQL dumps with `gunzip -c ... | docker exec -i ... psql`.

---

## 2. Directory Layout & Taxonomy

```
/Users/vrg/Documents/Sol/
├── .env                                  # Centralized master environment variables & secrets
├── .env.example                          # Sanitized template for environment configuration
├── Caddyfile                             # Active reverse proxy configuration & routing rules
├── Sol.code-workspace                    # VSCode multi-folder workspace configuration
├── docker-compose.yml                    # Master Compose orchestrator (name: sol) with native 'include:'
├── ports.json                            # Master internal & external port registry (status + profile keys)
│
├── compose/                              # MODULAR DOMAIN COMPOSE STACKS ([..] = profiles: ["standby"])
│   ├── core.yml                          # Ingress & Identity (Caddy, Authentik x3, Arcane)
│   ├── monitoring.yml                    # Dashboards & Metrics (Glance, [Gatus, Dozzle, Beszel, Beszel-Agent, Dockge, Uptime Kuma, Homarr])
│   ├── media.yml                         # Media & *arr Suite (Jellyfin, Seerr, Radarr, Sonarr, Bazarr, Lidarr, Prowlarr, Byparr, [FlareSolverr, Recyclarr, Wizarr])
│   ├── download.yml                      # Ingestion (qBittorrent, Cross-Seed, [Unpackerr, qbit_manage, Flood])
│   ├── paperless.yml                     # Dedicated Document Stack (Web, Broker, DB, [Gotenberg, Tika, AI])
│   ├── knowledge.yml                     # Digital Notes & Reading (Ignis, [LeafWiki, Kavita, Calibre, Calibre-Web])
│   ├── coding.yml                        # Developer Workspaces (code-server, Coder)
│   └── utilities.yml                     # Storage Logistics & Notifications (Copyparty, ntfy, [Homebox, Vaultwarden, n8n, Home Assistant, Rclone (ops+standby), Rclone GUI])
│
├── web/                                  # STATIC WEB APPS & FRONTENDS
│   ├── fam/                              # Family Data Vault static app (/fam)
│   ├── scan/                             # Homebox Barcode Scanner PWA (/scan)
│   ├── aysynbm/                          # Async Bookmark Manager (/aysynbm)
│   └── mind/                             # Quartz Digital Garden build (/mind) -> quartz/public
│
├── scripts/                              # MAINTENANCE & AUTOMATION SCRIPTS
│   ├── backup.sh                         # PostgreSQL dumps + SQLite .backup snapshots + versioned rclone sync
│   ├── restore.sh                        # Disaster recovery, SQLite snapshot restore & psql dump import
│   ├── setup_jellyfin_metal.py           # Native Jellyfin VideoToolbox bootstrap (destructive wipe only with --reset)
│   └── test_cross_seed.sh                # Cross-seed permission/hardlink diagnostic (runs as -u "${PUID:-501}:${PGID:-20}")
│
├── coder/                                # Terraform Coder v2 Workspace Definitions
│   ├── main.tf                           # Single template (default.tf removed), prebuilt jj v0.28.2 musl
│   └── README.md
│
├── config/                               # PERSISTENT CONFIGURATION DIRECTORIES
│   ├── authentik/, bazarr/, caddy/, code-server/, coder/, copyparty/, cross-seed/
│   ├── glance/, jellyfin/, jellyfin_metal/, seerr/, lidarr/, ntfy/, paperless/, prowlarr/
│   ├── qbittorrent/, radarr/, sonarr/
│   ├── rclone/                           # rclone.conf (secret), filter.txt (local), filter.txt.example (tracked)
│   └── [standby / legacy]: authelia/, calibre/, calibre-web/, flood/, gatus/, homarr/, homeassistant/, kavita/, n8n/, overseerr/, plex/, qbit_manage/, readarr/, recyclarr/, syncthing/, unpackerr/, vaultwarden/, wizarr/
│
├── data/                                 # PERSISTENT APPLICATION STORAGE & MEDIA
│   ├── arcane/, authentik/, caddy/, copyparty/, ignis/, media/, ntfy/
│   ├── backups/                          # authentik_db.sql.gz, paperless_db.sql.gz
│   │   └── sqlite/                       # Atomic online SQLite .backup snapshots (path '/' encoded as '__')
│   ├── paperless/ (consume, data, db, export, media, redis, scripts)
│   ├── torrents/
│   └── [standby / legacy]: authelia/, beszel/, beszel_agent/, dockge/, homebox/, leafwiki/, n8n/, paperless-ai/, syncthing/, uptime-kuma/
│
├── docs/                                 # DOCUMENTATION & STATE AUDITS
│   ├── system_state/                     # 00-09 Master Architecture, Audit & Upgrade Documentation
│   ├── FLASH_LOCAL_VERIFICATION_RUNBOOK.md
│   └── archive/                          # Archived historic compose files, paperless.env & configs
│
├── logs/                                 # Central log repository (backup_<TIMESTAMP>.log, pruned after 30 days)
└── _backup_pre_refactor/                 # Pre-refactoring safety rollback snapshot
```

---

## 3. Master Port Allocation Matrix

The table below catalogs every network port across Sol. It covers exposed host ports, internal bridge endpoints, Caddy routes, authentication mechanisms, and lifecycle status. Standby rows keep their historic host ports (`prev`) for reference. Standby containers publish no host ports today except `beszel-agent` and `homeassistant` (`network_mode: host`) and `rclone` (`127.0.0.1:53682`).

| Host Port | Service | Internal Port | Protocol | Proxy Route / FQDN | Auth Enforcement | Stack Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`80`** | `caddy` | `80` | TCP | `*.vrg.rocks` | Edge Redirect to HTTPS | **Active (Edge)** |
| **`443`** | `caddy` | `443` | TCP/UDP | `*.vrg.rocks` | Edge TLS Termination (HTTP/3) | **Active (Edge)** |
| **`127.0.0.1:9000`** | `authentik-server` | `9000` | TCP | `auth.vrg.rocks` | Authentik Native | **Active (Loopback)** |
| **`127.0.0.1:9443`** | `authentik-server` | `9443` | TCP | `auth.vrg.rocks` | Authentik Native TLS | **Active (Loopback)** |
| **`42069`** | `qbittorrent` | `42069` | TCP/UDP | *(Direct Peer Wire)* | None (WAN Torrenting) | **Active** |
| **`8097`** *(native)* | `jellyfin-metal` | `8097` | TCP | `metal.vrg.rocks` -> `http://host.docker.internal:8097` | Jellyfin Native Auth | **Active (Native macOS)** |
| *Bridge Only* | `authentik-postgresql` | `5432` | TCP | `authentik-postgresql:5432` | Internal DB Password | **Active** |
| *Bridge Only* | `authentik-worker` | N/A | Worker Daemon | N/A | N/A | **Active** |
| *Bridge Only* | `glance` | `8080` | TCP | `dash.vrg.rocks` | Authentik (Forward Auth) | **Active** |
| *Bridge Only* | `arcane` | `3552` | TCP | `arcane.vrg.rocks` | Authentik (Forward & OIDC) | **Active** |
| *Bridge Only* | `jellyfin` | `8096` | TCP | `watch.vrg.rocks`, `jellyfin.vrg.rocks` | Jellyfin Native Auth | **Active** |
| *Bridge Only* | `radarr` | `7878` | TCP | `radarr.vrg.rocks` | Authentik (Forward Auth) | **Active** |
| *Bridge Only* | `sonarr` | `8989` | TCP | `sonarr.vrg.rocks` | Authentik (Forward Auth) | **Active** |
| *Bridge Only* | `bazarr` | `6767` | TCP | `bazarr.vrg.rocks` | Authentik (Forward Auth) | **Active** |
| *Bridge Only* | `lidarr` | `8686` | TCP | `lidarr.vrg.rocks` | Authentik (Forward Auth) | **Active** |
| *Bridge Only* | `prowlarr` | `9696` | TCP | `prowlarr.vrg.rocks` | Authentik (Forward Auth) | **Active** |
| *Bridge Only* | `seerr` | `5055` | TCP | `request.vrg.rocks`, `seerr.vrg.rocks`, `jellyseerr.vrg.rocks` | Authentik (Forward Auth) | **Active** |
| *Bridge Only* | `byparr` (alias `flaresolverr`) | `8191` | TCP | `byparr.vrg.rocks`, `flaresolverr.vrg.rocks` | Authentik (Forward Auth) | **Active** |
| *Bridge Only* | `qbittorrent` | `8080` | TCP | `qb.vrg.rocks`, `qbittorrent.vrg.rocks` | qBittorrent Native (no Authentik, Android client) | **Active** |
| *Bridge Only* | `cross-seed` | `2468` | TCP | `cs.vrg.rocks` | Authentik (Forward Auth) | **Active** |
| *Bridge Only* | `paperless-webserver` | `8000` | TCP | `docs.vrg.rocks`, `paperless.vrg.rocks` | Paperless OIDC (Authentik) | **Active** |
| *Bridge Only* | `paperless-broker` | `6379` | TCP | `paperless-broker:6379` | Internal Redis Protocol | **Active** |
| *Bridge Only* | `paperless-db` | `5432` | TCP | `paperless-db:5432` | Internal DB Password | **Active** |
| *Bridge Only* | `ntfy` | `80` | TCP | `ntfy.vrg.rocks` | Direct / Token / Open | **Active** |
| *Bridge Only* | `code-server` | `8443` | TCP | `code.vrg.rocks` | Authentik (Forward Auth) + code-server Argon2 Hash | **Active** |
| *Bridge Only* | `coder` | `7080` | TCP | `coder.vrg.rocks` | Authentik (Forward Auth) | **Active** |
| *Bridge Only* | `copyparty` | `3923` | TCP | `files.vrg.rocks`, `copyparty.vrg.rocks` | Authentik + Copyparty ACL | **Active** |
| *Bridge Only* | `ignis` | `8080` | TCP | `ignis.vrg.rocks` | Authentik (Forward Auth) | **Active** |
| *Caddy Static* | *Quartz Garden* | N/A | File | `mind.vrg.rocks` | Authentik (Forward Auth) | **Active** |
| *Caddy Static* | *Family Vault* | N/A | File | `fam.vrg.rocks` | Authentik (Forward Auth) | **Active** |
| *Caddy Static* | *Scanner PWA* | N/A | File | `scan.vrg.rocks` | Authentik (Forward Auth) | **Active** |
| *Caddy Static* | *Aysynbm* | N/A | File | `aysynbm.vrg.rocks` | Direct Static | **Active** |
| *LAN Upstream* | *Router WebUI* | `80` | TCP | `router.vrg.rocks` -> `http://192.168.50.1` | Authentik (Forward Auth) + Router Native | **Active** |
| *Redirect* | *Sol Redirect* | N/A | HTTP 302 | `sol.vrg.rocks` -> `dash.vrg.rocks/sol` | N/A | **Active** |
| `8123` *(host)* | `homeassistant` | `8123` | TCP | `home.vrg.rocks` -> `http://host.docker.internal:8123` | Authentik (Forward Auth) | *Standby (route active in Caddyfile)* |
| `7745` *(prev)* | `homebox` | `7745` | TCP | `inv.vrg.rocks` *(vhost commented)* | Authentik (Forward Auth) + CORS `https://scan.vrg.rocks` | *Standby (pending SQLite repair)* |
| *Bridge Only* | `flaresolverr` | `8191` | TCP | `flaresolverr.vrg.rocks` *(served by `byparr`)* | Authentik (Forward Auth) | *Standby* |
| *None* | `recyclarr` | N/A | CLI / Cron Daemon | N/A | N/A | *Standby* |
| *None* | `unpackerr` | N/A | Daemon | N/A | N/A | *Standby* |
| *Bridge Only* | `gatus` | `8080` | TCP | `status.vrg.rocks` *(vhost commented)* | Direct (Public Status Page) | *Standby* |
| `40010` *(prev)* | `beszel` (Hub) | `8090` | TCP | `beszel.vrg.rocks` | Authentik (Forward Auth) | *Standby* |
| `45876` *(host)* | `beszel-agent` | `45876` | TCP | *(Direct Agent Connect)* | Beszel Token / Key | *Standby* |
| `40020` *(prev)* | `dozzle` | `8080` | TCP | `dozzle.vrg.rocks` | Authentik (Forward Auth) | *Standby* |
| `40030` *(prev)* | `dockge` | `5001` | TCP | `dockge.vrg.rocks` | Authentik (Forward Auth) | *Standby* |
| `40040` *(prev)* | `uptime-kuma` | `3001` | TCP | `kuma.vrg.rocks` | Authentik (Forward Auth) | *Standby* |
| `7575` *(prev)* | `homarr` | `7575` | TCP | `homarr.vrg.rocks` | Authentik (Forward Auth) | *Standby* |
| `5690` *(prev)* | `wizarr` | `5690` | TCP | `wizarr.vrg.rocks` | Authentik (Forward Auth) | *Standby* |
| `5000` *(prev)* | `kavita` | `5000` | TCP | `kavita.vrg.rocks` | Authentik (Forward Auth) | *Standby* |
| `28080` *(prev)* | `calibre` | `8080` | TCP | `calibre.vrg.rocks` | Authentik (Forward Auth) | *Standby* |
| `8083` *(prev)* | `calibre-web` | `8083` | TCP | `calibre-web.vrg.rocks` | Authentik (Forward Auth) | *Standby* |
| `8181` *(prev)* | `qbit_manage` | `8181` | TCP | `qbm.vrg.rocks`, `qbit_manage.vrg.rocks` | Authentik (Forward Auth) | *Standby* |
| `42024` *(prev)* | `flood` | `3000` | TCP | `flood.vrg.rocks` | Authentik (Forward Auth) | *Standby* |
| `3000` *(prev)* | `paperless-gotenberg` | `3000` | TCP | `http://paperless-gotenberg:3000` | Internal API | *Standby* |
| `9998` *(prev)* | `paperless-tika` | `9998` | TCP | `http://paperless-tika:9998` | Internal API | *Standby* |
| `3000` *(prev)* | `paperless-ai` | `3000` | TCP | `paperless-ai.vrg.rocks` | Authentik (Forward Auth) | *Standby* |
| `80` *(prev)* | `vaultwarden` | `80` | TCP | `vault.vrg.rocks`, `pass.vrg.rocks` | Authentik (Forward Auth) | *Standby* |
| `5678` *(prev)* | `n8n` | `5678` | TCP | `n8n.vrg.rocks` | Authentik (Forward Auth) | *Standby* |
| `8080` *(prev)* | `leafwiki` | `8080` | TCP | `leaf.vrg.rocks` (`wiki.vrg.rocks` historic) | Authentik + Native JWT | *Standby* |
| `127.0.0.1:53682` | `rclone` (Task) | `53682` | TCP | *(CLI OAuth Port)* | CLI OAuth Callback | *Ops / Standby (`profiles: ["ops", "standby"]`)* |
| `5572` *(prev)* | `rclone-gui` | `5572` | TCP | `rclone.vrg.rocks` | Authentik + Basic Auth | *Standby* |
| `3333` *(prev)* | `bitwarden` | `8080` | TCP | `vault.vrg.rocks` | Bitwarden Native | *Archived (not in compose, `bitwarden.env` in `docs/archive/`)* |
| `9091` *(arch)* | `authelia` | `9091` | TCP | `auth.vrg.rocks` *(Legacy)* | Authelia Native | *Decommissioned* |
| `32400` *(arch)* | `plex` | `32400` | TCP | `plex.vrg.rocks` *(Legacy)* | Plex Claim / Auth | *Decommissioned* |
| `8787` *(arch)* | `readarr` | `8787` | TCP | `readarr.vrg.rocks` *(Legacy)* | Authentik (Forward Auth) | *Decommissioned* |
| `5050` *(arch)* | `overseerr` | `5055` | TCP | `overseerr.vrg.rocks` *(Legacy)* | Authentik (Forward Auth) | *Decommissioned* |
| `9876` *(arch)* | `filebrowser` | `80` | TCP | `filebrowser.vrg.rocks` *(Legacy)* | FileBrowser Native DB | *Decommissioned* |
| `12080` *(arch)* | `obsidian-remote` | `12080` | TCP | *(Direct Web GUI)* | Remote User / Pass | *Decommissioned* |
| `3000` *(arch)* | `obsidian` (KasmVNC) | `3000` | TCP | `obsidian.vrg.rocks` *(Legacy)* | Authentik (Forward Auth) | *Decommissioned* |
| `8384` *(arch)* | `syncthing` (GUI) | `8384` | TCP | `syncthing.vrg.rocks` *(Legacy)* | Syncthing Native GUI | *Decommissioned* |
| `22000` *(arch)* | `syncthing` (Sync) | `22000` | TCP/UDP | *(Sync Protocol)* | Syncthing Protocol | *Decommissioned* |
| `81` *(arch)* | `nginx-proxy-manager` | `81` | TCP | *(NPM Admin GUI)* | NPM Admin User/Pass | *Decommissioned* |

> [!IMPORTANT]
> The auth column for standby rows shows the policy written in the commented Caddyfile vhost. A standby route goes live only after two steps: start the container with `docker compose --profile standby up -d <service>`, then uncomment its vhost in `Caddyfile` and reload Caddy.
