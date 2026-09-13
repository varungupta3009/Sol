# 00. Executive Topology: Sol Server Infrastructure

> **Environment:** `Sol` (macOS-based Home Server on OrbStack / Docker Engine)  
> **Base Workspace Path:** `/Users/vrg/Documents/Sol`  
> **Primary Domain:** `*.vrg.rocks`  
> **Network Ingress:** Caddy v2 (Edge Reverse Proxy with Automatic TLS & HTTP/3)  
> **Authentication Engine:** Authentik Server (Forward Auth & OIDC Provider)  
> **Audit Date:** August 2026  

---

## 1. System Overview & Architecture

**Sol** is a unified, self-hosted home server ecosystem architected around modular containerized stacks managed via Docker Compose V2 `include:`. The infrastructure delivers zero-trust edge routing, centralized identity management, high-throughput media streaming and PVR automation, document indexing with OCR and security sanitization, multi-tier development environments, and cloud backup synchronization.

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
     |   (:9000, :9443 / auth)  |  | (dash.)       |  |  - /mind (Quartz Garden) |
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

### Core Architecture Pillars

1. **Edge Routing & Ingress (`Caddy`):**
   - Serves as the sole public gateway (`80/tcp`, `443/tcp`, `443/udp` for HTTP/3).
   - Terminates Let's Encrypt TLS certificates wildcard-free per subdomain under `vrg.rocks`.
   - Enforces forward authentication against Authentik outpost endpoints via the `(authentik)` snippet.
   - Hosts static web applications (`Quartz`, `Vault`, `Scan`, `Aysynbm`) directly via high-performance `file_server` directives.

2. **Unified Identity & Access Management (`Authentik`):**
   - Centralizes authentication across administrative dashboards and backend utilities.
   - Operates embedded forward-auth outpost (`/outpost.goauthentik.io/auth/caddy`) for legacy web interfaces lacking native OIDC.
   - Supplies native OIDC single sign-on (SSO) to applications such as **Arcane** and **Paperless-ngx**.

3. **Media Orchestration & Ingestion Pipeline:**
   - **qBittorrent** acts as the core bittorrent daemon with incoming port `42069` forwarded directly on WAN.
   - **Cross-Seed** monitors active client torrents and auto-injects matches via symlinks to optimize ratio across multiple trackers.
   - **Prowlarr** manages indexer health, leveraging **FlareSolverr** for Cloudflare captcha bypass.
   - **Radarr**, **Sonarr**, **Lidarr**, and **Bazarr** coordinate metadata, downloads, subtitle synchronization, and file renaming.
   - **Jellyfin** serves hardware-accelerated streams natively to LAN TVs and remote clients.
   - **Seerr** handles user requests, TMDb discovery, and automated *arr ingestion.

4. **Document Archival & Information Capture (`Paperless-ngx`):**
   - Dedicated document pipeline with Redis broker (`paperless-broker`) and PostgreSQL 17 database (`paperless-db`).
   - Integrated Python pre-consumption hook (`pre-consumption.py` using `pikepdf`) for automated password-protected PDF decryption and embedded attachment extraction.
   - Post-consumption webhook (`ntfy_notify.sh`) delivering structured push notifications via **ntfy**.

5. **Developer Workspaces & File Logistics:**
   - **code-server** provides web-based VSCode direct access to `/Users/vrg/Documents/Sol` (`/Server`).
   - **Coder v2** provides programmable container workspaces provisioned via local Terraform (`coder/main.tf`).
   - **Copyparty** provides multi-user, multi-port, authenticated WebDAV / file sharing across internal SSD and external media drives.
   - **Homebox** tracks physical inventory with an optimized mobile barcode scanner PWA (`/scan`).
   - **Arcane** manages local Docker containers and compose stacks with OIDC authentication.

6. **Storage Hierarchy & Disaster Recovery:**
   - Base server directory structured cleanly into `./config` (persistent service state), `./data` (databases, caches, media root), and `./logs` (audit traces).
   - Automated cloud backup pipeline via `scripts/backup.sh` utilizing an **Rclone** filter (`config/rclone/filter.txt`) synchronizing critical configuration state to OneDrive while ignoring multi-terabyte bulk media and transient caches.

---

## 2. Directory Layout & Taxonomy

```
/Users/vrg/Documents/Sol/
├── .env                                  # Centralized master environment variables & secrets
├── .env.example                          # Sanitized template for environment configuration
├── Caddyfile                             # Active reverse proxy configuration & routing rules
├── Sol.code-workspace                    # VSCode multi-folder workspace configuration
├── docker-compose.yml                    # Master Compose orchestrator with native 'include:'
├── ports.json                            # Master internal & external port registry
│
├── compose/                              # MODULAR DOMAIN COMPOSE STACKS
│   ├── core.yml                          # Ingress & Identity (Caddy, Authentik, Arcane)
│   ├── monitoring.yml                    # Dashboards & Metrics (Glance, [Beszel, Kuma, Homarr])
│   ├── media.yml                         # Media & *arr Suite (Jellyfin, Seerr, Radarr, etc.)
│   ├── download.yml                      # Ingestion (qBittorrent, Cross-Seed, [qbit_manage, flood])
│   ├── paperless.yml                     # Dedicated Document Stack (Web, Broker, DB, [Gotenberg, Tika, AI])
│   ├── knowledge.yml                     # Digital Notes & Reading (Ignis, [LeafWiki, Kavita, Calibre])
│   ├── coding.yml                        # Developer Workspaces (code-server, Coder)
│   └── utilities.yml                     # Storage Logistics & Notifications (Copyparty, Homebox, ntfy)
│
├── web/                                  # STATIC WEB APPS & FRONTENDS
│   ├── fam/                              # Family Data Vault static app (/fam)
│   ├── scan/                             # Homebox Barcode Scanner PWA (/scan)
│   ├── aysynbm/                          # Async Bookmark Manager (/aysynbm)
│   └── mind/                             # Quartz Digital Garden build (/mind) -> quartz/public
│
├── scripts/                              # MAINTENANCE & AUTOMATION SCRIPTS
│   ├── backup.sh                         # Rclone to OneDrive backup automation script
│   ├── restore.sh                        # Disaster recovery & cold-start restore script
│   ├── setup_jellyfin_metal.py           # Native Jellyfin VideoToolbox bootstrap & API setup
│   └── test_cross_seed.sh                # Diagnostic script for cross-seed permissions/hardlinks
│
├── coder/                                # Terraform Coder v2 Workspace Definitions
│   ├── main.tf, default.tf, README.md
│
├── config/                               # PERSISTENT CONFIGURATION DIRECTORIES
│   ├── authentik/, bazarr/, caddy/, code-server/, coder/, copyparty/, cross-seed/
│   ├── glance/, jellyfin/, seerr/, lidarr/, ntfy/, paperless/, prowlarr/
│   ├── qbittorrent/, radarr/, rclone/, sonarr/
│   └── [inactive]: authelia/, calibre/, calibre-web/, flood/, homarr/, homeassistant/, kavita/, n8n/, overseerr/, plex/, qbit_manage/, readarr/, syncthing/, vaultwarden/, wizarr/
│
├── data/                                 # PERSISTENT APPLICATION STORAGE & MEDIA
│   ├── arcane/, authentik/, caddy/, copyparty/, homebox/, ignis/, media/, ntfy/
│   ├── paperless/ (consume, data, db, export, media, redis, scripts)
│   ├── torrents/
│   └── [inactive]: authelia/, beszel/, beszel_agent/, dockge/, leafwiki/, n8n/, paperless-ai/, syncthing/, uptime-kuma/
│
├── docs/                                 # DOCUMENTATION & STATE AUDITS
│   ├── system_state/                     # 00-05 Master Architecture & Migration Documentation
│   └── archive/                          # Archived historic compose files, paperless.env & configs
│
├── logs/                                 # Central log repository (Backup execution & audit logs)
└── _backup_pre_refactor/                 # Pre-refactoring safety rollback snapshot
```

---

## 3. Master Port Allocation Matrix

The table below catalogs every network port across Sol, spanning exposed host ports, internal bridge network endpoints, reverse proxy routing rules, authentication mechanisms, and operational lifecycle status.

| Host Port | Service | Internal Port | Protocol | Proxy Route / FQDN | Auth Enforcement | Stack Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`80`** | `caddy` | `80` | TCP | `*.vrg.rocks` | Edge Redirect to HTTPS | **Active (Edge)** |
| **`443`** | `caddy` | `443` | TCP/UDP | `*.vrg.rocks` | Edge TLS Termination | **Active (Edge)** |
| **`9000`** | `authentik-server` | `9000` | TCP | `auth.vrg.rocks` | Authentik Native | **Active** |
| **`9443`** | `authentik-server` | `9443` | TCP | `auth.vrg.rocks` | Authentik Native TLS | **Active** |
| **`42069`** | `qbittorrent` | `42069` | TCP/UDP | *(Direct Peer Wire)* | None (WAN Torrenting) | **Active** |
| *Bridge Only* | `authentik-postgresql` | `5432` | TCP | `authentik-postgresql:5432` | Internal DB Password | **Active** |
| *Bridge Only* | `glance` | `8080` | TCP | `dash.vrg.rocks` | Direct / Application | **Active** |
| *Bridge Only* | `arcane` | `3552` | TCP | `arcane.vrg.rocks` | Authentik (Forward & OIDC)| **Active** |
| *Bridge Only* | `jellyfin` | `8096` | TCP | `watch.vrg.rocks`, `jellyfin.vrg.rocks` | Jellyfin Native Auth | **Active** |
| *Bridge Only* | `radarr` | `7878` | TCP | `radarr.vrg.rocks` | Authentik (Forward Auth) | **Active** |
| *Bridge Only* | `sonarr` | `8989` | TCP | `sonarr.vrg.rocks` | Authentik (Forward Auth) | **Active** |
| *Bridge Only* | `bazarr` | `6767` | TCP | `bazarr.vrg.rocks` | Authentik (Forward Auth) | **Active** |
| *Bridge Only* | `lidarr` | `8686` | TCP | `lidarr.vrg.rocks` | Authentik (Forward Auth) | **Active** |
| *Bridge Only* | `prowlarr` | `9696` | TCP | `prowlarr.vrg.rocks` | Authentik (Forward Auth) | **Active** |
| *Bridge Only* | `seerr` | `5055` | TCP | `request.vrg.rocks`, `seerr.vrg.rocks`, `jellyseerr.vrg.rocks` | Authentik (Forward Auth) | **Active** |
| *Bridge Only* | `flaresolverr` | `8191` | TCP | `flaresolverr.vrg.rocks` | Direct Internal API | **Active** |
| *Bridge Only* | `qbittorrent` | `8080` | TCP | `qb.vrg.rocks`, `qbittorrent.vrg.rocks` | qBittorrent Native | **Active** |
| *Bridge Only* | `cross-seed` | `2468` | TCP | `cs.vrg.rocks` | Authentik (Forward Auth) | **Active** |
| *Bridge Only* | `paperless-webserver` | `8000` | TCP | `docs.vrg.rocks`, `paperless.vrg.rocks` | Paperless OIDC (Authentik)| **Active** |
| *Bridge Only* | `paperless-broker` | `6379` | TCP | `paperless-broker:6379` | Internal Redis Protocol | **Active** |
| *Bridge Only* | `paperless-db` | `5432` | TCP | `paperless-db:5432` | Internal DB Password | **Active** |
| *Bridge Only* | `ntfy` | `80` | TCP | `ntfy.vrg.rocks` | Direct / Token / Open | **Active** |
| *Bridge Only* | `code-server` | `8443` | TCP | `code.vrg.rocks` | code-server Argon2 Hash | **Active** |
| *Bridge Only* | `coder` | `7080` | TCP | `coder.vrg.rocks` | Authentik (Forward Auth) | **Active** |
| *Bridge Only* | `copyparty` | `3923` | TCP | `files.vrg.rocks`, `copyparty.vrg.rocks`| Authentik + Copyparty ACL | **Active** |
| *Bridge Only* | `homebox` | `7745` | TCP | `inv.vrg.rocks` | Authentik (Forward Auth) | **Active** |
| *Bridge Only* | `ignis` | `8080` | TCP | `ignis.vrg.rocks` | Authentik (Forward Auth) | **Active** |
| *Caddy Static* | *Quartz Garden* | N/A | File | `mind.vrg.rocks` | Authentik (Forward Auth) | **Active** |
| *Caddy Static* | *Family Vault* | N/A | File | `fam.vrg.rocks` | Authentik (Forward Auth) | **Active** |
| *Caddy Static* | *Scanner PWA* | N/A | File | `scan.vrg.rocks` | Authentik (Forward Auth) | **Active** |
| *Caddy Static* | *Aysynbm* | N/A | File | `aysynbm.vrg.rocks` | Direct Static | **Active** |
| *LAN Upstream* | *Router WebUI* | `80` | TCP | `router.vrg.rocks` | Router Native (`192.168.50.1`)| **Active** |
| *Redirect* | *Sol Redirect* | N/A | HTTP 302 | `sol.vrg.rocks` -> `dash.vrg.rocks/sol`| N/A | **Active** |
| `40010` *(prev)* | `beszel` (Hub) | `8090` | TCP | `beszel.vrg.rocks` | Authentik (Forward Auth) | *Disabled / Inactive* |
| `45876` *(host)* | `beszel-agent` | `45876` | TCP | *(Direct Agent Connect)* | Beszel Token / Key | *Disabled / Inactive* |
| `40020` *(prev)* | `dozzle` | `8080` | TCP | `dozzle.vrg.rocks` | Authentik (Forward Auth) | *Disabled / Inactive* |
| `40030` *(prev)* | `dockge` | `5001` | TCP | `dockge.vrg.rocks` | Authentik (Forward Auth) | *Disabled / Inactive* |
| `40040` *(prev)* | `uptime-kuma` | `3001` | TCP | `kuma.vrg.rocks` | Authentik (Forward Auth) | *Disabled / Inactive* |
| `7575` *(prev)* | `homarr` | `7575` | TCP | `homarr.vrg.rocks` | Authentik (Forward Auth) | *Disabled / Inactive* |
| `5690` *(prev)* | `wizarr` | `5690` | TCP | `wizarr.vrg.rocks` | Authentik (Forward Auth) | *Disabled / Inactive* |
| `5000` *(prev)* | `kavita` | `5000` | TCP | `kavita.vrg.rocks` | Authentik (Forward Auth) | *Disabled / Inactive* |
| `28080` *(prev)* | `calibre` | `8080` | TCP | `calibre.vrg.rocks` | Authentik (Forward Auth) | *Disabled / Inactive* |
| `8083` *(prev)* | `calibre-web` | `8083` | TCP | `calibre-web.vrg.rocks` | Authentik (Forward Auth) | *Disabled / Inactive* |
| `8181` *(prev)* | `qbit_manage` | `8181` | TCP | `qbm.vrg.rocks`, `qbit_manage.vrg.rocks`| Authentik (Forward Auth) | *Disabled / Inactive* |
| `42024` *(prev)* | `flood` | `3000` | TCP | `flood.vrg.rocks` | Authentik (Forward Auth) | *Disabled / Inactive* |
| `3000` *(prev)* | `paperless-gotenberg` | `3000` | TCP | `http://paperless-gotenberg:3000` | Internal API | *Disabled / Inactive* |
| `9998` *(prev)* | `paperless-tika` | `9998` | TCP | `http://paperless-tika:9998` | Internal API | *Disabled / Inactive* |
| `3000` *(prev)* | `paperless-ai` | `3000` | TCP | `paperless-ai.vrg.rocks` | Direct / Unauthenticated| *Disabled / Inactive* |
| `80` *(prev)* | `vaultwarden` | `80` | TCP | `vault.vrg.rocks`, `pass.vrg.rocks` | Authentik (Forward Auth) | *Disabled / Inactive* |
| `3333` *(prev)* | `bitwarden` | `8080` | TCP | `vault.vrg.rocks` | Bitwarden Native | *Disabled / Inactive* |
| `5678` *(prev)* | `n8n` | `5678` | TCP | `n8n.vrg.rocks` | Authentik (Forward Auth) | *Disabled / Inactive* |
| `8123` *(host)* | `homeassistant` | `8123` | TCP | `home.vrg.rocks` | Authentik (Forward Auth) | *Disabled / Inactive* |
| `8080` *(prev)* | `leafwiki` | `8080` | TCP | `leaf.vrg.rocks`, `wiki.vrg.rocks` | Authentik + Native JWT | *Disabled / Inactive* |
| `53682` *(prev)* | `rclone` (Task) | `53682` | TCP | *(CLI OAuth Port)* | CLI OAuth Callback | *Disabled / Inactive* |
| `5572` *(prev)* | `rclone-gui` | `5572` | TCP | `rclone.vrg.rocks` | Authentik + Basic Auth | *Disabled / Inactive* |
| `9091` *(arch)* | `authelia` | `9091` | TCP | `auth.vrg.rocks` *(Legacy)* | Authelia Native | *Decommissioned* |
| `32400` *(arch)* | `plex` | `32400` | TCP | `plex.vrg.rocks` *(Legacy)* | Plex Claim / Auth | *Decommissioned* |
| `8787` *(arch)* | `readarr` | `8787` | TCP | `readarr.vrg.rocks` *(Legacy)* | Authentik (Forward Auth) | *Decommissioned* |
| `5050` *(arch)* | `overseerr` | `5055` | TCP | `overseerr.vrg.rocks` *(Legacy)*| Authentik (Forward Auth) | *Decommissioned* |
| `9876` *(arch)* | `filebrowser` | `80` | TCP | `filebrowser.vrg.rocks` *(Legacy)*| FileBrowser Native DB | *Decommissioned* |
| `12080` *(arch)* | `obsidian-remote` | `12080`| TCP | *(Direct Web GUI)* | Remote User / Pass | *Decommissioned* |
| `3000` *(arch)* | `obsidian` (KasmVNC) | `3000` | TCP | `obsidian.vrg.rocks` *(Legacy)* | Authentik (Forward Auth) | *Decommissioned* |
| `8384` *(arch)* | `syncthing` (GUI) | `8384` | TCP | `syncthing.vrg.rocks` *(Legacy)*| Syncthing Native GUI | *Decommissioned* |
| `22000` *(arch)* | `syncthing` (Sync) | `22000`| TCP/UDP| *(Sync Protocol)* | Syncthing Protocol | *Decommissioned* |
| `81` *(arch)* | `nginx-proxy-manager`| `81` | TCP | *(NPM Admin GUI)* | NPM Admin User/Pass | *Decommissioned* |
