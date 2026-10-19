# Sol Server Roadmap and Next Steps

> **Project:** Sol Home Server (`*.vrg.rocks`)
> **Host:** Apple Silicon M1 Pro macOS (OrbStack Docker engine)
> **Status:** October 2026 architectural hardening merged in the repository. Live host verification pending (see [FLASH_LOCAL_VERIFICATION_RUNBOOK.md](docs/FLASH_LOCAL_VERIFICATION_RUNBOOK.md)).

---

## 🖥️ Open: Local Server Tasks (Gemini 3.8 Flash on the Live Host)

Run these on `/Users/vrg/Documents/Sol` in the runbook order. Each item links to its runbook task.

### A. Pre-Flight and `.env` Reconciliation ([Task 1](docs/FLASH_LOCAL_VERIFICATION_RUNBOOK.md#task-1-pre-flight-and-env-reconciliation))
- [x] Quote `PAPERLESS_OCR_LANGUAGES="hin kan pan"` and single-quote `PAPERLESS_SOCIALACCOUNT_PROVIDERS='...'` in the live `.env` (matches `.env.example`).
- [x] Add missing tag pins: `CADDY_TAG=2`, `PAPERLESS_TAG=3.3` (verified live running is Paperless 3.3.1, pinned 3.3 to avoid downgrade), `ARCANE_TAG=latest`, `CODER_TAG=latest`.
- [x] Confirm that the live Postgres role password in `data/paperless/db` matches `PAPERLESS_DB_PASS` over a network connection (the local socket uses trust auth and proves nothing). Verified direct network connection succeeds.
- [x] Confirm the bash 3.2 guards in `scripts/restore.sh` with `/bin/bash -c 'set -u; a=(); echo ${a[@]+"${a[@]}"}'`.

### B. Rclone Filter and Backup Pipeline ([Task 2](docs/FLASH_LOCAL_VERIFICATION_RUNBOOK.md#task-2-rclone-filter-and-backup-pipeline-verification))
- [x] Merge the live `config/rclone/filter.txt` with `filter.txt.example`. Make sure `- data/authentik/**`, `- data/paperless/db/**`, `- data/paperless/redis/**`, `- **/*-wal`, and `- **/*-shm` sit above every broader include.
- [x] Run `./scripts/backup.sh` and verify `data/backups/authentik_db.sql.gz`, `data/backups/paperless_db.sql.gz`, `data/backups/sqlite/*` (`PRAGMA integrity_check` = `ok`), and `BACKUP_EXIT=0`.
- [x] List SQLite files under `data/` outside the snapshot scope (`./config`, `./data/arcane`, `./data/ignis`) that belong to running services (for example `copyparty` `.hist`).
- [ ] Decide whether to `rclone purge` the stale raw cluster copies under `OneDrive:Sol/data/authentik/` and `OneDrive:Sol/data/paperless/db/` (sync never deletes excluded paths).
- [x] **OVERHAULED: Replaced Naive Rclone Sync with Restic + Backrest (`scripts/backup.sh`, `scripts/stage_db_backups.sh`, `scripts/restore.sh`):**
  - **Safe Pre-Backup Staging (`scripts/stage_db_backups.sh`):** Dumps `authentik-postgresql` and `paperless-db` via `pg_dump`, takes WAL-complete SQLite snapshots via temp-copy `.backup` (`data/backups/sqlite/`), exports all library symlinks (`data/media` and `/Volumes/PANOPTICON/media`) to `data/backups/symlinks_manifest.tsv`, and archives the persistent Coder workspace volume to `data/backups/coder_home.tar.gz`.
  - **Chunk-Based Deduplication & Encryption (`Backrest` + `Restic`):** Deployed `backrest` (`ghcr.io/garethgeorge/backrest:latest` on `backrest.vrg.rocks`, port `9898`) and replaced `rclone sync` in `scripts/backup.sh` and `scripts/restore.sh` with encrypted, content-addressed `restic` snapshots to `/Volumes/PANOPTICON/backups/sol-restic` (`/repos/local-panopticon`) and `rclone:OneDrive:Sol-Restic`, governed by `config/backrest/excludes.txt.example`.
  - **Full Mac Reset Recovery (`scripts/restore.sh`):** Restores all configs, databases, `.torrent`/`.fastresume` state, recreates all media symlinks from `symlinks_manifest.tsv`, and restores the Coder home volume in one command.

### C. Authentik Worker and Loopback Ports ([Task 3](docs/FLASH_LOCAL_VERIFICATION_RUNBOOK.md#task-3-authentik-worker-and-loopback-port-verification))
- [x] Confirm that no outpost uses a Docker service connection (only the embedded outpost is in use).
- [x] Recreate `authentik-server` and `authentik-worker`. Verify `docker port authentik-server` shows only `127.0.0.1:9000` and `127.0.0.1:9443`, and verify that the worker runs non-root with clean logs.
- [x] Confirm that `dash.vrg.rocks` and `code.vrg.rocks` redirect to Authentik and that `qb.vrg.rocks` still serves the qBittorrent login page. Recreated `caddy` to bind new `Caddyfile` inode.

### D. Byparr Cutover and Glance Command Center ([Task 4](docs/FLASH_LOCAL_VERIFICATION_RUNBOOK.md#task-4-byparr-cutover-verification) & [Task 4B](docs/FLASH_LOCAL_VERIFICATION_RUNBOOK.md#task-4b-glance-command-center-revamp-and-automatic-api-key-extraction))
- [x] `docker stop flaresolverr && docker rm flaresolverr`, then `docker compose up -d byparr`.
- [x] From `prowlarr`, confirm that `flaresolverr` resolves to the Byparr IP only and that `POST http://flaresolverr:8191/v1` returns `"status":"ok"`.
- [x] Run Prowlarr `indexer/testall` and test Cloudflare-protected indexers in the UI (7 of 9 passed; RuTracker auth & 1337x blocked upstream).
- [x] Run the Task 4B automatic API-key extractor to populate `RADARR_API_KEY`, `SONARR_API_KEY`, `PROWLARR_API_KEY`, `SEERR_API_KEY`, and `PAPERLESS_API_KEY` in `.env` from local `config/` files.
- [x] Run `docker container prune -f` and `docker compose up -d glance` (fixed widget type `lobste-rs` -> `lobsters`) so Glance loads cleanly on HTTP 200.

### E. `/downloads` to `/data/torrents` Live Cutover ([Task 5](docs/FLASH_LOCAL_VERIFICATION_RUNBOOK.md#task-5-unifying-downloads-and-data-qbittorrent-cross-seed-arr))
- [x] Run `./scripts/test_cross_seed.sh` and record the `/external`, `/downloads`, and `/data` hardlink results.
- [x] Inspect `qBittorrent.conf` (`SavePath`, `TempPath`), `categories.json`, `BT_backup` path counts, Cross-Seed `config.js` (`linkDirs`, `dataDirs`, `torrentDir`), and the Radarr, Sonarr, and Lidarr `RemotePathMappings`.
- [x] Migrated all 289 `.fastresume` path entries to `/data/torrents` (`212`) and `/external/torrents` (`77`) with `0` remaining on `/downloads`.
- [x] Removed legacy `- ${DOCKER_DATA_DIR}/torrents:/downloads` bind mount from `qbittorrent`, `cross-seed`, and `qbit_manage` in `compose/download.yml`.
- [x] Updated `config/cross-seed/config.js` (`maxDataDepth: 3` and `linkDirs: ["/data/torrents/cross-seed-links"]`).

### F. `paperless-db` `postgres:17` to `postgres:17-alpine` ([Task 6](docs/FLASH_LOCAL_VERIFICATION_RUNBOOK.md#task-6-optional-migrate-paperless-db-from-postgres17-glibc-to-postgres17-alpine-musl))
- [x] Dumped `paperless` database with `pg_dump`, validated dump integrity, switched image tag in `compose/core.yml` to `postgres:17-alpine`, initialized clean Alpine musl cluster, and restored database cleanly. Paperless healthy and indexing documents.

### G. `homebox` SQLite Recovery & Active Promotion ([Task 7](docs/FLASH_LOCAL_VERIFICATION_RUNBOOK.md#task-7-optional-diagnose-and-repair-the-homebox-database))
- [x] Repaired Homebox SQLite database, resolved encryption pepper configuration, verified asset items accessible.
- [x] Promoted `homebox` from `profiles: ["standby"]` back to active in `compose/utilities.yml`, uncommented `inv.vrg.rocks` in `Caddyfile`, updated `ports.json`, removed ad-hoc `kind_nobel` container, and started `homebox` cleanly under Docker Compose.

### H. Storage Restructuring & Zero-Copy *arr Automation (Completed October 2026)
- [x] Restructured `/Volumes/PANOPTICON` into clean `torrents/` and `media/` hierarchy aligned with TRaSH Guides.
- [x] Reclaimed 111.4 GiB on internal Mac SSD by eliminating duplicates (*The Dark Knight*, *Cloudy with a Chance of Meatballs 2*) and migrating *Star Wars Episode IV 3D* to PANOPTICON.
- [x] Migrated all 149 torrents in Docker qBittorrent and updated `.fastresume` files via offline Bencode tooling.
- [x] Implemented Option A for ExFAT zero-copy download handling: disabled built-in `Completed Download Handling` in Radarr and Sonarr, and deployed qBittorrent `AutoRun` completion hook (`config/qbittorrent/scripts/torrent_finished.py`) with relative symlinking, Radarr/Sonarr rescan, and Jellyfin library refresh.

### I. Live Container Repairs & 3-Page Glance Command Center (Completed October 2026)
- [x] **3-Page Glance Redesign (`config/glance/config/glance.yml` & `config/glance/assets/user.css`):**
  - **Page 1 (`Sol`, `/sol`):** Breathable, mobile-first unified landing page combining original `Home` and `Sol` pages with full-width `head-widgets` bang search bar, `sh:` icons, `PANOPTICON (2TB ExFAT)` host stats, and zero phantom services.
  - **Page 2 (`Stats & Ops`, `/stats`):** Geeky telemetry deck with 6 live `custom-api` cards (`Jellyfin` with fixed `#(NowPlayingItem.Name!=)#` GJSON filter, `Seerr`, `Prowlarr`, `Paperless-ngx`, and split-column `Radarr` + `Sonarr`), 20-container internal health mesh, live Docker socket fleet, and ops scratchpad.
  - **Page 3 (`Radar`, `/radar`):** Curated feeds for Cinema/IMAX, Pantheon of Interactive Explainers, Compiler-First Web Stack, and Airbus Flight Deck (`bookmarks`, `twitch-channels`, single consolidated `releases` widget without `ghostty-org/ghostty` 404, tabbed `rss` and `videos` groups, and subreddit tabs).
- [x] **Repaired `arcane` (`arcane.francis.db`):** Restored corrupted `data/arcane/arcane.francis.db` actor runtime database from clean snapshot and removed deprecated `JWT_SECRET` environment variable in `compose/core.yml`.
- [x] **Repaired `cross-seed` (`cross-seed.db`):** Recovered corrupted `config/cross-seed/cross-seed.db` via `sqlite3 .recover` so RSS and searchee indexing succeed without `SqliteError: database disk image is malformed`.
- [x] **Fixed `sonarr` -> `qbittorrent` Authentication (`401:Unauthorized`):** Replaced placeholder `00000000` password in Sonarr's qBittorrent DownloadClient settings with the valid `VRG` credential and verified `/api/v3/downloadclient/testall` returns `isValid: true`.
- [x] **Fixed `radarr` Movie Collection Root Folders:** Updated 8 Movie Collections in `radarr.db` from stale `/external/Movies` to `/external/media/movies` following the PANOPTICON restructuring.
- [x] **Hardened `scripts/stage_db_backups.sh` SQLite Snapshot Mode:** Copies `${db_file}` and `${db_file}-wal` (without `-shm`) to a local temp directory before running `sqlite3 .backup` so macOS host `sqlite3` captures all un-checkpointed WAL commits without touching guest Linux VM `-shm` mmap files over VirtioFS.
- [x] **Hardened Symlink Topology & Zero-Loss Media Safeguards (`H1`–`H5`, Completed October 2026):**
  - Converted all 4 TV series directories in `/Volumes/PANOPTICON/media/tv/` (`Impractical Jokers`, `Kochikame: Tokyo Beat Cops`, `Oswald`, `Shin Chan`) from directory symlinks into real directories containing per-file relative symlinks (`432`, `60`, `26`, and `819` links respectively) so destination and source paths never alias the same physical file.
  - Hardened [`scripts/torrent_finished.py`](scripts/torrent_finished.py), [`scripts/migrate_panopticon_live.py`](scripts/migrate_panopticon_live.py), and `config/{sonarr,radarr}/custom_scripts/arr_symlink_dedupe.sh` with `realpath` equality and directory-symlink abort guards, plus season subfolder preservation in `process_sonarr()`.
  - Configured `/external/media/.recycle` (`14`-day retention) and verified `enableCompletedDownloadHandling: false` and `removeCompletedDownloads: false` in both Sonarr and Radarr.
  - Re-pointed `Under the Sea 3D (2009)` in `/Volumes/PANOPTICON/media/movies/` from the `80 MB` `SAMPLE.mkv` to the full `9.59 GB` movie in the torrent folder.
  - **Re-Download Queue (42 episodes lost during Oct 18 directory-symlink upgrade collision):**
    - `Oswald` Season 1 (`S01E01`–`S01E26`, 26 files, `4.36 GB`)
    - `Impractical Jokers` Season 1 (`S01E01`–`S01E16`, 16 files, `6.95 GB`; note `S01E17`, Movie, and all of `S02`–`S09` are 100% intact)

### J. Known Drift and Follow-Ups
- [x] **Prowlarr Stale Indexer & App Cleanup + DB Recovery:** Recovered corrupted `prowlarr.db` (`Tree 16 page 5865`), deleted deprecated `TheRARBG` indexer (`ID 5`) and retired `Readarr` application sync (`ID 4`), and added `RADARR__`, `SONARR__`, `LIDARR__`, and `PROWLARR__SERVER__ALLOWEDHOSTS` in `compose/media.yml`.
- [x] **Reclaimed `11.6 GB` of Unused Docker Images & Removed 13 Empty Anonymous Volumes:** Executed `docker image prune -a -f` and removed dangling `0 B` volumes while preserving the `4.775 GB` stopped Coder workspace volume (`coder-8378beda-cda2-40ff-a1ad-bc2613acad62-home`).
- [x] **Purged Approved Retired Config Directories (`config/readarr`, `config/authelia*`, `_backup_pre_refactor`) & Legacy Pre-Refactor Named Volumes (`860 MB`):** Preserved `config/plex` (`292 MB`), `config/overseerr` (`576 KB`), `config/jellyseerr*`, and `/Users/vrg/Movies/overseerr` per user instruction.
- [x] **Separated `VRG's 1st Birthday` Home Videos from Jellyfin `Movies` Library & Disabled Trickplay-During-Scan CPU Spikes:** Moved `VRG's 1st Birthday` (`.mkv` and `.mpeg`) to `data/media/home-videos/`, created a Jellyfin `Home Videos` library (`collectionType=homevideos`) unchecked in Seerr, updated Jellyfin `Movies` and `Shows` library paths to `/media/external/media/movies` and `/media/external/media/tv`, and set `<ExtractTrickplayImagesDuringLibraryScan>false</ExtractTrickplayImagesDuringLibraryScan>`.
- [x] **Added `x-logging` (`driver: json-file`, `max-size: "10m"`, `max-file: "3"`) Across All 8 `compose/*.yml` Files:** Prevents unbounded container JSON logs from filling the 512 GB internal NVMe SSD.
- [ ] **Merge Historical Overseerr Requests into Active Seerr Database (`scripts/merge_overseerr_history.py`):**
  - Both `config/overseerr/db/db.sqlite3` (`45` media, `10` requests) and `/Users/vrg/Movies/overseerr/db/db.sqlite3` (`43` media, `10` requests) are preserved.
  - Created and dry-run verified [`scripts/merge_overseerr_history.py`](scripts/merge_overseerr_history.py) (`python3 scripts/merge_overseerr_history.py --dry-run`), which backdates `41` `media.createdAt` timestamps to May/June 2025 and inserts all `10` historical `media_request` rows (`2025-05-10` to `2025-06-19` by `admin@example.com` and `member1@example.com`, bringing total requests from `33` to `43`).
  - To execute when ready: `docker stop seerr && python3 scripts/merge_overseerr_history.py --apply && docker start seerr`.
- [ ] Put `glance`, `dozzle`, and `beszel-agent` behind a read-only Docker socket proxy (`wollomatic/socket-proxy:1`) instead of raw `/var/run/docker.sock:ro` mounts.

---

## 🌟 Roadmap: "Lean is Sexy" Container Replacements & Passion-Project Expansions

Full technical analysis and RAM benchmarks: [10_MEGA_OPTIMIZATION_AND_CONTAINER_ROADMAP.md](docs/system_state/10_MEGA_OPTIMIZATION_AND_CONTAINER_ROADMAP.md).

### 1. Next-Gen Container Discovery & Stack Benchmarking (Completed October 2026)
- [x] **Scoured, Benchmarked, and Curated the Best, Latest, and Most Optimized 2026 Containers/Images for Sol:**
  - Completed dual-agent research audit (`10_MEGA_OPTIMIZATION_AND_CONTAINER_ROADMAP.md`) evaluating Go/Rust/C/Svelte/WASM alternatives, RAM footprints on the 16GB M1 Pro, and Apple Silicon native vs OrbStack VM boundaries.

### 2. Download, Identity, Backup & Monitoring Replacements
- [x] **QUI (`qui.vrg.rocks` — DEPLOYED LIVE & FULL CUTOVER REPLACING `cross-seed` & `qbit_manage`):**
  - Deployed `ghcr.io/autobrr/qui:v1.32.0` (`23.6 MiB` RAM) on port `7476` and moved `cross-seed` (`~75 MiB` RAM) to `profiles: ["standby"]` in `compose/download.yml` and `Caddyfile`.
  - Created and tracked [`config/qui/tracker_registry.json`](config/qui/tracker_registry.json) mapping all 26 official short tracker tags (`IPT`, `MAM`, `3DT`, `ULCX`, `MLK`, `RUT`, `DT`, `TL`, `FNP`, `AVZ`, `CZ`, `PHD`, `AT`, `AB`, `PTP`, `BTN`, `BHD`, `BLU`, `ATH`, `FL`, `RED`, `OPS`, `HDB`, `KG`, `CG`, `PUB`) with full display names, privacy levels, site URLs, and announce domains.
  - Configured 25 Tracker Customizations, Radarr + Sonarr External Engines, Prowlarr Torznab indexers (`IPTorrents`, `Milkie`, `RuTracker.org`, `upload.cx`), Cross-Seed (`useHardlinks: true`, `hardlinkBaseDir: "/data/torrents/qui-links"`, `fallbackToRegularMode: true`), Completion Search, Library Scan, Orphan Scan, and 10 FUP/health automation rules in `qui`.
  - Stripped legacy manual tracker tags and retagged all `150 / 150` torrents (`100%` coverage: `MAM: 84`, `IPT: 32`, `PUB: 18`, `3DT: 12`, `ULCX: 2`, `RUT: 1`, `MLK: 1`), pausing `8` public torrents (`1.80 TiB` uploaded) that had already exceeded `ratio >= 1.0`.
- [x] **Backrest + Restic (`backrest.vrg.rocks` — DEPLOYED LIVE):** Deployed `ghcr.io/garethgeorge/backrest:latest` (`~25 MiB` RAM) on port `9898` and overhauled `scripts/stage_db_backups.sh`, `scripts/backup.sh`, and `scripts/restore.sh` to back up all configs, Postgres/SQLite databases, media symlink manifests, and Coder workspace archives to `/Volumes/PANOPTICON/backups/sol-restic` and `rclone:OneDrive:Sol-Restic` with chunk deduplication and AES-256 encryption.
- [x] **Tinyauth v5 + Unified `lldap` Single-Email Identity Spine (`auth.vrg.rocks` & `ldap.vrg.rocks` — DEPLOYED LIVE):**
  - Migrated all `*.vrg.rocks` services from Authentik (`~502 MiB` RAM moved to `profiles: ["standby"]`) to `ghcr.io/tinyauthapp/tinyauth:v5` (`v5.2.0`, `~29.4 MiB` RAM) and `lldap/lldap:stable` (`~12 MiB` RAM) in [`compose/core.yml`](compose/core.yml) and [`Caddyfile`](Caddyfile) using the provider-agnostic `(forward_auth)` snippet (`login.vrg.rocks` and `tinyauth.vrg.rocks` redirect `301` to `https://auth.vrg.rocks{uri}`).
  - Created [`config/auth/users.json`](config/auth/users.json), [`scripts/identity_sync.py`](scripts/identity_sync.py), and [`scripts/allowlist_user.sh`](scripts/allowlist_user.sh) to synchronize every user's single email across Tinyauth, 7 OIDC clients (`paperless-ngx`, `arcane`, `homebox`, `airtrail`, `coder`, `readeck`, `jellyfin`), `lldap` (`dc=vrg,dc=rocks` with `mailalias`), Jellyfin (`LDAP-Auth.xml` + `SSO-Auth.xml` `CanonicalLinks` + user `AuthenticationProviderId`), Seerr (`userType=3` Jellyfin login), and Copyparty (`idp-hm-usr`).
  - Upgraded `copyparty` (`--idp-h-usr Remote-Email` + `--idp-hm-usr`), `qui` (`QUI__AUTH_DISABLED=true`), `code-server` (`AUTH=none`), `backrest` (`auth.disabled=true`), `radarr`, `sonarr`, `lidarr`, `prowlarr` (`<AuthenticationMethod>External</AuthenticationMethod>`), and `bazarr` (`auth.type: null`) so there are zero double-login screens behind Tinyauth forward-auth.
  - Enforced per-app admin-only ACLs (`TINYAUTH_APPS_<APP>_OAUTH_WHITELIST`) on all infrastructure routes (`code`, `backrest`, `qui`, `radarr`, `sonarr`, `lidarr`, `prowlarr`, `bazarr`, `cs`, `byparr`, `pb`, `router`, `ldap`) and documented in [`11_AUTHENTICATION_AND_SSO_STRATEGY.md`](docs/system_state/11_AUTHENTICATION_AND_SSO_STRATEGY.md).
- [x] **Wave 2 Standby Bloat Cleanup (Completed October 2026):**
  - Removed superseded standby services (`dockge`, `uptime-kuma`, `homarr`, `qbit_manage`, `flood`, `calibre`, `calibre-web`, `rclone-gui`) from `compose/*.yml`, `Caddyfile`, and `ports.json`.
- [ ] **Beszel + Dozzle + Gatus behind `wollomatic/socket-proxy` (Standby / Low Priority):** Keep in `standby` profile until needed (`beszel`, `dozzle`, `gatus`).

### 3. Zero-Container Static Suite (Served Directly by Caddy from `web/` at `0 MiB` RAM — DEPLOYED LIVE)
Managed via [`scripts/sync_static_tools.sh`](scripts/sync_static_tools.sh) and mounted into `caddy` (`compose/core.yml`):
- [x] **BentoPDF (`pdf.vrg.rocks` — DEPLOYED LIVE):** Client-side WebAssembly PDF toolkit (`alam00000/bentopdf`, `0 MiB` server RAM) replacing bloated Java `Stirling-PDF` (`400+ MiB`).
- [x] **IT-Tools (`tools.vrg.rocks` — DEPLOYED LIVE):** 80+ client-side developer utilities (`CorentinTh/it-tools`).
- [x] **CyberChef (`chef.vrg.rocks` — DEPLOYED LIVE):** GCHQ client-side data encoding and binary analysis web app (`gchq/CyberChef`).
- [x] **OpenSpeedTest (`speed.vrg.rocks` — DEPLOYED LIVE):** Static HTML5 LAN and Wi-Fi throughput benchmark (`openspeedtest/Speed-Test`).
- [x] **Excalidraw (`draw.vrg.rocks` — DEPLOYED LIVE):** Static virtual whiteboard (`excalidraw/excalidraw`).
- [x] **MediaInfo Web (`mi.vrg.rocks` — DEPLOYED LIVE):** Custom GM3/Catppuccin Mocha client-side WebAssembly `mediainfo.js` inspector with zero-copy chunked reading for 80 GB+ 4K UHD Remuxes (Dolby Vision Profile, HDR10 MaxCLL/MaxFALL, TrueHD Atmos tracks, JSON/Text export).

### 4. Knowledge, Bookmarks, RSS & Encrypted Sharing
- [x] **Readeck (`links.vrg.rocks` — DEPLOYED LIVE):** Single-binary Go + SQLite bookmark and read-later archiver (`codeberg.org/readeck/readeck:latest`, `~45 MiB` RAM) with full-text extraction and EPUB export. Initialized admin user `VRG` with `CORE_PASSWORD`.
- [x] **Enclosed (`send.vrg.rocks` — DEPLOYED LIVE):** Zero-knowledge client-side encrypted notes and self-destructing file drops built with Hono + TypeScript (`ghcr.io/corentinth/enclosed:latest`, `~27 MiB` RAM).
- [x] **PocketBase Sandbox (`pb.vrg.rocks` — DEPLOYED LIVE):** Single-binary Go + SQLite backend (`ghcr.io/muchobien/pocketbase:latest`, `~27 MiB` RAM) for Svelte 5 / Datastar / HTMX rapid prototyping. Initialized superuser `admin@example.com` with `CORE_PASSWORD` at `https://pb.vrg.rocks/_/`.
- [x] **Retired Standby Desktop `calibre` & `calibre-web`:** Kept `kavita` in standby for EPUB/PDF/Manga/Comics.
- [ ] **Fusion or Miniflux (`rss.vrg.rocks`):** Go + SQLite RSS/Atom reader (`ghcr.io/0x2e/fusion:latest` or `miniflux/miniflux:latest`, `~25-50 MiB` RAM) with Fever/Google Reader API support.

### 5. Cinema, IMAX & Airbus Flight Deck Passion Projects
- [x] **AirTrail (`fly.vrg.rocks` — DEPLOYED LIVE):** Self-hosted personal flight log and aircraft registry built with **SvelteKit** (`johly/airtrail:latest`, sharing `paperless-db` PostgreSQL 17 `airtrail` database) with Flightradar24/Flighty import and REST API integration.
- [ ] **adsb-ultrafeeder (`adsb.vrg.rocks` on Raspberry Pi 3B):** Run `ghcr.io/sdr-enthusiasts/docker-adsb-ultrafeeder:latest` (`readsb` + `tar1090`) on the Raspberry Pi 3B with the RTL-SDR dongle and reverse-proxy `adsb.vrg.rocks` via Sol's Caddy.
- [ ] **ErsatzTV (`tv.vrg.rocks` Native macOS):** Run ErsatzTV natively on macOS (for Apple VideoToolbox hardware transcoding) to build 24/7 rolling IMAX, Criterion, and Nolan live channels with `data/media/preshows` bumpers in Jellyfin Live TV.
- [ ] **Jellyfin Intro Skipper & Playback Reporting Plugins:** Install in-process Jellyfin plugins (`0 MB` extra container RAM) for automatic intro skipping and SQLite watch analytics.

---

## ✅ Completed: October 2026 Architectural Hardening (`/double-agent` Review)

Full record: [09_ARCHITECTURAL_AUDIT_AND_UPGRADE_PLAN.md](docs/system_state/09_ARCHITECTURAL_AUDIT_AND_UPGRADE_PLAN.md).

### Phase 1: Functional Bug Fixes
- [x] `paperless-webserver` now receives `PAPERLESS_DBNAME`, `PAPERLESS_DBUSER`, and `PAPERLESS_DBPASS`. Replaced `PAPERLESS_WORKER_CONCURRENCY` and `PAPERLESS_OCR_THREADS` with `PAPERLESS_THREADS_PER_WORKER: 2` (kept `PAPERLESS_TASK_WORKERS: 2`).
- [x] `AUTHENTIK_WORKERS: 2` replaced with the upstream `AUTHENTIK_WEB__WORKERS: 2`.
- [x] Deleted the duplicate `coder/default.tf`. `coder/main.tf` installs the prebuilt `jj` `v0.28.2` musl binary instead of `cargo install jj-cli`.
- [x] `scripts/setup_jellyfin_metal.py` keeps an existing `config/jellyfin_metal` and wipes it only with `--reset`.
- [x] `scripts/test_cross_seed.sh` runs as `${PUID}:${PGID}` (`501:20`), not root, and tests `/data/torrents` to `/data/media` hardlinks.

### Phase 2: Caddy and Authentik Hardening
- [x] `inv.vrg.rocks` CORS allows only `https://scan.vrg.rocks` (no origin reflection with credentials).
- [x] `import forward_auth` on `dash.vrg.rocks` and `code.vrg.rocks`. `qb.vrg.rocks` keeps qBittorrent native auth for the Android app.
- [x] `authentik-server` ports `9000` and `9443` bound to `127.0.0.1`.
- [x] `authentik-worker` runs without `user: root` and without `/var/run/docker.sock` (Caddy uses the embedded outpost).
- [x] `arcane` `LOG_LEVEL: debug` changed to `info`.
- [x] 18 standby vhosts commented out under `--- Standby ... Routes ---` headers.

### Phase 3: Backup and Restore Integrity
- [x] `scripts/backup.sh`: line-by-line `.env` loader, `set -euo pipefail`, atomic `pg_dump` writes, online `sqlite3 .backup` snapshots to `data/backups/sqlite/`, `--backup-dir OneDrive:Sol-archive/<timestamp>`, rclone failures no longer swallowed, working `--profile ops` fallback.
- [x] `scripts/restore.sh`: restores missing SQLite snapshots, imports both dumps with `gunzip -c | docker exec -i ... psql` after `pg_isready` (`--restore-dbs`, or `--start-stack` on empty clusters), initializes `config/rclone/filter.txt`, and uses guarded array expansions for macOS bash 3.2.
- [x] Tracked `config/rclone/filter.txt.example` that excludes live PostgreSQL clusters, Redis, and SQLite `-wal`/`-shm` files. `.gitignore` ignores `/config/*` except that template.
- [x] `.env.example` quotes `PAPERLESS_OCR_LANGUAGES` and `PAPERLESS_SOCIALACCOUNT_PROVIDERS` so `bash` and Compose parse it the same way.

### Phase 4: Compose Modernization
- [x] All standby services converted from `#` comments to `profiles: ["standby"]` (26 services, `rclone` also on `ops`). Default `docker compose up -d` starts 24 containers.
- [x] `.env` tag pins: `CADDY_TAG=2`, `PAPERLESS_TAG=2`, `ARCANE_TAG=latest`, `CODER_TAG=latest` (Authentik already pinned at `2026.5.3`). `paperless-broker` on `redis:8-alpine`.
- [x] `glance` uses `TZ` instead of the missing macOS `/etc/timezone`. Removed SELinux `:z` suffixes.
- [x] `byparr` (`ghcr.io/thephaseless/byparr:latest`) replaces FlareSolverr on `8191` with the alias `flaresolverr`. `flaresolverr` moved to standby.
- [x] `qbittorrent` and `cross-seed` mount both `/downloads` and `/data` as a staging step for the cutover.
- [x] `paperless-db` kept on Debian `postgres:17` (glibc collation, decision record in `09`).

### Phase 5: Documentation and Registry Sync
- [x] `homebox` marked standby everywhere (compose profile, `ports.json`, `README.md`, `docs/system_state/`).
- [x] `ports.json` lists 24 active services plus `jellyfin-metal` and 26 standby services with their `profile`.
- [x] Updated `docs/system_state/00` to `08`. Added `09_ARCHITECTURAL_AUDIT_AND_UPGRADE_PLAN.md`, `docs/FLASH_LOCAL_VERIFICATION_RUNBOOK.md`, and rewritten `README.md`, `TODO.md`, and `coder/README.md`.

---

## 📋 Earlier Milestones

### 1. ⚡ Performance and Resource Optimization
- [x] **macOS / Apple Silicon efficiency:**
  - Audited CPU and RAM across the active containers (about 2.8 GB of 16 GB unified RAM at audit time).
  - M1 Pro (6P+2E) concurrency tuning for Paperless-ngx (`PAPERLESS_TASK_WORKERS: 2`, `PAPERLESS_THREADS_PER_WORKER: 2`) and Authentik (`AUTHENTIK_WEB__WORKERS: 2`). The earlier `PAPERLESS_WORKER_CONCURRENCY`, `PAPERLESS_OCR_THREADS`, and `AUTHENTIK_WORKERS` keys had no effect upstream and were replaced in October 2026.
- [x] **Storage and database tuning:**
  - Documented APFS zero-copy hardlinks (`torrents/` to `media/`) vs ExFAT external drive copies.
  - PostgreSQL 16 and 17 tuning (`shared_buffers=256MB`, `work_mem=16MB`, `effective_cache_size=1GB`, `maintenance_work_mem=64MB`, `wal_buffers=16MB`, `checkpoint_completion_target=0.9`) on `authentik-postgresql` and `paperless-db`.
  - SQLite WAL pragmas for Servarr and Arcane (`journal_mode(WAL)`, `busy_timeout(2500)`, `_txlock=immediate`).
- [x] **Network and ingress tuning:**
  - Upstream DNS resolvers (`1.1.1.1`, `9.9.9.9`) on `radarr`, `sonarr`, `bazarr`, `lidarr`, `prowlarr`, `byparr`, `qbittorrent`, and `cross-seed` to bypass ISP rate limits and blocks. `seerr` uses `8.8.8.8` and `1.1.1.1` for TMDb.
  - Caddy streaming buffers (`read_buffer 32768`, `write_buffer 32768`, `keepalive 120s`) on the Jellyfin and Jellyfin Metal routes.
  - Jellyfin transcode throttling (`EnableThrottling: true`, `ThrottleDelaySeconds: 120`, `EncodingThreadCount: 4`) in `encoding.xml`.

### 2. 🛡️ Disaster Recovery, Backup, and Restore
- [x] **OneDrive rclone sync:**
  - Filter covers persistent configs, credentials, and custom templates while it ignores multi-terabyte media, transcode caches, and logs. Tracked as `config/rclone/filter.txt.example`.
  - Keeps `data/media/preshows/**` and excludes bulk movies, TV, and torrent payloads.
  - Live `pg_dump` hooks for `authentik-postgresql` and `paperless-db` before every sync.
  - Includes all 444+ `.torrent` and `.fastresume` files from qBittorrent, Cross-Seed, and saved torrent directories.
- [x] **One-command restore:**
  - `scripts/restore.sh` supports `--dry-run`, `--skip-cloud-pull`, `--restore-dbs`, and `--start-stack`.
  - Disaster recovery steps documented in `docs/system_state/02_STORAGE_AND_VOLUMES.md` and `README.md`.

### 3. 📖 Repository Documentation (`README.md`)
- [x] Architecture, domain stacks, active and standby inventory, storage model, port matrix, and security model.
- [x] Operational commands: stack lifecycle, standby and ops profiles, service-scoped restarts (`docker compose restart <services>`), updates, logs, backups, restore, and Jellyfin Metal.
- [x] Repository index with every tracked path.

### 4. 🚀 Git and Jujutsu (jj) Version Control
- [x] **Repository hygiene and `.gitignore`:**
  - Root `.gitignore` excludes `.env`, `/data/`, `/config/*` (except `config/rclone/filter.txt.example`), `/web/`, `/quartz/`, `/priv/`, `/.hist/`, `/logs/`, `/docs/archive/`, `/_backup_pre_refactor/`, Terraform state, `.DS_Store`, and temporary files.
  - Tracks only declarative infrastructure: `docker-compose.yml`, `compose/*.yml`, `Caddyfile`, `ports.json`, `.env.example`, `config/rclone/filter.txt.example`, `scripts/*`, `coder/*.tf`, `docs/`, and `README.md`.
- [x] **Jujutsu initialized and published to GitHub:**
  - Private repository [`varungupta3009/Sol`](https://github.com/varungupta3009/Sol).
  - Initial commit and `main` bookmark pushed.

  **Everyday Jujutsu commands:**
  ```bash
  # Check working copy changes
  jj status

  # View the commit graph
  jj log

  # Start a new working copy commit
  jj new

  # Push the latest bookmark changes to GitHub
  jj git push
  ```

### 5. 🍿 Native macOS Jellyfin on Bare Metal (Apple VideoToolbox)
- [x] **Running in parallel with containerized Jellyfin:**
  - VideoToolbox hardware acceleration for 4K HEVC and AV1 decoding and HDR tone mapping on the M1 Pro media engine.
  - Endpoint `https://metal.vrg.rocks` to `http://host.docker.internal:8097` (see `Caddyfile`).
  - Paths: config `/Users/vrg/Documents/Sol/config/jellyfin_metal`, data `.../jellyfin_metal/data`, cache `.../jellyfin_metal/cache`, logs `.../jellyfin_metal/log`.
- [x] **Launch and bootstrap:**
  ```bash
  # Launch (keeps the existing database)
  python3 scripts/setup_jellyfin_metal.py

  # Wipe and re-run the setup wizard through the API
  python3 scripts/setup_jellyfin_metal.py --reset

  # Manual launch
  nohup /Applications/Jellyfin.app/Contents/MacOS/jellyfin \
    --configdir /Users/vrg/Documents/Sol/config/jellyfin_metal \
    --datadir /Users/vrg/Documents/Sol/config/jellyfin_metal/data \
    --cachedir /Users/vrg/Documents/Sol/config/jellyfin_metal/cache \
    --logdir /Users/vrg/Documents/Sol/config/jellyfin_metal/log \
    --webdir /Applications/Jellyfin.app/Contents/Resources/jellyfin-web \
    --ffmpeg /Applications/Jellyfin.app/Contents/MacOS/ffmpeg > /dev/null 2>&1 &
  ```

---

## 🧩 Backlog: Standby Services Activation

Start any of these with `docker compose --profile standby up -d <service>`, then uncomment the matching vhost in `Caddyfile` and recreate `caddy`.

- [ ] **Gatus health page (`compose/monitoring.yml`):**
  - Create `config/gatus/config.yaml` with HTTP and ping checks for every internal service.
  - Enable `status.vrg.rocks` to `http://gatus:8080`.
- [ ] **Recyclarr TRaSH sync (`compose/media.yml`):**
  - Create `config/recyclarr/recyclarr.yml` with the Sonarr and Radarr API keys.
  - Run a first dry-run sync of the 4K and 1080p custom formats and scores.
- [ ] **Unpackerr (`compose/download.yml`):**
  - Set `SONARR_API_KEY`, `RADARR_API_KEY`, and `LIDARR_API_KEY` in `.env`.
  - Verify extraction under `UN_FOLDER_0_PATH: /data/torrents` and the Servarr hooks.

---

## 🔮 Backlog: Dynamic Label Ingress with `caddy-docker-proxy`

- [ ] **Goal:**
  - Route `*.vrg.rocks` from Docker Compose labels instead of a static `Caddyfile` and `ports.json`.
  - Compose files become the single source for routes, internal ports, TLS, and forward-auth policy.
- [ ] **Design notes:**
  - **Image:** Replace `caddy:${CADDY_TAG:-2}` in `compose/core.yml` with `lucaslorentz/caddy-docker-proxy` (multi-arch ARM64).
  - **Docker socket:** Mount `/var/run/docker.sock:/var/run/docker.sock:ro` into Caddy (or reuse the planned socket proxy).
  - **Hybrid Caddyfile:** Keep a small base `Caddyfile` for global options, the `(forward_auth)` snippet, and the static sites (`/mind`, `/fam`, `/scan`, `/aysynbm`).
  - **Label format:**
    ```yaml
    labels:
      caddy: radarr.vrg.rocks
      caddy.reverse_proxy: "{{upstreams 7878}}"
      caddy.import: authentik
    ```
  - **Profiles fit:** Standby services carry their own labels, so their routes appear only while they run. That removes the commented vhost blocks.
  - **Retirement:** Once active, retire `ports.json`.
