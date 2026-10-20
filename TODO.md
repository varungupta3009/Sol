# Sol Server Roadmap and Milestone Ledger

> **Project:** Sol Home Server (`*.vrg.rocks`)
> **Host:** Apple Silicon M1 Pro macOS (OrbStack Docker engine, `/Users/vrg/Documents/Sol`)
> **Status:** October 20, 2026 31-agent swarm audit, Wave 1 to 3 consolidation, Tinyauth v5 + LLDAP identity spine, and 2-Tier Backrest + Restic DR verified live on `dash.vrg.rocks` (`29/29` active containers `(healthy)`, `16` standby/ops containers, `10` static web apps, `1` standby native app). See [`docs/SERVER_HISTORY_AND_EVOLUTION.md`](docs/SERVER_HISTORY_AND_EVOLUTION.md).

---

## 🔭 Open Backlog & Optional Enhancements

### 1. Media Re-Download Queue & Optional Plugins
- [ ] **Re-Download Queue (42 episodes lost during the Oct 18 directory-symlink upgrade collision prior to `H1` to `H5` per-file symlink hardening):**
  - `Oswald` Season 1 (`S01E01` to `S01E26`, 26 files, `4.36 GB`)
  - `Impractical Jokers` Season 1 (`S01E01` to `S01E16`, 16 files, `6.95 GB`, while `S01E17`, Movie, and `S02` to `S09` are 100% intact)
- [ ] **Jellyfin Intro Skipper & Playback Reporting Plugins:** Install in-process Jellyfin plugins (`0 MB` extra container RAM) for automatic intro skipping and SQLite watch analytics.
- [ ] **ErsatzTV (`tv.vrg.rocks` Native macOS):** Run ErsatzTV natively on macOS (for Apple VideoToolbox hardware transcoding) to build 24/7 rolling IMAX, Criterion, and Nolan live channels with `data/media/preshows` bumpers in Jellyfin Live TV.

### 2. Aviation, RSS & Infrastructure Optional Projects
- [ ] **adsb-ultrafeeder (`adsb.vrg.rocks` on Raspberry Pi 3B):** Run `ghcr.io/sdr-enthusiasts/docker-adsb-ultrafeeder:latest` (`readsb` + `tar1090`) on the Raspberry Pi 3B with the RTL-SDR dongle and reverse-proxy `adsb.vrg.rocks` via Sol's Caddy.
- [ ] **Fusion or Miniflux (`rss.vrg.rocks`):** Go + SQLite RSS/Atom reader (`ghcr.io/0x2e/fusion:latest` or `miniflux/miniflux:latest`, `~25-50 MiB` RAM) with Fever and Google Reader API support.
- [ ] **Read-Only Docker Socket Proxy (`wollomatic/socket-proxy:1`):** Put `glance`, `dozzle`, and `beszel-agent` behind a read-only Docker socket proxy instead of direct `/var/run/docker.sock:ro` mounts.
- [ ] **Purge Legacy Raw `OneDrive:Sol` Folder (Pre-Restic):** Optionally `rclone purge` the superseded unencrypted `OneDrive:Sol` directory now that encrypted `rclone:OneDrive:Sol-Restic` snapshots are active.

### 3. Standby Services Activation (On-Demand via `--profile standby`)
Start any of these with `docker compose --profile standby up -d <service>`, uncomment the matching vhost in `Caddyfile`, and recreate `caddy`:
- [ ] **Gatus health page (`compose/monitoring.yml`):** Create `config/gatus/config.yaml` and enable `status.vrg.rocks` to `http://gatus:8080`.
- [ ] **Recyclarr TRaSH sync (`compose/media.yml`):** Create `config/recyclarr/recyclarr.yml` with Sonarr and Radarr API keys and run a dry-run sync of custom formats.
- [ ] **Unpackerr (`compose/download.yml`):** Verify archive extraction under `UN_FOLDER_0_PATH: /data/torrents` and Servarr hooks.

### 4. Dynamic Label Ingress (`caddy-docker-proxy`, Optional)
- [ ] **Goal:** Route `*.vrg.rocks` from Docker Compose labels so standby service routes appear automatically only while they run.

---

## ✅ Completed: October 20, 2026 31-Agent Swarm Audit & Full-Stack Hardening

Full record: [`10_MEGA_OPTIMIZATION_AND_CONTAINER_ROADMAP.md`](docs/system_state/10_MEGA_OPTIMIZATION_AND_CONTAINER_ROADMAP.md) and [`docs/SERVER_HISTORY_AND_EVOLUTION.md`](docs/SERVER_HISTORY_AND_EVOLUTION.md).

- [x] **100% Container Healthcheck Coverage (`29/29` `(healthy)`):** Added internal healthchecks to `caddy`, `arcane` (exec array `CMD` for Distroless), `glance`, `jellyfin`, `radarr`, `sonarr`, `lidarr`, `prowlarr`, `bazarr`, `byparr` (`/openapi.json`), `qbittorrent`, `ignis` (`/api/version`), `code-server`, `coder`, `backrest`, and `enclosed`.
- [x] **Eliminated macOS `launchd` TCC Blocks (`com.vrg.sol.db-stage.plist` & `com.vrg.sol.identity-sync.plist`):**
  - Created and tracked `scripts/launchd/com.vrg.sol.db-stage.plist` (`03:00 IST`) and `scripts/launchd/com.vrg.sol.identity-sync.plist` (`WatchPaths` + `300s`).
  - Invoked `stage_db_backups.sh` via `/opt/homebrew/bin/python3` without `WorkingDirectory` inside `~/Documents` (bypassing `kTCCServiceSystemPolicyDocumentsFolder` `Exit 126`).
  - Routed symlink manifest discovery through an ephemeral `redis:8-alpine` container over OrbStack VirtioFS (`~12s`, bypassing `kTCCServiceSystemPolicyRemovableVolumes` on `/Volumes/PANOPTICON`).
  - Cleaned `data/backups/sqlite/` to **29 self-contained SQLite snapshots** (`PRAGMA journal_mode=DELETE`, `0` `-wal`/`-shm` sidecars, excluding `logs.db`, `cache.db`, `auxiliary.db`, `up2k.db`, and `MediaCover*`), stripped PG 17 `SET transaction_timeout` from `coder_db.sql.gz`, and recorded `coder-8378beda-cda2-40ff-a1ad-bc2613acad62-home` in `data/backups/coder_volume_name.txt`.
- [x] **Stopped `WatchPaths` Self-Triggering Login Write Loop (`scripts/identity_sync.py`):**
  - Replaced LLDAP `POST /auth/simple/login` + GraphQL polling with direct read-only SQLite reads (`file:/Users/vrg/Documents/Sol/data/lldap/users.db?immutable=1`) and an early `<50ms` SHA-256 fast-path check (`/tmp/sol_identity_sync.sha256`).
  - Pruned 59 stale `jwt_storage` and 58 stale `jwt_refresh_storage` headless `admin` rows from `data/lldap/users.db`.
  - Restricted `arcane` and `coder` OIDC consents in `data/tinyauth/tinyauth.db` strictly to `admin` user `vrg`, scoped AirTrail `is_owner = true` to `vrg`, pre-seeded Readeck users with the `preserve_lldap_user_identity` SQLite trigger, and locked `TINYAUTH_APPS_{IGNIS,MIND,SCAN,AYSYNBM}` to `${TINYAUTH_ADMIN_EMAILS:?}`.
- [x] **Caddyfile Security & Route Hardening:**
  - Added `Permissions-Policy` and `X-Permitted-Cross-Domain-Policies: none` to `(security_headers)`.
  - Wrapped `try_files` and `file_server` inside `route { ... }` in `(static_site)` (preventing unauthenticated filesystem path existence probing), added `@immutable` asset caching, and guarded `handle_errors` with `@custom_err`.
  - Added `import forward_auth` to `aysynbm.vrg.rocks`, gated note creation on `send.vrg.rocks` and unauthenticated external `POST`/`PUT` publishes on `ntfy.vrg.rocks` behind `forward_auth`, added `301` redirect blocks for `notes.vrg.rocks` (`-> ignis.vrg.rocks`) and `flaresolverr.vrg.rocks` (`-> byparr.vrg.rocks`), added `302` root redirect on `pb.vrg.rocks` (`-> /_/`), and added `POST /upload*` `200 OK` responder on `speed.vrg.rocks`.
- [x] **Jellyfin, Servarr, qBittorrent, Coder & PocketBase Live Fixes:**
  - Mounted `/tmp/jellyfin:size=2g,uid=501,gid=20,mode=0755` on `jellyfin`, switched `database.xml` to `<LockingBehavior>Optimistic</LockingBehavior>`, and moved `The Ba***ds of Business (1995).mp4` out of `Movies` into `data/media/home-videos/` (eliminating 5-minute Seerr TMDb sync errors).
  - Re-pointed all 7 recoverable cross-seed symlinks in `data/torrents/cross-seed-links/`, linked *The Sixth Sense (1999)* (`movieFileId: 472`) in Radarr, updated `sonarr` category `save_path` to `/external/torrents/tv`, and set `logLevel` to `info` across `prowlarr`, `radarr`, `sonarr`, and `lidarr`.
  - Added `group_add: ["0"]` to `coder` (`compose/coding.yml`) and pushed the `sol-workspace` Terraform template live.
  - Set `logs.minLevel = 4` in PocketBase (`data/pocketbase/data.db`) and truncated 2,534 `/api/health` probe rows from `auxiliary.db`.
  - Converted `/Users/vrg/Documents/Sol/web/fam` from an external symlink into a real directory copy so Restic backs up `vault.enc`.
  - Deleted retired `authentik-*`, `flaresolverr`, and `cross-seed` blocks from `compose/*.yml` and `ports.json`, and removed leftover `config/{jellyfin_metal,plex,cross-seed,homarr,calibre,calibre-web,qbit_manage,syncthing,flood}` and `data/{uptime-kuma,dockge,syncthing,authentik}` directories on `dash.vrg.rocks`.

---

## ✅ Completed: October 18 to 19, 2026 Architectural Renaissance (Waves 1 to 3, Tinyauth + LLDAP, QUI, Backrest)

### 1. Download, Identity & Backup Replacements
- [x] **QUI (`qui.vrg.rocks`):** Deployed `ghcr.io/autobrr/qui:v1.32.0` on port `7476`, created [`config/qui/tracker_registry.json`](config/qui/tracker_registry.json) (26 tracker codes), configured 25 Tracker Customizations, 10 FUP and health automation rules, Prowlarr Torznab cross-seeding, and tagged `150 / 150` torrents (`MAM: 84`, `IPT: 32`, `PUB: 18`, `3DT: 12`, `ULCX: 2`, `RUT: 1`, `MLK: 1`).
- [x] **Backrest + Restic (`backrest.vrg.rocks`):** Deployed `ghcr.io/garethgeorge/backrest:latest` on port `9898` and overhauled `scripts/stage_db_backups.sh`, `scripts/backup.sh`, and `scripts/restore.sh` to snapshot `/Users/vrg/Documents/Sol` to `/Volumes/PANOPTICON/backups/sol-restic` and `rclone:OneDrive:Sol-Restic`.
- [x] **Tinyauth v5 + Unified `lldap` Identity Spine (`auth.vrg.rocks` & `ldap.vrg.rocks`):** Migrated all `*.vrg.rocks` services from Authentik (`~502 MiB` RAM) to `ghcr.io/tinyauthapp/tinyauth:v5` (`v5.2.0`, `~29 MiB` RAM) and `ghcr.io/lldap/lldap:stable` (`~12 MiB` RAM) with 0-click Google OAuth, 7 OIDC clients, and `scripts/identity_sync.py`.
- [x] **Merged Historical Overseerr Requests into Active Seerr Database (`scripts/archive/merge_overseerr_history.py`):** Backdated `41` `media.createdAt` timestamps to May/June 2025 and inserted all `10` historical `media_request` rows (`2025-05-10` to `2025-06-19`), bringing total Seerr requests from `33` to `43`.

### 2. Wave 1: Zero-Container Static Suite (`0 MiB` RAM via Caddy `web/`)
Managed via [`scripts/sync_static_tools.sh`](scripts/sync_static_tools.sh):
- [x] **BentoPDF (`pdf.vrg.rocks`):** Client-side WebAssembly PDF toolkit (`alam00000/bentopdf`).
- [x] **IT-Tools (`tools.vrg.rocks`):** 80+ client-side developer utilities (`CorentinTh/it-tools`).
- [x] **CyberChef (`chef.vrg.rocks`):** GCHQ client-side data encoding and binary analysis web app (`gchq/CyberChef`).
- [x] **OpenSpeedTest (`speed.vrg.rocks`):** Static HTML5 LAN and Wi-Fi throughput benchmark (`openspeedtest/Speed-Test`).
- [x] **Excalidraw (`draw.vrg.rocks`):** Static virtual whiteboard (`excalidraw/excalidraw`).
- [x] **MediaInfo Web (`mi.vrg.rocks`):** Client-side WebAssembly `mediainfo.js` inspector for 80 GB+ 4K UHD Remuxes.

### 3. Wave 2 & Wave 3: Standby Bloat Cleanup & Lean Active Containers
- [x] **Wave 2 Cleanup:** Removed superseded services (`dockge`, `uptime-kuma`, `homarr`, `qbit_manage`, `flood`, `calibre`, `calibre-web`, `rclone-gui`, `authentik-*`, `flaresolverr`, `cross-seed`) and reclaimed over `13.5 GB` of disk space.
- [x] **Readeck (`links.vrg.rocks`):** Single-binary Go + SQLite bookmark and read-later archiver (`codeberg.org/readeck/readeck:latest`).
- [x] **Enclosed (`send.vrg.rocks`):** Zero-knowledge client-side encrypted notes and file drops (`ghcr.io/corentinth/enclosed:latest`).
- [x] **PocketBase (`pb.vrg.rocks`):** Single-binary Go + SQLite backend sandbox (`ghcr.io/muchobien/pocketbase:latest`).
- [x] **AirTrail (`fly.vrg.rocks`):** Self-hosted personal flight log and aircraft registry (`johly/airtrail:latest`, sharing `paperless-db` PostgreSQL 17).

### 4. Storage Restructuring, `111.4 GiB` SSD Reclamation & `H1` to `H5` Symlink Hardening
- [x] Restructured `/Volumes/PANOPTICON` into TRaSH-aligned `torrents/` and `media/` directories and reclaimed `111.4 GiB` on the internal APFS SSD.
- [x] Migrated all 289 `.fastresume` path entries to `/data/torrents` (`212`) and `/external/torrents` (`77`) and removed the legacy `/downloads` bind mount.
- [x] Implemented Option A (`scripts/torrent_finished.py` and `scripts/arr_symlink_dedupe.sh`) and converted all 4 external TV series folders into real directories containing per-file relative symlinks (`H1` to `H5`) with `/external/media/.recycle` (`14`-day retention).
- [x] Migrated `paperless-db` to `postgres:17-alpine` (`PG 17.11` musl) and promoted repaired `homebox` (`inv.vrg.rocks`) to active production.

---

## ✅ Completed: October 17, 2026 Architectural Hardening (`/double-agent` Review)

Full record: [`09_ARCHITECTURAL_AUDIT_AND_UPGRADE_PLAN.md`](docs/system_state/09_ARCHITECTURAL_AUDIT_AND_UPGRADE_PLAN.md) and [`docs/archive/FLASH_LOCAL_VERIFICATION_RUNBOOK.md`](docs/archive/FLASH_LOCAL_VERIFICATION_RUNBOOK.md).

- [x] **Functional Bug Fixes:** Fixed `paperless-webserver` DB env vars and worker concurrency (`PAPERLESS_TASK_WORKERS: 2`, `PAPERLESS_THREADS_PER_WORKER: 2`), deleted duplicate `coder/default.tf`, switched `coder/main.tf` to prebuilt `jj` `v0.28.2` musl binary, and added `x-logging` (`10m` x `3`) across all 8 compose files.
- [x] **Compose Profiles & Byparr Cutover:** Converted commented YAML blocks into `profiles: ["standby"]`, replaced `flaresolverr` with `byparr` (`ghcr.io/thephaseless/byparr:latest`), and redesigned Glance into a 3-page Command Center (`/sol`, `/stats`, `/radar`).
- [x] **Git, Jujutsu (jj) & Native Jellyfin Metal (`2026-08-22`):** Initialized declarative Git/Jujutsu repository (`varungupta3009/Sol`) and automated native macOS `jellyfin-metal` (`scripts/setup_jellyfin_metal.py`).
