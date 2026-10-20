# 00. Executive Topology: Sol Server Infrastructure

> **Environment:** `Sol` (macOS-based Home Server on OrbStack / Docker Engine, Apple Silicon M1 Pro)  
> **Base Workspace Path:** `/Users/vrg/Documents/Sol` (`DOCKER_BASE_DIR`)  
> **Primary Domain:** `*.vrg.rocks`  
> **Network Ingress:** Caddy v2 (`caddy:latest` / `v2.11.7`, Edge Reverse Proxy with Automatic TLS & HTTP/3 QUIC)  
> **Authentication Spine:** Tinyauth v5 (`v5.2.0`, Zero-Click Google OAuth 2.0 Forward-Auth & OIDC Provider at `auth.vrg.rocks`) + LLDAP (`v0.6.2`, Rust LDAP Directory at `ldap.vrg.rocks`)  
> **Orchestration:** Docker Compose V2 `include:` with `profiles: ["standby"]` and `profiles: ["ops"]`  
> **Original Audit Date:** August 2026  
> **Last Synced to Ground Truth:** 2026-10-20 (`docker-compose.yml`, `compose/*.yml`, `Caddyfile`, `ports.json`, `.env.example`, `scripts/*`, `scripts/launchd/*.plist`, `coder/main.tf`)  

---

## 1. System Overview & Architecture

**Sol** is a self-hosted home server built from modular container stacks on an Apple Silicon M1 Pro MacBook Pro (`16 GB` unified memory). The root `docker-compose.yml` (project `name: sol`) loads 8 domain files under `compose/` through Docker Compose V2 `include:`. Across **29 active containers (`29/29 healthy`, `~1.95 GiB` total RAM)** and **10 zero-container static web applications**, the stack delivers edge routing with zero-click Google SSO and native OIDC, unified LDAP identity reconciliation, hardware-accelerated media streaming, zero-copy ExFAT/APFS torrent and PVR automation, multi-language document OCR, cloud developer workspaces, and two-tier encrypted disaster recovery.

### Service Inventory Summary

| Tier | Count | Activation | Members |
| :--- | :---: | :--- | :--- |
| **Active Containers (Default Profile)** | `29` | `docker compose up -d` | `caddy`, `tinyauth`, `lldap`, `arcane`, `glance`, `jellyfin`, `seerr`, `radarr`, `sonarr`, `bazarr`, `lidarr`, `prowlarr`, `byparr`, `qbittorrent`, `qui`, `paperless-webserver`, `paperless-broker`, `paperless-db`, `ignis`, `readeck`, `code-server`, `coder`, `pocketbase`, `copyparty`, `ntfy`, `homebox`, `backrest`, `enclosed`, `airtrail` |
| **Standby / Ops Containers (Profiled)** | `16` | `docker compose --profile standby up -d <service>` (or `--profile ops` for `rclone`) | `gatus`, `dozzle`, `beszel`, `beszel-agent`, `recyclarr`, `wizarr`, `unpackerr`, `paperless-gotenberg`, `paperless-tika`, `paperless-ai`, `leafwiki`, `kavita`, `vaultwarden`, `n8n`, `homeassistant`, `rclone` (`ops`) |
| **Static Web Apps (Caddy Served)** | `10` | Mounted read-only into `caddy` (`0 MiB` container RAM) | `mind` (`Quartz`), `fam` (`Family Data Vault`), `scan` (`Homebox Scanner PWA`), `aysynbm` (`Bookmarks`), `tools` (`IT-Tools`), `chef` (`CyberChef`), `pdf` (`BentoPDF`), `speed` (`OpenSpeedTest`), `draw` (`Excalidraw`), `mi` (`MediaInfo WebASM` + `/mi/rom`) |
| **Native macOS (Standby)** | `1` | `python3 scripts/setup_jellyfin_metal.py` | `jellyfin-metal` (host port `8097`, `https://metal.vrg.rocks` commented in `Caddyfile`) |

> [!NOTE]
> Standby services are declared as full YAML service blocks with `profiles: ["standby"]`. `rclone` carries `profiles: ["ops"]` so manual tasks can launch it via `docker compose --profile ops run --rm rclone ...` without starting it during standby tests. Retired Era 1–4 containers (`authentik-*`, `flaresolverr`, `cross-seed`, `dockge`, `uptime-kuma`, `homarr`, `qbit_manage`, `flood`, `calibre`, `calibre-web`, `rclone-gui`) have been fully removed from `compose/*.yml` and `ports.json`.

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
                   | (Forward Auth / OIDC) |                       |
                   v                       v                       v
     +--------------------------+  +---------------+  +--------------------------+
     |     Tinyauth v5.2.0      |  | Glance v0.8.7 |  | 10 Static Web Apps       |
     | (auth.vrg.rocks, :3000)  |  | (dash. /sol)  |  |  - mind, fam, scan       |
     +-------------+------------+  +---------------+  |  - aysynbm, tools, chef  |
                   |                                  |  - pdf, speed, draw, mi  |
                   v                                  +--------------------------+
     +--------------------------+
     |   LLDAP v0.6.2 (:3890)   | ---> scripts/identity_sync.py (WatchPaths <50ms)
     |   (ldap.vrg.rocks)       |
     +-------------+------------+
                   |
  +----------------+----------------+----------------+----------------+
  |                                 |                                 |
  v                                 v                                 v
+----------------------+  +----------------------+  +----------------------+
| Media & Downloads    |  | Docs & Knowledge     |  | Workspaces & Ops     |
| - Jellyfin (:8096)   |  | - Paperless (:8000)  |  | - Code-Server (:8443)|
| - Seerr (:5055)      |  | - Redis 8 (:6379)    |  | - Coder v2 (:7080)   |
| - Radarr (:7878)     |  | - Postgres 17 (:5432)|  | - PocketBase (:8090) |
| - Sonarr (:8989)     |  |   (paperless +       |  | - Copyparty (:3923)  |
| - Bazarr (:6767)     |  |    airtrail DBs)     |  | - Homebox (:7745)    |
| - Lidarr (:8686)     |  | - Ignis (:8080)      |  | - Backrest (:9898)   |
| - Prowlarr (:9696)   |  | - Readeck (:8000)    |  | - Enclosed (:8787)   |
| - Byparr (:8191)     |  +----------------------+  | - AirTrail (:3000)   |
| - qBittorrent (:8080)|                            | - ntfy Push (:80)    |
| - QUI (:7476)        |                            | - Arcane (:3552)     |
+----------------------+                            +----------------------+
```

### Core Architecture Pillars

1. **Edge Routing, Static Suite & Security (`Caddy`):**
   - Serves as the sole public gateway (`80/tcp`, `443/tcp`, `443/udp` for HTTP/3 QUIC) across **33 active site blocks** (and 12 commented standby vhosts).
   - Issues Let's Encrypt TLS certificates per subdomain under `vrg.rocks`.
   - Enforces zero-click Google OAuth forward authentication against `tinyauth:3000` through the `(forward_auth)` snippet (`copy_headers Remote-User Remote-Name Remote-Email Remote-Groups`).
   - Applies `(security_headers)` (`nosniff`, `SAMEORIGIN`, `strict-origin-when-cross-origin`, `Permissions-Policy`, `X-Permitted-Cross-Domain-Policies: none`, HSTS `max-age=31536000; includeSubDomains; preload`, `-Server`).
   - Serves 10 static web applications (`mind`, `fam`, `scan`, `aysynbm`, `tools`, `chef`, `pdf`, `speed`, `draw`, `mi`) via `(static_site)`, wrapping `try_files` and `file_server` inside a `route { ... }` block so `forward_auth` always executes before filesystem lookups.

2. **Unified Identity & Access Management (`Tinyauth v5` + `LLDAP` + `identity_sync.py`):**
   - Replaced the heavy ~950 MiB Authentik stack with **Tinyauth v5** (`~25 MiB` RAM) + **LLDAP** (`~5 MiB` RAM).
   - **Tinyauth (`auth.vrg.rocks`)** handles edge forward-auth for internal dashboards/tools (`TINYAUTH_APPS_*` locks 17 admin/personal domains to `TINYAUTH_ADMIN_EMAILS`) and acts as the native OpenID Connect (OIDC) provider (`RS256`) for **Paperless-ngx**, **Arcane**, **Homebox**, **AirTrail**, **Coder**, **Readeck**, and **Jellyfin SSO**.
   - **LLDAP (`ldap.vrg.rocks`)** is the single source of truth for users (`vrg` and household member accounts), groups (`admin`, `family`, `friends`), and multi-email aliases.
   - **`scripts/identity_sync.py`** (triggered by `com.vrg.sol.identity-sync.plist` `WatchPaths` on `data/lldap/users.db*`) reads LLDAP's SQLite database directly in immutable mode (`<50ms` SHA-256 fast-path exit when unchanged) and reconciles `config/auth/users.json`, Tinyauth whitelist/OIDC consents, Jellyfin users/LDAP/SSO, Seerr, Paperless, AirTrail, Homebox, Readeck, and Copyparty.

3. **Media Orchestration, Zero-Copy ExFAT Symlinks & FUP Governance:**
   - **qBittorrent** (`qb.vrg.rocks`, WAN port `42069` TCP/UDP) and **QUI** (`qui.vrg.rocks`, Go WebUI + native cross-seeding + 26-tracker registry + 10 Airtel 3,333 GB FUP automation rules) form the ingestion core.
   - **Zero-Copy ExFAT Import Pipeline:** On torrent completion, `scripts/torrent_finished.py` (and the Servarr fallback hook `scripts/arr_symlink_dedupe.sh`) pre-creates relative symlinks (`../../../torrents/...`) on `/Volumes/PANOPTICON` (ExFAT) and triggers targeted Radarr/Sonarr disk scans, achieving `<1s` zero-copy imports across ExFAT and APFS.
   - **Prowlarr** manages indexers and routes Cloudflare challenges through **Byparr** (`ghcr.io/thephaseless/byparr:latest`, port `8191`, network alias `flaresolverr`, `1gb` `/dev/shm`, `512m` `/tmp` tmpfs, `BLOCK_MEDIA: "true"`).
   - **Jellyfin** (`watch.vrg.rocks`, `2g` `/tmp/jellyfin` RAM tmpfs, `Optimistic` SQLite locking) and **Seerr** (`request.vrg.rocks`, `v3.5.0` with 43 merged Overseerr+Seerr requests and Quick Connect + LDAP login) serve the household and friends.

4. **Document Archival & Knowledge Management (`Paperless-ngx`, `Ignis`, `Readeck`):**
   - **Paperless-ngx** runs with `paperless-broker` (`redis:8-alpine`, capped at `256mb` `volatile-lru`) and `paperless-db` (`postgres:17-alpine` musl, hosting both `paperless` and `airtrail` databases), multi-script OCR (`eng+hin+kan+pan`), PDF password decryption (`pre-consumption.py`), and `ntfy` push notifications.
   - **Ignis** (`ignis.vrg.rocks` / `notes.vrg.rocks`) synchronizes Obsidian vaults, and **Readeck** (`links.vrg.rocks`) provides read-later article archival with native Tinyauth OIDC.

5. **Developer Workspaces, Logistics & Utilities:**
   - **code-server** (`code.vrg.rocks`), **Coder v2** (`coder.vrg.rocks`, with active `sol-workspace` Terraform template in `coder/main.tf` and `group_add: ["0"]` Docker socket access), and **PocketBase** (`pb.vrg.rocks`) provide cloud development and backend sandboxes.
   - **Copyparty** (`files.vrg.rocks`), **Homebox** (`inv.vrg.rocks`), **Enclosed** (`send.vrg.rocks`), **AirTrail** (`fly.vrg.rocks`), **Backrest** (`backrest.vrg.rocks`), **ntfy** (`ntfy.vrg.rocks`), and **Arcane** (`arcane.vrg.rocks`) round out the active utility tier.

6. **Two-Tier Disaster Recovery (`Backrest` + `Restic` + `stage_db_backups.sh`):**
   - **`com.vrg.sol.db-stage.plist`** runs `scripts/stage_db_backups.sh` at `02:45` and `14:45` IST daily (via `/opt/homebrew/bin/python3` and OrbStack `redis:8-alpine` to avoid macOS TCC blocks on `~/Documents` and `/Volumes/PANOPTICON`), staging `paperless_db.sql.gz`, `airtrail_db.sql.gz`, `coder_db.sql.gz`, `coder_home.tar.gz`, `coder_volume_name.txt`, `symlinks_manifest.tsv` (`1,459` symlinks), and **29 WAL-complete SQLite snapshots** in `data/backups/sqlite/`.
   - **Backrest (`v1.14.1` + Restic `0.19.1`)** snapshots `/userdata/sol` twice daily (`03:00` & `15:00` IST) to `/Volumes/PANOPTICON/backups/sol-restic` and daily (`03:30` IST) to `rclone:OneDrive:Sol-Restic`.
   - **`scripts/restore.sh`** restores the complete server from local or cloud Restic onto bare metal in a single command.

---

## 2. Directory Layout & Taxonomy

```
/Users/vrg/Documents/Sol/
├── .env                                  # Centralized master environment variables & secrets (mode 0600, gitignored)
├── .env.example                          # Sanitized template for environment configuration (tracked)
├── .gitignore                            # Strict deny-by-default ignore rules with explicit template allowlists
├── Caddyfile                             # Active reverse proxy configuration & routing rules (33 active vhosts)
├── README.md                             # Quick-start & architectural overview
├── TODO.md                               # Completed architectural milestone ledger
├── docker-compose.yml                    # Master Compose orchestrator (name: sol) with native 'include:'
├── ports.json                            # Master internal & external port registry (46 entries: 29 active, 17 standby/ops)
│
├── compose/                              # MODULAR DOMAIN COMPOSE STACKS ([..] = profiles: ["standby"] / ["ops"])
│   ├── core.yml                          # Ingress, Identity & Stack Manager (caddy, tinyauth, lldap, arcane)
│   ├── monitoring.yml                    # Dashboards & Metrics (glance, [gatus, dozzle, beszel, beszel-agent])
│   ├── media.yml                         # Media & *arr Suite (jellyfin, seerr, radarr, sonarr, bazarr, lidarr, prowlarr, byparr, [recyclarr, wizarr])
│   ├── download.yml                      # Ingestion & Cross-Seed (qbittorrent, qui, [unpackerr])
│   ├── paperless.yml                     # Document Stack (paperless-webserver, paperless-broker, paperless-db, [gotenberg, tika, paperless-ai])
│   ├── knowledge.yml                     # Digital Notes & Bookmarks (ignis, readeck, [leafwiki, kavita])
│   ├── coding.yml                        # Developer Workspaces (code-server, coder, pocketbase)
│   └── utilities.yml                     # Logistics & Backups (copyparty, ntfy, homebox, backrest, enclosed, airtrail, [vaultwarden, n8n, homeassistant, rclone (ops)])
│
├── web/                                  # 9 STATIC WEB APPS MOUNTED INTO CADDY (+ quartz/public as 10th)
│   ├── fam/                              # Family Data Vault static app (/fam, includes vault.enc)
│   ├── scan/                             # Homebox Barcode Scanner PWA (/scan)
│   ├── aysynbm/                          # Async Bookmark Manager (/aysynbm)
│   ├── tools/                            # IT-Tools static bundle (/tools, managed by sync_static_tools.sh)
│   ├── chef/                             # CyberChef static bundle (/chef, managed by sync_static_tools.sh)
│   ├── pdf/                              # BentoPDF static bundle (/pdf, managed by sync_static_tools.sh)
│   ├── speed/                            # OpenSpeedTest static bundle (/speed, managed by sync_static_tools.sh)
│   ├── draw/                             # Excalidraw static bundle (/draw, managed by sync_static_tools.sh)
│   └── mi/                               # MediaInfo WebASM + NES ROM (/mi, managed by sync_static_tools.sh)
│
├── quartz/                               # Quartz v4 Digital Garden (mind.vrg.rocks -> quartz/public:/mind:ro)
│
├── scripts/                              # OPERATIONAL AUTOMATION SCRIPTS & LAUNCHAGENTS
│   ├── allowlist_user.sh                 # Declarative user onboarding helper (config/auth/users.json + identity_sync.py)
│   ├── arr_symlink_dedupe.sh             # Servarr CustomScript hook for relative ExFAT symlink deduplication
│   ├── backup.sh                         # Manual CLI wrapper for stage_db_backups.sh + Restic local/cloud backup
│   ├── identity_sync.py                  # One-way LLDAP -> Tinyauth/Jellyfin/Seerr/OIDC/Copyparty reconciler (<50ms fast-path)
│   ├── restore.sh                        # Bare-metal disaster recovery (Restic pull, symlinks, SQLite, PG, Coder, LaunchAgents)
│   ├── setup_jellyfin_metal.py           # Standby native macOS Jellyfin VideoToolbox bootstrap (:8097)
│   ├── stage_db_backups.sh               # Pre-backup staging (PG dumps, 29 WAL-complete SQLite snapshots, symlink manifest, Coder home)
│   ├── sync_static_tools.sh              # Version-pinned downloader/builder for web/{tools,chef,pdf,speed,draw,mi}
│   ├── torrent_finished.py               # qBittorrent completion hook (zero-copy ExFAT symlinks, Servarr scan, ntfy push)
│   ├── launchd/                          # Tracked macOS LaunchAgent templates installed into ~/Library/LaunchAgents/
│   │   ├── com.vrg.sol.db-stage.plist    # Runs stage_db_backups.sh at 02:45 & 14:45 daily via /opt/homebrew/bin/python3
│   │   └── com.vrg.sol.identity-sync.plist # Watches data/lldap/users.db* and triggers identity_sync.py
│   └── archive/                          # Historical one-off migration & diagnostic scripts
│       ├── merge_overseerr_history.py
│       ├── migrate_panopticon_live.py
│       └── test_cross_seed.sh
│
├── coder/                                # Terraform Coder v2 Workspace Definitions
│   ├── main.tf                           # Active 'sol-workspace' template pushed to Coder (prebuilt jj v0.28.2 musl + Bun)
│   └── README.md
│
├── config/                               # PERSISTENT SERVICE CONFIGURATIONS
│   ├── auth/                             # users.json (local), users.json.example (tracked)
│   ├── backrest/                         # config.json, excludes.txt (local) + *.example (tracked)
│   ├── bazarr/, caddy/, code-server/, coder/, copyparty/
│   ├── glance/                           # Tracked dashboard config (glance.yml) & custom CSS/SVG (user.css, sol.svg)
│   ├── jellyfin/, lidarr/, ntfy/, paperless/, prowlarr/, qbittorrent/
│   ├── qui/                              # qui.db + tracked tracker_registry.json (26 trackers + 10 FUP rules)
│   ├── radarr/, rclone/, seerr/, sonarr/
│   └── [standby]: gatus/, homeassistant/, kavita/, n8n/, recyclarr/, unpackerr/, vaultwarden/, wizarr/
│
├── data/                                 # PERSISTENT APPLICATION DATA, DATABASES & LOCAL MEDIA
│   ├── airtrail/, arcane/, backrest/, caddy/, copyparty/, enclosed/, homebox/
│   ├── ignis/, lldap/, ntfy/, pocketbase/, readeck/, tinyauth/
│   ├── backups/                          # paperless_db.sql.gz, airtrail_db.sql.gz, coder_db.sql.gz, coder_home.tar.gz,
│   │   │                                 # coder_volume_name.txt, symlinks_manifest.tsv
│   │   └── sqlite/                       # 29 clean WAL-complete SQLite snapshots (journal_mode=DELETE, 0 sidecars)
│   ├── media/                            # Internal APFS media (movies, tv, music, books, home-videos, preshows)
│   ├── paperless/                        # consume, data, db (PG 17 Alpine), export, media, redis, scripts
│   ├── torrents/                         # Internal APFS torrent payloads, .torrent metafiles (files/), cross-seed-links, qui-links
│   └── [standby]: beszel/, beszel_agent/, kavita/, leafwiki/, n8n/, paperless-ai/
│
├── docs/                                 # ARCHITECTURE & AUDIT DOCUMENTATION
│   ├── system_state/                     # 00-11 Master Architecture, Audit & Operations Suite
│   ├── FLASH_LOCAL_VERIFICATION_RUNBOOK.md
│   └── archive/                          # Historical compose files & legacy configs
│
└── logs/                                 # LaunchAgent & operational logs (db_stage.log, identity_sync.log)
```

---

## 3. Master Port Allocation Matrix

The table below catalogs every network port across Sol: exposed host ports, internal Docker bridge endpoints (`sol_default`), Caddy routes, authentication tiers, and stack status (`29` Active Containers, `10` Static Web Apps, `2` Utility/LAN Routes, `16` Standby/Ops Containers, and `1` Standby Native macOS App).

| Host Port | Service | Internal Port | Protocol | Proxy Route / FQDN | Auth Enforcement | Stack Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`80`** | `caddy` | `80` | TCP | `*.vrg.rocks` | Edge Redirect to HTTPS | **Active (Edge)** |
| **`443`** | `caddy` | `443` | TCP/UDP | `*.vrg.rocks` | Edge TLS Termination (HTTP/3 QUIC) | **Active (Edge)** |
| **`42069`** | `qbittorrent` | `42069` | TCP/UDP | *(Direct Peer Wire)* | None (WAN BitTorrent Wire) | **Active** |
| *Bridge Only* | `tinyauth` | `3000` | TCP | `auth.vrg.rocks` | Google OAuth 2.0 + Break-Glass Bcrypt | **Active** |
| *Bridge Only* | `lldap` | `3890`, `17170` | LDAP, HTTP | `ldap.vrg.rocks` | Tinyauth (Admin Only) + LLDAP Native | **Active** |
| *Bridge Only* | `arcane` | `3552` | TCP | `arcane.vrg.rocks` | Native Tinyauth OIDC (Admin Only) | **Active** |
| *Bridge Only* | `glance` | `8080` | TCP | `dash.vrg.rocks` (`/sol`, `/stats`, `/radar`) | Tinyauth (Forward Auth) | **Active** |
| *Bridge Only* | `jellyfin` | `8096` | TCP | `watch.vrg.rocks`, `jellyfin.vrg.rocks` | Jellyfin Native + LLDAP + Tinyauth OIDC SSO | **Active** |
| *Bridge Only* | `seerr` | `5055` | TCP | `request.vrg.rocks`, `seerr.vrg.rocks`, `jellyseerr.vrg.rocks` | Tinyauth (Forward Auth) + Jellyfin LDAP/QuickConnect | **Active** |
| *Bridge Only* | `radarr` | `7878` | TCP | `radarr.vrg.rocks` | Tinyauth (Admin Only) | **Active** |
| *Bridge Only* | `sonarr` | `8989` | TCP | `sonarr.vrg.rocks` | Tinyauth (Admin Only) | **Active** |
| *Bridge Only* | `bazarr` | `6767` | TCP | `bazarr.vrg.rocks` | Tinyauth (Admin Only) | **Active** |
| *Bridge Only* | `lidarr` | `8686` | TCP | `lidarr.vrg.rocks` | Tinyauth (Admin Only) | **Active** |
| *Bridge Only* | `prowlarr` | `9696` | TCP | `prowlarr.vrg.rocks` | Tinyauth (Admin Only) | **Active** |
| *Bridge Only* | `byparr` (alias `flaresolverr`) | `8191` | TCP | `byparr.vrg.rocks` (`flaresolverr.vrg.rocks` -> 301) | Tinyauth (Admin Only) | **Active** |
| *Bridge Only* | `qbittorrent` | `8080` | TCP | `qb.vrg.rocks`, `qbittorrent.vrg.rocks` | qBittorrent Native (Mobile Client Compatible) | **Active** |
| *Bridge Only* | `qui` | `7476` | TCP | `qui.vrg.rocks` | Tinyauth (Admin Only) | **Active** |
| *Bridge Only* | `paperless-webserver` | `8000` | TCP | `docs.vrg.rocks`, `paperless.vrg.rocks` | Native Tinyauth OIDC | **Active** |
| *Bridge Only* | `paperless-broker` | `6379` | TCP | `paperless-broker:6379` | Internal Redis Protocol (`256mb` cap) | **Active** |
| *Bridge Only* | `paperless-db` | `5432` | TCP | `paperless-db:5432` | Internal PostgreSQL 17 (`paperless` + `airtrail`) | **Active** |
| *Bridge Only* | `ignis` | `8080` | TCP | `ignis.vrg.rocks` (`notes.vrg.rocks` -> 301) | Tinyauth (Admin Only) | **Active** |
| *Bridge Only* | `readeck` | `8000` | TCP | `links.vrg.rocks` | Native Tinyauth OIDC | **Active** |
| *Bridge Only* | `code-server` | `8443` | TCP | `code.vrg.rocks` | Tinyauth (Admin Only) | **Active** |
| *Bridge Only* | `coder` | `7080` | TCP | `coder.vrg.rocks` | Native Tinyauth OIDC (Admin Only) | **Active** |
| *Bridge Only* | `pocketbase` | `8090` | TCP | `pb.vrg.rocks` (`/` -> `/_/` 302) | Tinyauth (Admin Only) + PocketBase Superuser | **Active** |
| *Bridge Only* | `copyparty` | `3923` | TCP | `files.vrg.rocks`, `copyparty.vrg.rocks` | Tinyauth (`Remote-User` IdP Header) + Copyparty ACL | **Active** |
| *Bridge Only* | `ntfy` | `80` | TCP | `ntfy.vrg.rocks` | Public Read / Tinyauth or Token on `POST`/`PUT` | **Active** |
| *Bridge Only* | `homebox` | `7745` | TCP | `inv.vrg.rocks` | Native Tinyauth OIDC + CORS `scan.vrg.rocks` | **Active** |
| *Bridge Only* | `backrest` | `9898` | TCP | `backrest.vrg.rocks` | Tinyauth (Admin Only) | **Active** |
| *Bridge Only* | `enclosed` | `8787` | TCP | `send.vrg.rocks` | Tinyauth on Note Creation (`/` & `POST /api/notes`), Public View | **Active** |
| *Bridge Only* | `airtrail` | `3000` | TCP | `fly.vrg.rocks` | Native Tinyauth OIDC | **Active** |
| *Caddy Static* | *Quartz Garden* | N/A | File (`/mind:ro`) | `mind.vrg.rocks` | Tinyauth (Admin Only) | **Active (Static)** |
| *Caddy Static* | *Family Data Vault* | N/A | File (`/fam:ro`) | `fam.vrg.rocks` | Tinyauth (Forward Auth) + Client AES-GCM | **Active (Static)** |
| *Caddy Static* | *Scanner PWA* | N/A | File (`/scan:ro`) | `scan.vrg.rocks` | Tinyauth (Admin Only) | **Active (Static)** |
| *Caddy Static* | *Aysynbm* | N/A | File (`/aysynbm:ro`) | `aysynbm.vrg.rocks` | Tinyauth (Admin Only) | **Active (Static)** |
| *Caddy Static* | *IT-Tools* | N/A | File (`/tools:ro`) | `tools.vrg.rocks` | Tinyauth (Forward Auth) | **Active (Static)** |
| *Caddy Static* | *CyberChef* | N/A | File (`/chef:ro`) | `chef.vrg.rocks` | Tinyauth (Forward Auth) | **Active (Static)** |
| *Caddy Static* | *BentoPDF* | N/A | File (`/pdf:ro`) | `pdf.vrg.rocks` | Tinyauth (Forward Auth) | **Active (Static)** |
| *Caddy Static* | *OpenSpeedTest* | N/A | File (`/speed:ro`) | `speed.vrg.rocks` | Tinyauth (Forward Auth) | **Active (Static)** |
| *Caddy Static* | *Excalidraw* | N/A | File (`/draw:ro`) | `draw.vrg.rocks` | Tinyauth (Forward Auth) | **Active (Static)** |
| *Caddy Static* | *MediaInfo + ROM* | N/A | File (`/mi:ro`) | `mi.vrg.rocks` | Tinyauth (Forward Auth) | **Active (Static)** |
| *LAN Upstream* | *Router WebUI* | `80` | TCP | `router.vrg.rocks` -> `http://192.168.50.1` | Tinyauth (Admin Only) + Router Native | **Active** |
| *Redirect* | *Sol Redirect* | N/A | HTTP 302 | `sol.vrg.rocks` -> `https://dash.vrg.rocks/sol` | N/A | **Active** |
| `8097` *(native)* | `jellyfin-metal` | `8097` | TCP | `metal.vrg.rocks` *(vhost commented)* | Jellyfin Native Auth | *Standby (Native macOS)* |
| *Bridge Only* | `gatus` | `8080` | TCP | `status.vrg.rocks` *(vhost commented)* | Tinyauth (Forward Auth) | *Standby* |
| *Bridge Only* | `dozzle` | `8080` | TCP | `dozzle.vrg.rocks` *(vhost commented)* | Tinyauth (Forward Auth) | *Standby* |
| *Bridge Only* | `beszel` | `8090` | TCP | `beszel.vrg.rocks` *(vhost commented)* | Tinyauth (Forward Auth) | *Standby* |
| *Bridge Only* | `beszel-agent` | `45876` | TCP | `beszel:8090` <- `beszel-agent:45876` | Beszel SSH Key / Token | *Standby* |
| *None* | `recyclarr` | N/A | Cron Daemon | N/A | N/A | *Standby* |
| *Bridge Only* | `wizarr` | `5690` | TCP | `wizarr.vrg.rocks` *(vhost commented)* | Tinyauth (Forward Auth) | *Standby* |
| *None* | `unpackerr` | N/A | Daemon | N/A | N/A | *Standby* |
| *Bridge Only* | `paperless-gotenberg` | `3000` | TCP | `http://paperless-gotenberg:3000` | Internal API | *Standby* |
| *Bridge Only* | `paperless-tika` | `9998` | TCP | `http://paperless-tika:9998` | Internal API | *Standby* |
| *Bridge Only* | `paperless-ai` | `3000` | TCP | `paperless-ai.vrg.rocks` *(vhost commented)* | Tinyauth (Forward Auth) | *Standby* |
| *Bridge Only* | `leafwiki` | `8080` | TCP | `leaf.vrg.rocks` *(vhost commented)* | Tinyauth (Forward Auth) + Native JWT | *Standby* |
| *Bridge Only* | `kavita` | `5000` | TCP | `kavita.vrg.rocks` *(vhost commented)* | Tinyauth (Forward Auth) | *Standby* |
| *Bridge Only* | `vaultwarden` | `80` | TCP | `vault.vrg.rocks`, `pass.vrg.rocks` *(vhost commented)* | Tinyauth (Forward Auth) | *Standby* |
| *Bridge Only* | `n8n` | `5678` | TCP | `n8n.vrg.rocks` *(vhost commented)* | Tinyauth (Forward Auth) | *Standby* |
| `8123` *(host)* | `homeassistant` | `8123` | TCP | `home.vrg.rocks` *(vhost commented)* | Tinyauth (Forward Auth) | *Standby* |
| `127.0.0.1:53682` | `rclone` | `53682` | TCP | *(CLI OAuth Callback)* | CLI OAuth Callback | *Ops (`profiles: ["ops"]`)* |
