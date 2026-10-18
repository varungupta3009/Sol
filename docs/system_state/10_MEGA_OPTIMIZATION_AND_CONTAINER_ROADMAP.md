# 10 — Mega Optimization Audit, Live Repairs & "Lean is Sexy" Container Roadmap

**Audit Date:** October 2026
**Target Host:** Apple MacBook Pro (`M1 Pro`, 8 Cores: 6P + 2E, 16 GB Unified Memory, 512 GB Internal NVMe + 2 TB ExFAT `PANOPTICON`)
**Container Runtime:** OrbStack (`7.817 GiB` VM ceiling, VirtioFS shared mounts, `*.vrg.rocks`)
**Active Fleet:** 27 running containers (`~2.98 GiB` total RSS), 25 standby profile containers, 1 native service (`jellyfin-metal`)

---

## 1. Live Server Audit & Immediate Repairs Executed on Sol

During the live SSH audit of `/Users/vrg/Documents/Sol`, all 27 active containers, 38 SQLite databases, Docker storage volumes, and service logs were inspected and repaired:

| # | Subsystem | Issue Found on Live Server | Root Cause | Fix Executed |
| :--- | :--- | :--- | :--- | :--- |
| **1** | **QUI (`qui.vrg.rocks`)** | Requested immediate deployment of `qui`; initial login password had literal quotes | `CORE_PASSWORD` in `.env` was wrapped in double quotes (`"..."`), so `qui create-user` included quotes in the password | Deployed `ghcr.io/autobrr/qui:latest` (`v1.32.0`, `23.6 MiB` RAM) on port `7476` in `compose/download.yml`, `Caddyfile`, `ports.json`, and `config/glance/config/glance.yml`. Reset `VRG` password to clean unquoted `CORE_PASSWORD` via `qui change-password` (`POST /api/auth/login` = `200 OK`) and connected `Sol (qBittorrent)` with `hasLocalFilesystemAccess: true`. |
| **2** | **Backrest + Restic (`backrest.vrg.rocks`)** | `rclone sync` to OneDrive failed with Graph API `drive id appears to be malformed` and lacked chunk deduplication | Naive full-file cloud sync without pre-staged symlink/volume manifests or chunk deduplication | Deployed `ghcr.io/garethgeorge/backrest:latest` (`~25 MiB` RAM) on port `9898` (`backrest.vrg.rocks`) and overhauled `scripts/stage_db_backups.sh`, `scripts/backup.sh`, and `scripts/restore.sh` to create encrypted, deduplicated Restic snapshots (with Postgres dumps, WAL-complete SQLite snapshots, `symlinks_manifest.tsv`, and `coder_home.tar.gz`) to `/Volumes/PANOPTICON/backups/sol-restic` and `rclone:OneDrive:Sol-Restic`. |
| **3** | **SQLite WAL Integrity (`arcane`, `cross-seed`, `prowlarr`)** | `arcane` crash-looping (`disk I/O error`), `cross-seed` failing (`malformed`), `prowlarr` failing `CheckHealth` (`Tree 16 page 5865 malformed`) | Opening guest Linux WAL-mode SQLite DBs in read-write mode from macOS host `sqlite3` over VirtioFS desynchronizes `-shm` mmap pages | Recovered `arcane.francis.db`, `cross-seed.db`, and `prowlarr.db` offline (`PRAGMA integrity_check = ok`). Hardened `scripts/stage_db_backups.sh` to copy `${db_file}` and `${db_file}-wal` (without `-shm`) to a local temp directory before running `sqlite3 .backup`. |
| **4** | **Sonarr & Radarr Health + Option A Import** | Sonarr logged `401:Unauthorized` against `qbittorrent:8080` and then populated Activity queue; Radarr warned on 8 missing Movie Collection root folders | Sonarr had placeholder password `00000000` and still had `enableCompletedDownloadHandling: true` in `sonarr.db` | Updated Sonarr's qBittorrent password, disabled `enableCompletedDownloadHandling` in Sonarr (`false`, matching Radarr and `torrent_finished.py` Option A), verified `0` physical duplicate TV files exist on `/Volumes/PANOPTICON/media/tv`, and updated all 8 Radarr Collections to `/external/media/movies`. |
| **5** | **Prowlarr & Servarr `AllowedHostsCheck`** | Prowlarr showed 4 health alerts (`TheRARBG`, `Readarr`, `AllowedHostsCheck`, `1337x`). Radarr and Sonarr warned on `AllowedHostsCheck` | Upstream Cardigann removed `TheRARBG` (`ID 5`), `Readarr` (`ID 4`) is retired, and 2026 Servarr builds require `<AllowedHosts>` | Deleted stale `TheRARBG` (`ID 5`) and `Readarr` (`ID 4`) via Prowlarr API, and added `RADARR__`, `SONARR__`, `LIDARR__`, and `PROWLARR__SERVER__ALLOWEDHOSTS` in `compose/media.yml`. |
| **6** | **Cross-Seed v6 & `/downloads` Retirement** | Cross-Seed warned `maxDataDepth of 3` needed for `seasonFromEpisodes: 1` and warned on `/external` `linkDirs` | TV episodes sit at depth 3 (`tv/Series/Season/Ep.mkv`), and Cross-Seed probes `fs.linkSync` even in `symlink` mode (which fails on ExFAT) | Set `maxDataDepth: 3` and `linkDirs: ["/data/torrents/cross-seed-links"]` in `config/cross-seed/config.js`. Verified `0` of `289` `.fastresume` files use `/downloads` and removed `/downloads` from `compose/download.yml`. |
| **7** | **Jellyfin `/tmp` RAM Scratch, Keyframe Trickplay & `Home Videos`** | Jellyfin decoded every P/B frame of 4K HDR movies on CPU during library scans, and Seerr logged `Unable to find TMDb ID` every 5m for `VRG's 1st Birthday` | `/tmp/jellyfin` was not on `tmpfs`, `<EnableKeyFrameOnlyExtraction>` was `false`, `<ExtractTrickplayImagesDuringLibraryScan>` was `true`, and home videos sat in `Movies` | Added `tmpfs: - /tmp/jellyfin:size=512m` in `compose/media.yml`, enabled `<EnableKeyFrameOnlyExtraction>true</EnableKeyFrameOnlyExtraction>`, disabled Trickplay during library scans, updated Jellyfin library paths to `/media/external/media/movies` and `/media/external/media/tv`, and moved `VRG's 1st Birthday` to `data/media/home-videos/` (`Home Videos` library). |
| **8** | **Docker Disk Hygiene & Log Rotation (`12.46 GB` Reclaimed)** | `docker system df` reported `12.88 GB` of unused images, 17 unattached volumes, and unbounded JSON logs | Old container layers, 3 legacy pre-refactor volumes (`860 MB`), and retired `config/readarr` / `config/authelia*` | Pruned unused images (`11.6 GB`), removed 13 empty `0 B` volumes + 3 legacy pre-refactor volumes (`sol_coder_home`, `sol_coder_data`, `sol_database`) + retired `config/readarr` / `config/authelia*` while preserving `config/plex`, `config/overseerr`, `~/Movies/overseerr`, and the active `4.775 GB` Coder workspace volume. Added `x-logging` (`10m` x `3`) across all 8 `compose/*.yml` files. |

---

## 2. Live Resource Profile & High-Impact Server Optimizations

### 2.1 Measured Live Memory Footprint (`~2.95 GiB` Across All 26 Active Containers)

| Tier | Services & Measured RSS | Total Tier RAM |
| :--- | :--- | :--- |
| **Top Memory Consumers (8 services)** | `jellyfin` (`653 MiB` during Trickplay), `authentik-worker` (`257 MiB`), `authentik-server` (`245 MiB`), `paperless-webserver` (`311 MiB`), `sonarr` (`184 MiB`), `radarr` (`171 MiB`), `prowlarr` (`165 MiB`), `lidarr` (`128 MiB`), `authentik-postgresql` (`127 MiB`) | `~2.24 GiB` |
| **Middleware (3 services)** | `bazarr` (`139 MiB`), `seerr` (`133 MiB`), `byparr` (`56 MiB`) | `~328 MiB` |
| **"Lean is Sexy" Fleet (16 services)** | `arcane` (`75 MiB`), `coder` (`66 MiB`), `qbittorrent` (`46 MiB`), `cross-seed` (`31 MiB`), `backrest` (`25 MiB`), `qui` (`24 MiB`), `paperless-db` (`23 MiB`), `caddy` (`23 MiB`), `ntfy` (`22 MiB`), `ignis` (`21 MiB`), `homebox` (`18 MiB`), `copyparty` (`13 MiB`), `code-server` (`13 MiB`), `glance` (`7.5 MiB`), `paperless-broker` (`4.4 MiB`) | `~412 MiB` |

### 2.2 Completed Host Hygiene & Media Library Actions

1. **Silenced `seerr` 5-Minute `Unable to find TMDb ID` Error Loop (`VRG's 1st Birthday`) — COMPLETED:**
   - Moved `VRG's 1st Birthday` (`.mkv` and `.mpeg`) into `/Users/vrg/Documents/Sol/data/media/home-videos/` and created a separate Jellyfin `Home Videos` library (`collectionType=homevideos`) unchecked in Seerr.
2. **Purged Approved Retired Config Directories (`config/readarr`, `config/authelia*`, `_backup_pre_refactor`) & Legacy Pre-Refactor Volumes (`860 MB`) — COMPLETED:**
   - Preserved `config/plex` (`292 MB`), `config/overseerr` (`576 KB`), `config/jellyseerr*`, and `/Users/vrg/Movies/overseerr` per user instruction, and created `scripts/merge_overseerr_history.py` (`--dry-run` verified) to merge all 10 historical May/June 2025 Overseerr requests into `config/seerr/db/db.sqlite3`.
   - Removed legacy pre-refactor volumes (`sol_coder_home`, `sol_database`, `sol_coder_data`) while protecting the `4.775 GB` active Coder workspace volume (`coder-8378beda-cda2-40ff-a1ad-bc2613acad62-home`).

---

## 3. "Lean is Sexy": 2026 Container Replacement & Upgrade Matrix

| Domain | Current / Planned Stack | Measured / Typical RAM | "Lean is Sexy" 2026 Replacement | Stack & RAM | Why It Wins for Sol |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1. Identity & SSO** | `authentik-server` + `authentik-worker` + `authentik-postgresql` | **`502 MiB` RAM** + `10%` idle CPU | **[Tinyauth v5 Standalone](https://github.com/steveiliop56/tinyauth)** (`ghcr.io/tinyauthapp/tinyauth:v5`) *(Kept Authentik active in prod)* | **Go** (`~15 MiB` total, `0%` idle CPU) | Pocket ID v2 is strictly passkey-only and lacks upstream Google OAuth (GitHub #1712). However, **Tinyauth v5 alone** supports upstream Google OAuth with `TINYAUTH_OAUTH_AUTOREDIRECT=google` (silent redirect to `accounts.google.com`), Caddy forward-auth, and a built-in OIDC provider (v5.1.0+). Authentik remains untouched until Tinyauth v5 OIDC `sub` migration is tested. |
| **2. Torrent WebUI & Automation** | Standby `flood` (Node) + `qbit_manage` (Python) | `~180 MiB` combined | **[QUI](https://github.com/autobrr/qui)** (`ghcr.io/autobrr/qui:latest`) — **DEPLOYED LIVE!** | **Go + React** (`23.6 MiB` measured on Sol!) | Single Go binary with 10k+ torrent support, built-in tracker tagging/share rules, orphan file scanning, and hardlink/reflink inspection. Allows deleting `flood` and `qbit_manage` from standby. |
| **3. Cloud Backups** | Raw `rclone sync` in `scripts/backup.sh` + standby `rclone-gui` | Full-file re-uploads, OneDrive API errors | **[Backrest](https://github.com/garethgeorge/backrest)** (`ghcr.io/garethgeorge/backrest:latest`) + **Restic** — **DEPLOYED LIVE!** | **Go** (`~25 MiB` RAM on `backrest.vrg.rocks`) | Chunk-level Rabin deduplication + `zstd` compression + AES-256-GCM encryption to `/Volumes/PANOPTICON/backups/sol-restic` and `rclone:OneDrive:Sol-Restic`, paired with `scripts/stage_db_backups.sh` and `scripts/restore.sh`. |
| **4. Monitoring & Logs** | Standby `uptime-kuma` (Node) + `homarr` (Next.js) + `dockge` (Node) | `~450 MiB` combined | **[Beszel](https://github.com/henrygd/beszel)** + **[Dozzle](https://github.com/amir20/dozzle)** + **[Gatus](https://github.com/TwiN/gatus)** behind **[wollomatic/socket-proxy](https://github.com/wollomatic/socket-proxy)** *(Standby / TODO)* | **4x Go binaries** (`~65 MiB` combined) | Kept in `standby` profile and documented in `TODO.md` per user preference. |
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
