# 06. Configuration Taxonomy & UI Inspection Roadmap

> **Scope:** Comprehensive audit of container configuration storage mechanisms across `Sol`. Identifies declarative file-based services vs. stateful database/UI-driven services requiring browser exploration for full optimization.  
> **Host Root:** `/Users/vrg/Documents/Sol`  
> **Audit Date:** August 2026  

---

## 1. Executive Summary & Configuration Taxonomy

To prepare for deep architectural and performance optimizations, the Sol ecosystem is categorized into two distinct configuration models:

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
          - Glance (glance.yml)                                     - Jellyfin (SQLite + Admin UI)
          - Cross-Seed (config.js)                                  - Jellyseerr (SQLite + Settings)
          - Copyparty (copyparty.conf)                              - Radarr (SQLite + TRaSH Formats)
          - ntfy (server.yml)                                       - Sonarr (SQLite + Quality Profiles)
          - qBittorrent (qBittorrent.conf)                          - Prowlarr (SQLite + Indexers)
          - Coder (main.tf / default.tf)                            - Bazarr (SQLite + Providers)
          - code-server (settings.json)                             - Paperless-ngx (PostgreSQL 17)
          - FlareSolverr (Environment Vars)                         - Homebox (SQLite + Custom Fields)
          - Ignis (Environment + Vaults)                            - Arcane (SQLite + Stacks)
```

---

## 2. Category A: 100% Declarative / File-Inspectable Services

These services store their entire operational configuration in plain-text, YAML, JSON, JavaScript, or INI files directly on the host filesystem. An AI agent can read, parse, and optimize these completely without visual browser inspection.

| Container | Primary Configuration Path | Format | Status | What Has Been Fully Inspected & Understood |
| :--- | :--- | :--- | :--- | :--- |
| **`caddy`** | `./Caddyfile` | Caddyfile | Active | Ingress routing, TLS, HTTP/3, security headers, compression, Authentik forward-auth endpoints, and static web routing. |
| **`glance`** | `config/glance/config/glance.yml` | YAML | Active | Homepage feeds, weather, system monitors, container discovery labels, and dashboard bookmarks. |
| **`cross-seed`** | `config/cross-seed/config.js` | JavaScript | Active | Matching criteria, sleep delays, tracker mappings, `linkType: "symlink"`, action mode, and injection targets. |
| **`copyparty`** | `config/copyparty/copyparty.conf` | Plain Conf | Active | User accounts, permission flags (`r`, `w`, `m`, `d`), volume mounts, media streaming, and WebDAV endpoints. |
| **`ntfy`** | `config/ntfy/etc/ntfy/server.yml` | YAML | Active | Base URL, cache duration, attachment limits, authentication tokens, and message queue persistence. |
| **`qbittorrent`** | `config/qbittorrent/qBittorrent/qBittorrent.conf` | INI | Active | Listening port (`42069`), WebUI port (`8080`), speed limits, connection limits, and default save paths. |
| **`coder`** | `coder/main.tf`, `coder/default.tf` | Terraform | Active | Local Docker workspace templates, CPU/memory quotas, and development environment definitions. |
| **`code-server`** | `config/code-server/data/User/settings.json` | JSON | Active | VS Code editor settings, themes, keybindings, and telemetry toggles. |
| **`flaresolverr`** | Declarative in `compose/media.yml` | ENV | Active | Port `8191`, log levels, and Cloudflare challenge timeout handlers. |
| **`ignis`** | Declarative in `compose/knowledge.yml` | ENV | Active | Obsidian note sync directories (`data/ignis/vaults/`) and port allocations. |

---

## 3. Category B: Database-Driven Services Requiring Browser UI Exploration

These services store their critical operational logic (rules, profiles, custom scoring formats, workflows, outposts, and hardware acceleration pipelines) inside relational or SQLite databases. To optimize performance, prevent media bloat, and eliminate bottlenecks, **we must inspect their web interfaces directly**.

---

### 1. Authentik (`auth.vrg.rocks` / `http://localhost:9000`)
* **Storage Engine:** PostgreSQL 16 (`data/authentik`)
* **Why Browser Inspection is Essential:**
  - **Outposts:** Inspect the embedded Caddy forward-auth proxy outpost health and token lifespans.
  - **Applications & Providers:** Verify OAuth2/OIDC configurations for Paperless, Arcane, and Coder.
  - **Flows & Stages:** Audit password policies, session durations, MFA requirements, and error handling.
  - **Blueprints:** Inspect declarative blueprint imports and tenant configurations.

---

### 2. Jellyfin (`watch.vrg.rocks` / `http://localhost:8096`)
* **Storage Engine:** SQLite (`config/jellyfin/data/data/jellyfin.db`) + XML
* **Why Browser Inspection is Essential:**
  - **Hardware Acceleration:** Verify Apple Silicon VideoToolbox decoding/encoding settings, HEVC/H.264/AV1 acceleration, tonemapping (VPP), and transcode thread allocations.
  - **Library Setup & Scrapers:** Audit metadata scrapers (TMDb, TheTVDB, OMDb), image fetchers, and chapter thumbnail generators (Trickplay).
  - **Plugins:** Inspect active plugins (Introskipper, Fanart, OpenSubtitles) and their execution schedules.
  - **User & Transcode Limits:** Verify concurrent transcode limits, remote bitrate throttling, and user playback policies.

---

### 3. Jellyseerr (`request.vrg.rocks` / `http://localhost:5055`)
* **Storage Engine:** SQLite (`config/jellyseerr/db/jellyseerr.db`) + `settings.json`
* **Why Browser Inspection is Essential:**
  - **Radarr & Sonarr Integrations:** Audit server API connections, default root folder paths (`/data/media/movies` vs `/external`), and quality profile assignments (4K vs 1080p).
  - **User Request Rules:** Verify user request quotas, auto-approval rules, and notification dispatch webhooks.
  - **TMDb Discovery & Caching:** Check sync frequency with Jellyfin libraries and indexers.

---

### 4. Radarr (`radarr.vrg.rocks` / `http://localhost:7878`)
* **Storage Engine:** SQLite (`config/radarr/radarr.db`)
* **Why Browser Inspection is Essential:**
  - **TRaSH Guides Custom Formats:** Inspect active Custom Formats (e.g. HDR10+, Dolby Vision, AV1, Remux, Unwanted/Low Quality filters) and their score weighting.
  - **Quality Profiles:** Audit upgrade thresholds, cutoff unmet rules, and allowed video resolutions.
  - **Media Management:** Verify hardlink creation toggles, file renaming tokens, unmonitor deleted items, and root folder assignments.
  - **Download Client & Indexers:** Check qBittorrent category mapping (`movies`), seed ratio limits, and Prowlarr sync status.

---

### 5. Sonarr (`sonarr.vrg.rocks` / `http://localhost:8989`)
* **Storage Engine:** SQLite (`config/sonarr/sonarr.db`)
* **Why Browser Inspection is Essential:**
  - **Quality & Release Profiles:** Audit custom scoring rules for anime, standard TV, and 4K releases.
  - **Media Management & Naming:** Verify season folder structures, multi-episode naming patterns, and atomic hardlink validation.
  - **Root Folders:** Check internal SSD paths vs external disk allocations.

---

### 6. Prowlarr (`prowlarr.vrg.rocks` / `http://localhost:9696`)
* **Storage Engine:** SQLite (`config/prowlarr/prowlarr.db`)
* **Why Browser Inspection is Essential:**
  - **Indexer Health & Priorities:** Inspect active Usenet and BitTorrent indexers, VIP status, rate limits, and failure rates.
  - **Sync Profiles:** Verify automatic schema synchronization to Radarr, Sonarr, and Lidarr.
  - **FlareSolverr Proxy Routing:** Confirm indexers with Cloudflare protection are correctly tagged to use `http://flaresolverr:8191`.

---

### 7. Bazarr (`bazarr.vrg.rocks` / `http://localhost:6767`)
* **Storage Engine:** SQLite (`config/bazarr/db/bazarr.db`) + `config.yaml`
* **Why Browser Inspection is Essential:**
  - **Subtitle Providers:** Audit provider accounts, daily API limits, and anti-captcha tokens.
  - **Language Profiles & Thresholds:** Check minimum score matching thresholds, forced subtitle rules, hearing-impaired (HI) tag removal, and audio language sync.
  - **Path Mappings:** Verify path translation between Bazarr container paths and Radarr/Sonarr internal paths.

---

### 8. Paperless-ngx (`docs.vrg.rocks` / `http://localhost:8000`)
* **Storage Engine:** PostgreSQL 17 (`data/paperless/db`) + Redis
* **Why Browser Inspection is Essential:**
  - **Workflows & Automation:** Audit automatic tagging, correspondent assignment, and document type categorization rules.
  - **Matching Algorithms:** Inspect matching criteria (Exact, Any, All, Fuzzy, Automatic ML classifier).
  - **Storage Paths:** Check physical folder organization rules for generated PDFs.
  - **Custom Fields:** Verify metadata fields (e.g. Invoice Numbers, Expiry Dates, Monetary Values).

---

### 9. Homebox (`inv.vrg.rocks` / `http://localhost:7745`)
* **Storage Engine:** SQLite (`data/homebox/data/homebox.db`)
* **Why Browser Inspection is Essential:**
  - **Location & Category Hierarchy:** Audit physical room, container, and shelf taxonomy.
  - **Custom Fields & Warranties:** Check custom asset tracking schemas.
  - **Mobile Scanner Compatibility:** Verify API interaction with the `/scan` PWA frontend.

---

### 10. Arcane (`arcane.vrg.rocks` / `http://localhost:3552`)
* **Storage Engine:** SQLite (`data/arcane/data/arcane.db`)
* **Why Browser Inspection is Essential:**
  - **Stack Templates:** Inspect stored Docker Compose templates and container deployment hooks.
  - **OIDC Authentication:** Verify user role mapping from Authentik.

---

## 4. Structured Phased Browser Exploration Plan

To conduct an efficient and thorough review, we will explore the browser interfaces in 4 focused batches:

```
+-----------------------------------------------------------------------------------+
|                            PHASED UI EXPLORATION ROADMAP                          |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|  [ BATCH 1: INGRESS, IDENTITY & ORCHESTRATION ]                                   |
|  Targets: Authentik (auth.vrg.rocks), Glance (dash.vrg.rocks), Arcane (arcane.)   |
|  Focus: Outpost health, SSO flows, container status, and dashboard monitors.      |
|                                                                                   |
|  [ BATCH 2: MEDIA STREAMING & REQUEST PIPELINE ]                                  |
|  Targets: Jellyfin (watch.vrg.rocks), Jellyseerr (request.vrg.rocks)              |
|  Focus: Hardware acceleration, playback rules, library scrapers, request quotas.  |
|                                                                                   |
|  [ BATCH 3: THE SERVARR AUTOMATION & INDEXING ENGINE ]                            |
|  Targets: Radarr (radarr.), Sonarr (sonarr.), Prowlarr (prowlarr.), Bazarr        |
|  Focus: TRaSH profiles, custom formats, scoring, hardlink configs, indexer sync.  |
|                                                                                   |
|  [ BATCH 4: INGESTION, ARCHIVAL & LOGISTICS ]                                     |
|  Targets: qBittorrent (qb.vrg.rocks), Paperless-ngx (docs.), Homebox (inv.)       |
|  Focus: Peer ratios, tracker states, OCR classifiers, workflows, inventory schema.|
|                                                                                   |
+-----------------------------------------------------------------------------------+
```
