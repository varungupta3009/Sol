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
- [x] Inspect `qBittorrent.conf` (`SavePath`, `TempPath`), `categories.json`, `BT_backup` path counts (101 on `/downloads`, 46 on `/external`, 0 on `/data`), Cross-Seed `config.js` (`linkDirs`, `dataDirs`, `torrentDir`), and the Radarr, Sonarr, and Lidarr `RemotePathMappings`.
- [x] Verified dry-run of `/tmp/qbt_rewrite.py` on 147 `.fastresume` files: `changed=101 untouched=46 skipped=0`.
- [ ] **TODO (Deferred to tomorrow per user instruction - Prompt user when restarting work):**
  - [ ] Phase A: point qBittorrent defaults and categories at `/data/torrents` (qBittorrent stopped).
  - [ ] Phase B: apply `/tmp/qbt_rewrite.py` to rewrite `/downloads` to `/data/torrents` in `.fastresume` files offline (`docker compose stop qbittorrent cross-seed`, backup `BT_backup`, apply, verify 0 remain).
  - [ ] Phase C: set Cross-Seed `linkDirs` to `/data/torrents/cross-seed-links` (plus `/external/cross-seed-links`) and add `/data/media/movies` and `/data/media/tv` to `dataDirs`. Remove the `*arr` Remote Path Mappings. Verify a shared inode on one new import.
  - [ ] After one full Cross-Seed cycle, remove `- ${DOCKER_DATA_DIR}/torrents:/downloads` from `qbittorrent`, `cross-seed`, and `qbit_manage` in `compose/download.yml`.

### F. Optional: `paperless-db` `postgres:17` to `postgres:17-alpine` ([Task 6](docs/FLASH_LOCAL_VERIFICATION_RUNBOOK.md#task-6-optional-migrate-paperless-db-from-postgres17-glibc-to-postgres17-alpine-musl))
- [ ] *(Skipped per user instruction)*

### G. Optional: `homebox` SQLite Recovery ([Task 7](docs/FLASH_LOCAL_VERIFICATION_RUNBOOK.md#task-7-optional-diagnose-and-repair-the-homebox-database))
- [ ] *(Skipped per user instruction)*

### H. Known Drift and Follow-Ups
- [ ] `home.vrg.rocks` is an active vhost but `homeassistant` is on the standby profile (`502`). Either comment out the vhost or start Home Assistant.
- [ ] Put `glance` behind a read-only Docker socket proxy (`wollomatic/socket-proxy`, `GET /containers/(json|.*/json)` only) instead of the raw `/var/run/docker.sock:ro` mount.
- [ ] Consider minor-version pins for `paperless-ngx`, `caddy`, `arcane`, and `coder` once the live versions are recorded.
- [ ] Consider switching `PAPERLESS_DBPASS` and `POSTGRES_PASSWORD` from `:-paperless` to `:?` (fail loudly) after item A passes.

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
- [x] `import authentik` on `dash.vrg.rocks` and `code.vrg.rocks`. `qb.vrg.rocks` keeps qBittorrent native auth for the Android app.
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
  - **Hybrid Caddyfile:** Keep a small base `Caddyfile` for global options, the `(authentik)` snippet, and the static sites (`/mind`, `/fam`, `/scan`, `/aysynbm`).
  - **Label format:**
    ```yaml
    labels:
      caddy: radarr.vrg.rocks
      caddy.reverse_proxy: "{{upstreams 7878}}"
      caddy.import: authentik
    ```
  - **Profiles fit:** Standby services carry their own labels, so their routes appear only while they run. That removes the commented vhost blocks.
  - **Retirement:** Once active, retire `ports.json`.
