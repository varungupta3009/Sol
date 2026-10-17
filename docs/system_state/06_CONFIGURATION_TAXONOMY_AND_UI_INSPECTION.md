# 06. Configuration Taxonomy & UI Inspection Roadmap

> **Scope:** Audit of container configuration storage mechanisms across `Sol`. Separates declarative file-based services from stateful database/UI-driven services that need browser exploration for full optimization.  
> **Host Root:** `/Users/vrg/Documents/Sol`  
> **Original Audit Date:** August 2026  
> **Last Synced to Ground Truth:** 2026-10-17  

---

## 1. Executive Summary & Configuration Taxonomy

To prepare for architectural and performance optimization, the Sol ecosystem splits into two configuration models:

```
                                  +---------------------------------------+
                                  |     Sol Server Container Ecosystem    |
                                  +-------------------+-------------------+
                                                      |
                         +----------------------------+----------------------------+
                         |                                                         |
                         v                                                         v
          [ CATEGORY A: DECLARATIVE FILES ]                         [ CATEGORY B: STATEFUL DB / UI ]
          (100% Inspectable via Filesystem)                         (Requires Browser UI Exploration)
          ---------------------------------                         ---------------------------------
          - Caddy (Caddyfile)                                       - Authentik (PostgreSQL 16)
          - Compose Stacks (compose/*.yml + profiles)               - Jellyfin (SQLite + Admin UI)
          - Glance (glance.yml)                                     - Jellyfin Metal (SQLite + Admin UI)
          - Cross-Seed (config.js)                                  - Seerr (SQLite + Settings)
          - Copyparty (copyparty.conf)                              - Radarr (SQLite + TRaSH Formats)
          - ntfy (server.yml)                                       - Sonarr (SQLite + Quality Profiles)
          - qBittorrent (qBittorrent.conf)                          - Prowlarr (SQLite + Indexers)
          - Coder (main.tf)                                         - Bazarr (SQLite + Providers)
          - code-server (settings.json)                             - Paperless-ngx (PostgreSQL 17)
          - Byparr (Environment Vars)                               - Arcane (SQLite + Stacks)
          - Ignis (Environment + Vaults)                            - Homebox (SQLite, Standby)
          - Rclone (filter.txt.example)
          - Scripts (backup.sh, restore.sh, setup_jellyfin_metal.py, test_cross_seed.sh)
```

---

## 2. Category A: 100% Declarative / File-Inspectable Services

These services store their full operational configuration in plain-text, YAML, JSON, JavaScript, INI, HCL, or shell files on the host filesystem. An AI agent can read, parse, and optimize them without visual browser inspection.

| Container / Artifact | Primary Configuration Path | Format | Status | What Has Been Fully Inspected & Understood |
| :--- | :--- | :--- | :--- | :--- |
| **`caddy`** | `./Caddyfile` | Caddyfile | Active | 27 active site blocks, 18 commented standby vhosts, TLS, HTTP/3, `(security_headers)`, `(optimize)`, `(authentik)`, `(static_site)` snippets, streaming transport for `watch`/`metal`, Homebox CORS restricted to `https://scan.vrg.rocks`. |
| **Compose stacks** | `docker-compose.yml`, `compose/*.yml` | YAML | Active | `include:` of 8 domain files, 24 active services, 26 services under `profiles: ["standby"]` / `["ops", "standby"]`, `glance.*` labels, DNS overrides, network aliases (`flaresolverr` on `byparr`, `jellyseerr` on `seerr`). |
| **`ports.json`** | `./ports.json` | JSON | Active | Per-service `internal_port`, `host_port`, `protocol`, `url`, `status` (`active` / `standby`), `profile`, `category`. Includes `jellyfin-metal` and `byparr`. |
| **`glance`** | `config/glance/config/glance.yml` | YAML | Active | Homepage feeds, weather, system monitors, container discovery labels, and dashboard bookmarks. |
| **`cross-seed`** | `config/cross-seed/config.js` | JavaScript | Active | Matching criteria, sleep delays, tracker mappings, `linkType: "symlink"`, action mode, injection targets. Compose adds `${DOCKER_DATA_DIR}:/data` next to `/downloads` for `dataDirs` scanning. |
| **`copyparty`** | `config/copyparty/copyparty.conf` | Plain Conf | Active | User accounts, permission flags (`r`, `w`, `m`, `d`), volume mounts, media streaming, and WebDAV endpoints. |
| **`ntfy`** | `config/ntfy/etc/ntfy/server.yml` | YAML | Active | Base URL, cache duration, attachment limits, authentication tokens, and message queue persistence. |
| **`qbittorrent`** | `config/qbittorrent/qBittorrent/qBittorrent.conf` | INI | Active | Listening port (`42069`), WebUI port (`8080`), speed limits, connection limits, and default save paths (`/downloads`, staged for `/data/torrents`). |
| **`coder`** | `coder/main.tf` | Terraform | Active | Single Docker workspace template (`default.tf` removed), `codercom/enterprise-base:ubuntu`, per-workspace home volume, agent metadata, `code-server` module `~> 1.0`, prebuilt `jj` `v0.28.2` musl download. |
| **`code-server`** | `config/code-server/data/User/settings.json` | JSON | Active | VS Code editor settings, themes, keybindings, and telemetry toggles. Mounts `/Server` and `/Documents`. |
| **`byparr`** | Declarative in `compose/media.yml` | ENV | Active | Port `8191`, `LOG_LEVEL: info`, DNS `1.1.1.1` / `9.9.9.9`, network alias `flaresolverr`. |
| **`flaresolverr`** | Declarative in `compose/media.yml` | ENV | Standby | Port `8191`, `LOG_LEVEL: info`, `profiles: ["standby"]`. |
| **`ignis`** | Declarative in `compose/knowledge.yml` | ENV | Active | Obsidian note sync directories (`data/ignis/vaults/`) and port allocations. |
| **`paperless-webserver`** | Declarative in `compose/paperless.yml` + `.env` | ENV | Active | `PAPERLESS_DBNAME`, `PAPERLESS_DBUSER`, `PAPERLESS_DBPASS`, `PAPERLESS_TASK_WORKERS: 2`, `PAPERLESS_THREADS_PER_WORKER: 2`, OCR languages, consume hooks, OIDC provider JSON. |
| **`authentik-server`** | Declarative in `compose/core.yml` + `.env` | ENV | Active | Loopback ports `127.0.0.1:9000` / `127.0.0.1:9443`, `AUTHENTIK_WEB__WORKERS: 2`, `shm_size: 512mb`. Worker runs without root or Docker socket. |
| **`arcane`** | Declarative in `compose/core.yml` + `.env` | ENV | Active | `LOG_LEVEL: info`, `LOG_JSON: "false"`, OIDC to Authentik, SQLite WAL `DATABASE_URL`. |
| **`rclone`** | `config/rclone/filter.txt.example` (tracked), `config/rclone/filter.txt` (local) | Rclone filter | Ops / Standby | Excludes `data/authentik/**`, `data/paperless/db/**`, `data/paperless/redis/**`, `**/*-wal`, `**/*-shm`, caches and bulk media. Includes `data/backups/**`, preshows, torrent metafiles. |
| **`scripts/backup.sh`** | `scripts/backup.sh` | Bash | Active | Safe `load_env`, PG dumps, SQLite `.backup` snapshots to `data/backups/sqlite/`, `rclone sync --backup-dir OneDrive:Sol-archive/<TIMESTAMP>`, `--profile ops` fallback. |
| **`scripts/restore.sh`** | `scripts/restore.sh` | Bash | Active | `--dry-run`, `--skip-cloud-pull`, `--restore-dbs`, `--start-stack`, SQLite snapshot restore, `gunzip -c ... \| docker exec -i ... psql` import. |
| **`scripts/setup_jellyfin_metal.py`** | `scripts/setup_jellyfin_metal.py` | Python | Active | Default relaunch preserves `config/jellyfin_metal/data/jellyfin.db`. `shutil.rmtree(CONFIG_DIR)` and wizard re-run only with `--reset`. |
| **`scripts/test_cross_seed.sh`** | `scripts/test_cross_seed.sh` | Bash | Active | `docker exec -u "${PUID:-501}:${PGID:-20}" cross-seed`, write and hardlink tests on `/external`, `/downloads`, and `/data/torrents` <-> `/data/media`. |

---

## 3. Category B: Database-Driven Services Requiring Browser UI Exploration

These services store their critical operational logic (rules, profiles, custom scoring formats, workflows, outposts, and hardware acceleration pipelines) in relational or SQLite databases. To tune performance, prevent media bloat, and remove bottlenecks, **we must inspect their web interfaces directly**.

> [!NOTE]
> Only Authentik publishes host ports, and only on loopback (`127.0.0.1:9000`, `127.0.0.1:9443`). Every other Category B service is bridge-only. Reach it through its Caddy FQDN, or from inside the network at the listed `http://<container>:<port>` address. Jellyfin Metal listens on host port `8097`.

---

### 1. Authentik (`auth.vrg.rocks` / `http://127.0.0.1:9000` on host)
* **Storage Engine:** PostgreSQL 16 (`data/authentik`, backed up as `data/backups/authentik_db.sql.gz`)
* **Why Browser Inspection is Essential:**
  - **Outposts:** Inspect the embedded Caddy forward-auth proxy outpost health and token lifespans. The worker no longer has Docker socket access, so Docker-managed outposts are not available.
  - **Applications & Providers:** Verify OAuth2/OIDC configurations for Paperless, Arcane, and Coder, plus proxy providers for the newly gated `dash`, `code`, `router`, `byparr`, and `flaresolverr` hostnames.
  - **Flows & Stages:** Audit password policies, session durations, MFA requirements, and error handling.
  - **Blueprints:** Inspect declarative blueprint imports and tenant configurations.

---

### 2. Jellyfin (`watch.vrg.rocks` / `http://jellyfin:8096`)
* **Storage Engine:** SQLite (`config/jellyfin/data/data/jellyfin.db`) + XML
* **Why Browser Inspection is Essential:**
  - **Hardware Acceleration:** The container cannot use Apple VideoToolbox. Verify software transcode thread allocation and throttling. Hardware transcoding runs on Jellyfin Metal instead.
  - **Library Setup & Scrapers:** Audit metadata scrapers (TMDb, TheTVDB, OMDb), image fetchers, and chapter thumbnail generators (Trickplay).
  - **Plugins:** Inspect active plugins (Introskipper, Fanart, OpenSubtitles) and their execution schedules.
  - **User & Transcode Limits:** Verify concurrent transcode limits, remote bitrate throttling, and user playback policies.

---

### 3. Jellyfin Metal (`metal.vrg.rocks` / `http://127.0.0.1:8097` on host)
* **Storage Engine:** SQLite (`config/jellyfin_metal/data/jellyfin.db`) + XML (`network.xml`)
* **Why Browser Inspection is Essential:**
  - **VideoToolbox Pipeline:** Confirm `HardwareAccelerationType: videotoolbox`, tonemapping, `EnableThrottling: true`, `ThrottleDelaySeconds: 120`, HEVC/AV1 encoding, and 10-bit HEVC/VP9 decoding as set by the `--reset` bootstrap.
  - **Libraries:** Verify `Movies` and `Shows` paths (internal `data/media/*` plus PANOPTICON).
  - **API Keys:** Confirm `Jellyseerr` and `Bazarr` keys if Seerr or Bazarr point at Metal.

---

### 4. Seerr (`request.vrg.rocks` / `http://seerr:5055`)
* **Storage Engine:** SQLite (`config/seerr/db/db.sqlite3`) + `settings.json`
* **Why Browser Inspection is Essential:**
  - **Radarr & Sonarr Integrations:** Audit server API connections, default root folder paths (`/data/media/movies` vs `/external`), and quality profile assignments (4K vs 1080p).
  - **User Request Rules:** Verify user request quotas, auto-approval rules, and notification dispatch webhooks.
  - **TMDb Discovery & Caching:** Check sync frequency with Jellyfin libraries and indexers.

---

### 5. Radarr (`radarr.vrg.rocks` / `http://radarr:7878`)
* **Storage Engine:** SQLite (`config/radarr/radarr.db`)
* **Why Browser Inspection is Essential:**
  - **TRaSH Guides Custom Formats:** Inspect active Custom Formats (for example HDR10+, Dolby Vision, AV1, Remux, Unwanted/Low Quality filters) and their score weighting. `recyclarr` is available under `--profile standby`.
  - **Quality Profiles:** Audit upgrade thresholds, cutoff unmet rules, and allowed video resolutions.
  - **Media Management:** Verify hardlink creation toggles, file renaming tokens, unmonitor deleted items, and root folder assignments.
  - **Download Client & Indexers:** Check qBittorrent category mapping (`movies`), seed ratio limits, remote path mapping during the `/downloads` to `/data/torrents` migration, and Prowlarr sync status.

---

### 6. Sonarr (`sonarr.vrg.rocks` / `http://sonarr:8989`)
* **Storage Engine:** SQLite (`config/sonarr/sonarr.db`)
* **Why Browser Inspection is Essential:**
  - **Quality & Release Profiles:** Audit custom scoring rules for anime, standard TV, and 4K releases.
  - **Media Management & Naming:** Verify season folder structures, multi-episode naming patterns, and atomic hardlink validation.
  - **Root Folders:** Check internal SSD paths vs external disk allocations.

---

### 7. Prowlarr (`prowlarr.vrg.rocks` / `http://prowlarr:9696`)
* **Storage Engine:** SQLite (`config/prowlarr/prowlarr.db`)
* **Why Browser Inspection is Essential:**
  - **Indexer Health & Priorities:** Inspect active Usenet and BitTorrent indexers, VIP status, rate limits, and failure rates.
  - **Sync Profiles:** Verify automatic schema synchronization to Radarr, Sonarr, and Lidarr.
  - **Challenge Solver Proxy Routing:** Confirm indexers with Cloudflare protection carry the `flaresolverr` tag and use `http://flaresolverr:8191`. That hostname resolves to `byparr` through its network alias.

---

### 8. Bazarr (`bazarr.vrg.rocks` / `http://bazarr:6767`)
* **Storage Engine:** SQLite (`config/bazarr/db/bazarr.db`) + `config.yaml`
* **Why Browser Inspection is Essential:**
  - **Subtitle Providers:** Audit provider accounts, daily API limits, and anti-captcha tokens.
  - **Language Profiles & Thresholds:** Check minimum score matching thresholds, forced subtitle rules, hearing-impaired (HI) tag removal, and audio language sync.
  - **Path Mappings:** Verify path translation between Bazarr container paths and Radarr/Sonarr internal paths.

---

### 9. Paperless-ngx (`docs.vrg.rocks` / `http://paperless-webserver:8000`)
* **Storage Engine:** PostgreSQL 17 (`data/paperless/db`, Debian `glibc` collation) + Redis 8 Alpine (`data/paperless/redis`)
* **Why Browser Inspection is Essential:**
  - **Workflows & Automation:** Audit automatic tagging, correspondent assignment, and document type categorization rules.
  - **Matching Algorithms:** Inspect matching criteria (Exact, Any, All, Fuzzy, Automatic ML classifier).
  - **Storage Paths:** Check physical folder organization rules for generated PDFs.
  - **Custom Fields:** Verify metadata fields (for example Invoice Numbers, Expiry Dates, Monetary Values).
  - **Task Queue:** Confirm 2 task workers x 2 threads per worker process bulk scans without queue backlog.

---

### 10. Homebox (`inv.vrg.rocks` / `http://homebox:7745`) (Standby)
* **Storage Engine:** SQLite (`data/homebox/data/homebox.db`)
* **Current State:** `profiles: ["standby"]`, vhost commented out, pending local SQLite database repair.
* **Why Browser Inspection is Essential (after repair):**
  - **Location & Category Hierarchy:** Audit physical room, container, and shelf taxonomy.
  - **Custom Fields & Warranties:** Check custom asset tracking schemas.
  - **Mobile Scanner Compatibility:** Verify API interaction with the `/scan` PWA frontend under the restricted `https://scan.vrg.rocks` CORS origin.

---

### 11. Arcane (`arcane.vrg.rocks` / `http://arcane:3552`)
* **Storage Engine:** SQLite (`data/arcane/data/arcane.db`)
* **Why Browser Inspection is Essential:**
  - **Stack Templates:** Inspect stored Docker Compose templates and container deployment hooks.
  - **Profile Awareness:** Confirm Arcane shows the 26 profiled standby services correctly and does not start them by accident.
  - **OIDC Authentication:** Verify user role mapping from Authentik.

---

## 4. Structured Phased Browser Exploration Plan

To run an efficient review, we explore the browser interfaces in 4 focused batches:

```
+-----------------------------------------------------------------------------------+
|                            PHASED UI EXPLORATION ROADMAP                          |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|  [ BATCH 1: INGRESS, IDENTITY & ORCHESTRATION ]                                   |
|  Targets: Authentik (auth.vrg.rocks), Glance (dash.vrg.rocks), Arcane (arcane.)   |
|  Focus: Outpost health, SSO flows, new edge-gated apps, dashboard monitors.       |
|                                                                                   |
|  [ BATCH 2: MEDIA STREAMING & REQUEST PIPELINE ]                                  |
|  Targets: Jellyfin (watch.), Jellyfin Metal (metal.), Seerr (request.vrg.rocks)   |
|  Focus: VideoToolbox vs software transcode, library scrapers, request quotas.     |
|                                                                                   |
|  [ BATCH 3: THE SERVARR AUTOMATION & INDEXING ENGINE ]                            |
|  Targets: Radarr (radarr.), Sonarr (sonarr.), Prowlarr (prowlarr.), Bazarr        |
|  Focus: TRaSH profiles, custom formats, hardlinks, Byparr proxy tag, indexers.    |
|                                                                                   |
|  [ BATCH 4: INGESTION, ARCHIVAL & LOGISTICS ]                                     |
|  Targets: qBittorrent (qb.vrg.rocks), Paperless-ngx (docs.), Homebox (inv.)       |
|  Focus: Save path migration, OCR classifiers, workflows, Homebox after repair.    |
|                                                                                   |
+-----------------------------------------------------------------------------------+
```
