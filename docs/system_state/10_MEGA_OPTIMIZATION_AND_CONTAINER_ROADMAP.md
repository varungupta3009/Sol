# 10 — Mega Optimization Audit, Live Repairs & "Lean is Sexy" Container Roadmap

**Audit Date:** October 2026
**Target Host:** Apple MacBook Pro (`M1 Pro`, 8 Cores: 6P + 2E, 16 GB Unified Memory, 512 GB Internal NVMe + 2 TB ExFAT `PANOPTICON`)
**Container Runtime:** OrbStack (`7.817 GiB` VM ceiling, VirtioFS shared mounts, `*.vrg.rocks`)
**Active Fleet:** 26 running containers (`~2.95 GiB` total RSS), 25 standby profile containers, 1 native service (`jellyfin-metal`)

---

## 1. Live Server Audit & Immediate Repairs Executed on Sol

During the live SSH audit of `/Users/vrg/Documents/Sol`, all 26 active containers, 38 SQLite databases, Docker storage volumes, and service logs were inspected and repaired:

| # | Subsystem | Issue Found on Live Server | Root Cause | Fix Executed |
| :--- | :--- | :--- | :--- | :--- |
| **1** | **QUI (`qui.vrg.rocks`)** | Requested immediate deployment of `qui` | Not yet wired in `compose/download.yml` or `Caddyfile` | Deployed `ghcr.io/autobrr/qui:latest` (`v1.32.0`, `23.6 MiB` RAM) on port `7476` in `compose/download.yml`, `Caddyfile`, `ports.json`, and `config/glance/config/glance.yml`. Initialized user `VRG` and connected `Sol (qBittorrent)` (`http://qbittorrent:8080`) with `hasLocalFilesystemAccess: true`. |
| **2** | **SQLite WAL Integrity (`arcane`, `cross-seed`, `prowlarr`)** | `arcane` crash-looping (`disk I/O error`), `cross-seed` failing (`malformed`), `prowlarr` failing `CheckHealth` (`Tree 16 page 5865 malformed`) | Opening guest Linux WAL-mode SQLite DBs in read-write mode from macOS host `sqlite3` over VirtioFS desynchronizes `-shm` mmap pages | Recovered `arcane.francis.db`, `cross-seed.db`, and `prowlarr.db` offline (`PRAGMA integrity_check = ok`). Hardened `scripts/backup.sh` to use `file:${db_file}?immutable=1` and check the `SQLite format 3` magic header. |
| **3** | **Sonarr & Radarr Health** | Sonarr logged `401:Unauthorized` against `qbittorrent:8080`. Radarr warned on 8 missing Movie Collection root folders | Sonarr had placeholder password `00000000`. Radarr Collections still pointed to pre-migration `/external/Movies` | Updated Sonarr's qBittorrent password from `radarr.db` (`testall` = `isValid: true`) and updated all 8 Radarr Collections to `/external/media/movies`. |
| **4** | **Prowlarr & Servarr `AllowedHostsCheck`** | Prowlarr showed 4 health alerts (`TheRARBG`, `Readarr`, `AllowedHostsCheck`, `1337x`). Radarr and Sonarr warned on `AllowedHostsCheck` | Upstream Cardigann removed `TheRARBG` (`ID 5`), `Readarr` (`ID 4`) is retired, and 2026 Servarr builds require `<AllowedHosts>` | Deleted stale `TheRARBG` (`ID 5`) and `Readarr` (`ID 4`) via Prowlarr API, and added `RADARR__`, `SONARR__`, `LIDARR__`, and `PROWLARR__SERVER__ALLOWEDHOSTS` in `compose/media.yml`. |
| **5** | **Cross-Seed v6 & `/downloads` Retirement** | Cross-Seed warned `maxDataDepth of 3` needed for `seasonFromEpisodes: 1` and warned on `/external` `linkDirs` | TV episodes sit at depth 3 (`tv/Series/Season/Ep.mkv`), and Cross-Seed probes `fs.linkSync` even in `symlink` mode (which fails on ExFAT) | Set `maxDataDepth: 3` and `linkDirs: ["/data/torrents/cross-seed-links"]` in `config/cross-seed/config.js`. Verified `0` of `289` `.fastresume` files use `/downloads` and removed `/downloads` from `compose/download.yml`. |
| **6** | **Jellyfin `/tmp` RAM Scratch & Keyframe Trickplay** | Jellyfin writes thousands of temporary `%08d.jpg` Trickplay frames to disk and decodes every P/B frame of 4K HDR movies on CPU | `/tmp/jellyfin` was not mounted on `tmpfs`, `<EnableKeyFrameOnlyExtraction>` was `false`, and `scripts/setup_jellyfin_metal.py` still referenced `/Volumes/PANOPTICON/Movies` | Added `tmpfs: - /tmp/jellyfin:size=512m` in `compose/media.yml`, enabled `<EnableKeyFrameOnlyExtraction>true</EnableKeyFrameOnlyExtraction>` and `<ScanBehavior>NonBlocking</ScanBehavior>` in `config/jellyfin/data/config/system.xml`, and updated `setup_jellyfin_metal.py` paths. |
| **7** | **Docker Disk Hygiene (`11.6 GB` Reclaimed)** | `docker system df` reported `12.88 GB` of unused images and 17 unattached volumes | Old container layers and 13 empty anonymous volumes accumulated over prior upgrades | Pruned unused images (`0 B` reclaimable across 25 active images) and removed 13 empty `0 B` volumes while protecting the stopped `4.775 GB` Coder workspace volume (`coder-8378beda-cda2-40ff-a1ad-bc2613acad62-home`). |

---

## 2. Live Resource Profile & High-Impact Server Optimizations

### 2.1 Measured Live Memory Footprint (`~2.95 GiB` Across All 26 Active Containers)

| Tier | Services & Measured RSS | Total Tier RAM |
| :--- | :--- | :--- |
| **Top Memory Consumers (8 services)** | `jellyfin` (`653 MiB` during Trickplay), `authentik-worker` (`257 MiB`), `authentik-server` (`245 MiB`), `paperless-webserver` (`311 MiB`), `sonarr` (`184 MiB`), `radarr` (`171 MiB`), `prowlarr` (`165 MiB`), `lidarr` (`128 MiB`), `authentik-postgresql` (`127 MiB`) | `~2.24 GiB` |
| **Middleware (3 services)** | `bazarr` (`139 MiB`), `seerr` (`133 MiB`), `byparr` (`56 MiB`) | `~328 MiB` |
| **"Lean is Sexy" Fleet (15 services)** | `arcane` (`75 MiB`), `coder` (`66 MiB`), `qbittorrent` (`46 MiB`), `cross-seed` (`31 MiB`), `qui` (`24 MiB`), `paperless-db` (`23 MiB`), `caddy` (`23 MiB`), `ntfy` (`22 MiB`), `ignis` (`21 MiB`), `homebox` (`18 MiB`), `copyparty` (`13 MiB`), `code-server` (`13 MiB`), `glance` (`7.5 MiB`), `paperless-broker` (`4.4 MiB`) | `~387 MiB` |

### 2.2 Remaining Host Hygiene & Media Library Actions

1. **Silence `seerr` 5-Minute `Unable to find TMDb ID` Error Loop (`VRG's 1st Birthday`):**
   - **Root Cause:** Two personal home videos (`VRG's 1st Birthday ` `.mkv` and `VRG's 1st Birthday (MPEG-2)`) sit inside Jellyfin's `Movies` library (`Type: Movie`). Every 5 minutes, Seerr scans the `Movies` library and logs an error because those two items have no TMDb ID.
   - **Fix:** Move both files into `/Users/vrg/Documents/Sol/data/media/home-videos/`, add a separate Jellyfin library with `Content type: Home videos and photos` (`collectionType=homevideos`), and leave that library unchecked in Seerr's Jellyfin settings.
2. **Purge Stale Retired Config Directories (`420.6 MB`) & Legacy Pre-Refactor Volumes (`860 MB`):**
   - **Stale `config/` directories from retired services:** `config/plex` (`292 MB`), `config/readarr` (`121 MB`), `config/jellyseerr` (`3.2 MB`), `config/jellyseerr_backup_pre_seerr_migration` (`3.2 MB`), `config/overseerr` (`576 KB`), `config/authelia` (`336 KB`), `config/authelia_auto` (`72 KB`), `data/authelia` (`4 KB`), and `_backup_pre_refactor` (`104 KB`).
   - **Legacy named Docker volumes:** `sol_coder_home` (`699.4 MB`), `sol_database` (`85.84 MB`), and `sol_coder_data` (`74.78 MB`).
   - **Critical Safety Rule:** Never run bare `docker volume prune` on Sol! The `4.775 GB` volume `coder-8378beda-cda2-40ff-a1ad-bc2613acad62-home` is the active `/home/coder` disk for the Coder workspace (`coder/main.tf` line 153), which shows `0` container links whenever the workspace container is stopped.

---

## 3. "Lean is Sexy": 2026 Container Replacement & Upgrade Matrix

| Domain | Current / Planned Stack | Measured / Typical RAM | "Lean is Sexy" 2026 Replacement | Stack & RAM | Why It Wins for Sol |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1. Identity & SSO** | `authentik-server` + `authentik-worker` + `authentik-postgresql` | **`502 MiB` RAM** + `10%` idle CPU | **[Pocket ID v2](https://github.com/pocket-id/pocket-id)** (`ghcr.io/pocket-id/pocket-id:v2`) + **[Tinyauth v5](https://github.com/steveiliop56/tinyauth)** (`ghcr.io/steveiliop56/tinyauth:v5`) | **Go + SQLite** (`~30-45 MiB` total, `0%` idle CPU) | Saves **`~460 MiB` RAM** and eliminates an entire PostgreSQL cluster. Passkey-first WebAuthn/OIDC provider (`id.vrg.rocks`) paired with Tinyauth forward-auth for Caddy. |
| **2. Torrent WebUI & Automation** | Standby `flood` (Node) + `qbit_manage` (Python) | `~180 MiB` combined | **[QUI](https://github.com/autobrr/qui)** (`ghcr.io/autobrr/qui:latest`) — **DEPLOYED LIVE!** | **Go + React** (`23.6 MiB` measured on Sol!) | Single Go binary with 10k+ torrent support, built-in tracker tagging/share rules, orphan file scanning, and hardlink/reflink inspection. Allows deleting `flood` and `qbit_manage` from standby. |
| **3. Cloud Backups** | Raw `rclone sync` in `scripts/backup.sh` + standby `rclone-gui` | Full-file re-uploads, OneDrive API errors | **[Backrest](https://github.com/garethgeorge/backrest)** (`ghcr.io/garethgeorge/backrest:latest` or native macOS) + **Restic** | **Go** (`~25 MiB` RAM) | Chunk-level Rabin deduplication + `zstd` compression + AES-256-GCM encryption. When `radarr.db` (`260 MB`) changes, uploads only `1-2 MB` of diff chunks instead of `260 MB`. |
| **4. Monitoring & Logs** | Standby `uptime-kuma` (Node) + `homarr` (Next.js) + `dockge` (Node) | `~450 MiB` combined | **[Beszel](https://github.com/henrygd/beszel)** + **[Dozzle](https://github.com/amir20/dozzle)** + **[Gatus](https://github.com/TwiN/gatus)** behind **[wollomatic/socket-proxy](https://github.com/wollomatic/socket-proxy)** | **4x Go binaries** (`~65 MiB` combined) | Delete `uptime-kuma`, `homarr`, and `dockge` (Arcane already replaces Dockge). Run `beszel-agent` natively on macOS so it reports real Apple Silicon metrics rather than the OrbStack VM. |
| **5. PDF Manipulation** | Planned `Stirling-PDF` (`stirlingtools/stirling-pdf`) | `300-600 MiB` (Java/Spring JVM) | **[BentoPDF](https://github.com/alam00000/bentopdf)** (Client-side WebAssembly) | **Static WASM** (`0 MiB` RAM via Caddy) | 50+ PDF tools (merge, split, sign, redact, compress) running 100% client-side in WebAssembly. Served directly from Caddy `web/bentopdf` with zero container overhead. |
| **6. Bookmarks & Read-Later** | Planned `Karakeep` (Hoarder) or `Linkwarden` | `350-500+ MiB` (Node + Chromium + Meilisearch) | **[Readeck](https://codeberg.org/readeck/readeck)** (`codeberg.org/readeck/readeck:latest`) | **Go + SQLite** (`~25 MiB` RAM) | Single Go binary with full-text reader mode, article archiving, highlights, labels, OPDS, and EPUB export (`links.vrg.rocks`). |
| **7. RSS Reader** | Planned `FreshRSS` (PHP) | `80-150 MiB` | **[Fusion](https://github.com/0x2E/fusion)** (`ghcr.io/0x2e/fusion:latest`) or **[Miniflux](https://miniflux.app/)** | **Go + SQLite** (`~25-50 MiB` RAM) | Ultra-clean Go + SQLite RSS aggregator with Fever/Google Reader API support for mobile clients (`rss.vrg.rocks`). |
| **8. E-Books & Comics** | Standby `calibre` (KasmVNC desktop) + `calibre-web` | `400+ MiB` (GUI desktop in browser) | **[Kavita](https://www.kavitareader.com/)** (already in standby) or **[Calibre-Web-Automated](https://github.com/crocodilestick/Calibre-Web-Automated)** | **.NET / Python** (`~120 MiB` for Kavita) | Delete desktop `calibre` and legacy `calibre-web` from standby. Keep `kavita` for EPUB/PDF/Manga/Comics (or CWA if Kobo/Kindle wireless sync is needed). |
| **9. Dev & Network Micro-Tools** | Planned `it-tools`, `cyberchef`, `excalidraw`, `openspeedtest` containers | `4x nginx/Node` containers (`~120 MiB`) | **Zero-Container Static Hosting via Caddy (`web/<tool>`)** | **Static Assets** (`0 MiB` extra RAM!) | Caddy already serves static sites (`/mind`, `/fam`, `/scan`, `/aysynbm`). Hosting static builds of `IT-Tools`, `CyberChef`, `BentoPDF`, `OpenSpeedTest`, and `Excalidraw` under `web/` costs **0 MB RAM** and **0 containers**. |

### Security Advisory — Two Containers to Strictly Avoid in 2026
- **Never deploy `Huntarr`:** In February 2026, `Huntarr` v9.4.2 exposed an unauthenticated `POST /api/settings/general` endpoint that leaked all connected Radarr/Sonarr/Prowlarr API keys and passwords in cleartext, after which the author deleted the repository.
- **Never deploy `Booklore`:** The upstream author pulled the repository, website, and Discord in March 2026.

---

## 4. Dossier-Aligned Passion-Project Expansions for Sol

### 4.1 Cinema, IMAX, 4K Remuxes & Theatre Automation
- **[ErsatzTV](https://ersatztv.org/) (Custom IMAX & Criterion Live Channels, `tv.vrg.rocks`):** Run natively on macOS (for Apple VideoToolbox hardware transcoding) to turn local libraries and `data/media/preshows` (Dolby Atmos, IMAX countdowns, DTS bumpers) into scheduled 24/7 rolling channels (*"IMAX 70mm Showcase"*, *"Criterion Restorations"*, *"Nolan Archive"*) inside Jellyfin Live TV (M3U / XMLTV).
- **[MediaInfo Web (`mediainfo.js`)](https://mediaarea.net/MediaInfoOnline) (`mi.vrg.rocks`):** Zero-container client-side WebAssembly bitstream inspector served by Caddy (`web/mediainfo`) for verifying Dolby Vision Profile 7 FEL vs Profile 8.1, HDR10 MaxCLL/MaxFALL metadata, TrueHD Atmos object tracks, and remux bitrates.
- **[Recyclarr](https://recyclarr.dev/) (`compose/media.yml`):** Daily sync of TRaSH Guides custom formats into Radarr and Sonarr (scoring 4K Remux, Dolby Vision + HDR10 fallback, IMAX Enhanced, and TrueHD Atmos).
- **Jellyfin [Intro Skipper](https://github.com/intro-skipper/intro-skipper) & [Playback Reporting](https://github.com/jellyfin/jellyfin-plugin-playbackreporting) Plugins:** In-process Jellyfin plugins (`0 MB` extra container RAM) for automatic intro/credits skip buttons and SQLite watch history analytics.

### 4.2 Airbus Flight Deck & Aviation Telemetry
- **[AirTrail](https://github.com/johanohly/AirTrail) (`fly.vrg.rocks`):** Modern self-hosted personal flight log and passport map built with **SvelteKit** (`ghcr.io/johanohly/airtrail:latest`, sharing `paperless-db` PostgreSQL 17). Tracks commercial flights, Airbus A320neo/A350 airframe tail numbers, seat classes, and airports, with Flightradar24/Flighty import and a REST API that feeds Glance `/radar`.
- **[adsb-ultrafeeder (`tar1090` + `readsb`)](https://github.com/sdr-enthusiasts/docker-adsb-ultrafeeder) (`adsb.vrg.rocks`):** Runs on the Raspberry Pi 3B that owns the USB RTL-SDR dongle (since macOS OrbStack cannot pass USB SDRs into Linux containers) and is reverse-proxied by Sol's Caddy with live aircraft metrics surfaced in Glance.

### 4.3 Compiler-First Web Stack, Zero-Container Tools & Micro-Sandboxes
- **Zero-Container Static Developer Suite (`tools.`, `chef.`, `pdf.`, `speed.`, `draw.vrg.rocks`):** Served directly from `web/` by Caddy (`IT-Tools`, `CyberChef`, `BentoPDF`, `OpenSpeedTest`, `Excalidraw`) with `0` extra containers and `0 MiB` RAM.
- **[Enclosed](https://github.com/CorentinTh/enclosed) (`send.vrg.rocks`):** Zero-knowledge client-side encrypted notes and file drops built on **Hono + TypeScript** (`corentinth/enclosed:latest`, `~30 MiB` RAM).
- **[PocketBase](https://pocketbase.io/) Sandbox (`pb.vrg.rocks`):** Single-binary Go + SQLite backend (`~15 MiB` RAM) ready for Svelte 5 / Datastar / HTMX personal projects (*The Hub*, *StockPile*, *gon*).
