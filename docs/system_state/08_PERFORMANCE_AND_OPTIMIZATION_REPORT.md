# 08. Sol Server Performance, Resilience & Optimization Master Report

> **Target Architecture:** Apple Silicon M1 Pro (8 Cores: 6P + 2E) | 16 GB Unified Memory | macOS Sequoia (OrbStack / Docker Engine)  
> **Host Path:** `/Users/vrg/Documents/Sol`  
> **Scope:** Analysis and implementation blueprint for Action Item 1 in `TODO.md`.  
> **Original Audit Date:** August 2026 (memory and CPU measurements below are from that audit)  
> **Implementation Status Sync:** 2026-10-17 (verified against `compose/*.yml`, `Caddyfile`, `scripts/*`)  

---

## 1. Executive Summary: The Performance Profile

The Sol server runs in a lean state:
* **Container Topology:** `24` active containers by default, `26` standby/ops containers held under Docker Compose V2 `profiles: ["standby"]` / `profiles: ["ops"]` (zero RAM and CPU until started), plus the native macOS `jellyfin-metal` process on port `8097`.
* **Memory Footprint (Aug 2026):** The active containers consumed **~2.8 GB RAM** out of the 7.8 GB allocated to the OrbStack VM, leaving >13 GB of unified memory for macOS and cache buffers.
* **CPU Idle Profile (Aug 2026):** Baseline CPU usage across all containers hovered at **~1-3%**, with brief spikes during media indexing and OCR.

```
+-----------------------------------------------------------------------------------------+
|                              M1 PRO HARDWARE PROFILE (16 GB)                            |
+-----------------------------------------------------------------------------------------+
| [ Core System / macOS ]  [ OrbStack VM (7.8 GB Cap) ]           [ Dynamic Buffers ]    |
|   ~4.5 GB Memory           ~2.8 GB Active Containers (24 Active)  ~8.7 GB File Cache/IO |
|   + Jellyfin Metal (native, outside VM cap)                                             |
+-----------------------------------------------------------------------------------------+
```

To lift this stack to peak performance and remove friction points (such as the OrbStack removable drive disconnect), this report covers optimizations across 6 pillars. Each item carries its implementation status as of 2026-10-17.

### Implementation Status Overview

| Pillar | Item | Status | Ground Truth |
| :--- | :--- | :--- | :--- |
| 1 | External drive resiliency (TCC, sleep, watcher) | Open | No `scripts/check_mounts.sh` or `scripts/watch_external.sh` in repo |
| 2 | Paperless worker tuning | **Done** | `PAPERLESS_TASK_WORKERS: 2`, `PAPERLESS_THREADS_PER_WORKER: 2` in `compose/paperless.yml` |
| 2 | Authentik worker tuning | **Done** | `AUTHENTIK_WEB__WORKERS: 2` in `compose/core.yml` |
| 2 | Authentik worker privilege reduction | **Done** | No `user: root`, no `/var/run/docker.sock` on `authentik-worker` |
| 2 | Arcane log volume | **Done** | `LOG_LEVEL: info` (was `debug`) |
| 3 | PostgreSQL buffer tuning | **Done** | `shared_buffers=256MB` and related flags on `authentik-postgresql` and `paperless-db` |
| 3 | Paperless broker image | **Done** | `redis:8-alpine` |
| 3 | Paperless DB image | Retained | Debian `postgres:17` (`glibc`) to avoid collation mismatch. Alpine move is an optional local trial. |
| 3 | SQLite backup consistency | **Done** | `sqlite3 .backup` snapshots in `scripts/backup.sh`, `**/*-wal` and `**/*-shm` excluded from rclone |
| 3 | SQLite runtime pragmas for Servarr | Open | Application-managed, not set by compose |
| 4 | Unified `/data/torrents` hardlink path | Staged | `qbittorrent` and `cross-seed` mount both `/downloads` and `/data` |
| 5 | Container DNS overrides | **Done** | `1.1.1.1` / `9.9.9.9` on media and download services, `8.8.8.8` / `1.1.1.1` on Seerr |
| 5 | Caddy streaming transport | **Done** | Inline on `watch.vrg.rocks` / `jellyfin.vrg.rocks` and `metal.vrg.rocks` |
| 5 | Cloudflare solver | **Done** | `byparr` active on `8191` with alias `flaresolverr` |
| 6 | Recyclarr TRaSH sync | Declared | `recyclarr` under `profiles: ["standby"]`, not started |
| 6 | Jellyfin throttling | Partial | Set on Jellyfin Metal by `setup_jellyfin_metal.py --reset`. Container `encoding.xml` unverified. |

---

## 2. Pillar 1: OrbStack & External Drive Resiliency (Preventing USB Dropouts)

### The Underlying Issue
On macOS, external USB drives (like `PANOPTICON`) formatted as ExFAT or APFS mount under `/Volumes/`. When macOS sleeps, unmounts and remounts the drive, or switches mount points, **OrbStack's background VirtioFS bridge holds onto a stale inode handle**. Containers then receive `ENOENT (No such file or directory)` until OrbStack restarts.

Active services that mount `${EXTERNAL_DRIVE_00}` (`/Volumes/PANOPTICON`): `jellyfin`, `radarr`, `sonarr`, `bazarr`, `lidarr`, `qbittorrent`, `cross-seed`, `copyparty`. Native `jellyfin-metal` reads `/Volumes/PANOPTICON` directly and does not go through VirtioFS.

### Prevention Strategies

#### Strategy A: Ensure Full Disk Access & Removable Volumes Permission
1. Open macOS **System Settings → Privacy & Security → Files and Folders → OrbStack**.
2. Ensure **Removable Volumes** is checked `ON`.
3. Go to **System Settings → Privacy & Security → Full Disk Access** and grant OrbStack full access, so the macOS TCC security subsystem does not drop file descriptors on wake.

#### Strategy B: Prevent External Drive Sleep in macOS
Prevent macOS from putting external hard drives to sleep during server operations:
* In macOS **System Settings → Displays → Advanced** or **Energy Saver**, set:
  - *"Prevent automatic sleeping when the display is off"* ➔ **Turn ON**.
  - *"Put hard disks to sleep when possible"* ➔ **Turn OFF**.

#### Strategy C: Automated Mount-Health Recovery Watcher (Zero-Touch Script)
Create a lightweight macOS LaunchAgent or healthcheck script (proposed path `scripts/check_mounts.sh`, not yet in the repo) that detects lost container access to `/Volumes/PANOPTICON` and restarts the affected containers:
```bash
#!/bin/bash
# scripts/check_mounts.sh (proposed)
if [ -d "/Volumes/PANOPTICON" ]; then
  # Test if container can read the mount
  if ! docker exec radarr test -d /external/Movies 2>/dev/null; then
    echo "$(date): Remount detected out of sync. Restarting media containers..."
    cd /Users/vrg/Documents/Sol && docker compose restart jellyfin radarr sonarr bazarr lidarr qbittorrent cross-seed copyparty
  fi
fi
```

> [!NOTE]
> The earlier draft ran `docker compose -f compose/media.yml restart`. Under the `include:` model that targets only one sub-file and misses `qbittorrent`, `cross-seed`, and `copyparty`. Run it from the project root with explicit service names instead.

---

## 3. Pillar 2: Apple Silicon M1 Pro Resource & Concurrency Tuning

### 1. Paperless-ngx OCR & Worker Tuning (Done)
* **Previous State:** Default single-threaded OCR consumption.
* **Implemented in `compose/paperless.yml`:**
  ```yaml
  PAPERLESS_TASK_WORKERS: 2           # Background Celery queue workers
  PAPERLESS_THREADS_PER_WORKER: 2     # 2 threads per worker on M1 Pro Performance cores
  PAPERLESS_DBNAME: ${PAPERLESS_DB_NAME:-paperless}
  PAPERLESS_DBUSER: ${PAPERLESS_DB_USER:-paperless}
  PAPERLESS_DBPASS: ${PAPERLESS_DB_PASS:-paperless}
  ```
* **Variable Correction:** The earlier draft proposed `PAPERLESS_WORKER_CONCURRENCY`, `PAPERLESS_OCR_THREADS`, and `PAPERLESS_OCR_USER_ARGS`. None of those are set. The stack uses the upstream `PAPERLESS_TASK_WORKERS` and `PAPERLESS_THREADS_PER_WORKER` pair.
* *Projected Impact (Aug 2026 estimate, not re-measured):* Document ingestion time drops by **65%** during bulk scanning while leaving 4 Performance cores free for media and web requests.

### 2. Authentik Worker Allocation (Done)
* **Previous State:** Default auto-concurrency.
* **Implemented in `compose/core.yml`:**
  ```yaml
  AUTHENTIK_WEB__WORKERS: 2           # 2 Gunicorn web workers (upstream nested env var)
  ```
* **Variable Correction:** The earlier draft proposed `AUTHENTIK_WORKERS: 2`. The implemented key is the nested `AUTHENTIK_WEB__WORKERS`.
* **Related Hardening:** `authentik-server` host ports bind to `127.0.0.1` only. `authentik-worker` drops `user: root` and the Docker socket. Both keep `shm_size: 512mb`.

### 3. Log Volume Reduction (Done)
* `arcane` runs `LOG_LEVEL: info` instead of `debug`, which cuts container log I/O.
* Caddy global log runs at `level INFO` with `format console` to stdout.

---

## 4. Pillar 3: Database Engine Tuning (SQLite WAL & PostgreSQL)

### 1. SQLite Pragmas for Servarr & Jellyfin (`radarr`, `sonarr`, `prowlarr`, `bazarr`) (Open)
SQLite databases on Apple Silicon NVMe SSDs perform best in WAL (Write-Ahead Logging) mode.
* **Tuning Parameters:**
  - `PRAGMA journal_mode = WAL` (Allows reads during writes).
  - `PRAGMA synchronous = NORMAL` (Reduces disk sync calls by an estimated 70% with no corruption risk in WAL mode).
  - `PRAGMA cache_size = -64000` (Allocates 64MB RAM cache for fast search indexing).
  - `PRAGMA busy_timeout = 5000` (Removes `database is locked` errors during heavy RSS syncs).
* **Arcane (Done):** `DATABASE_URL: file:data/arcane.db?_pragma=journal_mode(WAL)&_pragma=busy_timeout(2500)&_txlock=immediate`.
* **Backup Consistency (Done):** WAL mode creates live `-wal` and `-shm` sidecar files. `scripts/backup.sh` now snapshots every `*.db`, `*.sqlite`, and `*.sqlite3` under `./config`, `./data/arcane`, and `./data/ignis` (depth 4) with `sqlite3 ".timeout 5000" ".backup ..."` into `data/backups/sqlite/`. The rclone filter excludes `**/*-wal` and `**/*-shm`, so the cloud copy never holds a torn WAL pair.

### 2. PostgreSQL 16 & 17 Tuning (`authentik-postgresql` & `paperless-db`) (Done)
* **Previous State:** Default PostgreSQL parameters (sized for 512MB RAM servers).
* **Implemented on both services:**
  ```yaml
  command:
    - "postgres"
    - "-c"
    - "shared_buffers=256MB"
    - "-c"
    - "work_mem=16MB"
    - "-c"
    - "effective_cache_size=1GB"
    - "-c"
    - "maintenance_work_mem=64MB"
    - "-c"
    - "wal_buffers=16MB"
    - "-c"
    - "checkpoint_completion_target=0.9"
  ```
  *Projected Impact (Aug 2026 estimate):* Faster Authentik flow lookups and Paperless full-text SQL searches, estimated at **3x**.

### 3. Image Selection
| Service | Image | Rationale |
| :--- | :--- | :--- |
| `authentik-postgresql` | `postgres:16-alpine` | Unchanged |
| `paperless-db` | `postgres:17` (Debian, `glibc`) | Keeps collation compatibility with the existing `data/paperless/db` cluster. Alpine (`musl`) requires `pg_dump` / `pg_restore` and is documented as an optional local trial. |
| `paperless-broker` | `redis:8-alpine` | Smaller image, stateless queue (excluded from backup) |

### 4. Backup & Restore Path
* `scripts/backup.sh` writes `pg_dump | gzip` to `.sql.gz.tmp`, then renames, so a failed dump never replaces a good one.
* `scripts/restore.sh --restore-dbs` imports with `gunzip -c ... | docker exec -i <container> psql`.

---

## 5. Pillar 4: Storage Logistics & Hardlink Mechanics

### 1. Internal SSD vs External Drive Dynamics
* **Internal Drive (`${DOCKER_DATA_DIR}` on NVMe SSD):**
  - Unified root `/data` enables **APFS atomic hardlinks** between `/data/torrents` and `/data/media`.
  - Downloads move in **0.001 seconds** with **0 bytes duplicate storage** used.
* **External Drive (`PANOPTICON` on ExFAT):**
  - **ExFAT does not support hardlinks**.
  - When Radarr/Sonarr import directly to `/external/Movies`, they must perform a **full file copy** (requiring 2x disk space during seeding) or a move.
  - **Optimal Strategy:**
    1. Direct all active, incoming torrents to `/data/torrents` (Internal SSD).
    2. Import to `/data/media/movies` (Internal SSD) through zero-copy hardlinks.
    3. For long-term cold storage, move completed seasons or movies to `/external/Movies` when SSD space is needed.

### 2. Dual Mount Staging (Staged)
* `qbittorrent` and `cross-seed` now mount `${DOCKER_DATA_DIR}/torrents:/downloads` **and** `${DOCKER_DATA_DIR}:/data`.
* Both paths reach the same inodes, so save paths can move to `/data/torrents/...` with no copy and no downtime.
* After migration, qBittorrent and the *arr apps see one identical path, so Radarr no longer needs its `/downloads/movies` -> `/data/torrents/movies/` remote path mapping.
* Verify with `scripts/test_cross_seed.sh`, which runs as `-u "${PUID:-501}:${PGID:-20}"` and tests the `/data/torrents` <-> `/data/media` hardlink.

---

## 6. Pillar 5: Network, DNS & Ingress Fine-Tuning

### 1. Upstream DNS Resolvers for Servarr Containers (Done)
* **Previous State:** Containers inherited the default Docker/OrbStack virtual bridge DNS resolver (`192.168.x.x` or ISP DNS).
* **Deficiency:** Public trackers and Russian indexers (for example `RuTracker.org`) often suffer DNS poisoning or throttling by consumer ISPs.
* **Implemented:**
  ```yaml
  dns:
    - 1.1.1.1       # Cloudflare Fast DNS
    - 9.9.9.9       # Quad9 Security DNS
  ```
  Applied to `radarr`, `sonarr`, `bazarr`, `lidarr`, `prowlarr`, `byparr`, `flaresolverr` (standby), `qbittorrent`, and `cross-seed`. `seerr` uses `8.8.8.8` and `1.1.1.1`.
  *Impact:* Resolves connection timeouts and improves indexer scrape speed.

### 2. Caddy Transport & Streaming Buffer Tuning (Done)
* The proposed `(streaming_transport)` snippet is implemented inline (not as a snippet) inside the `reverse_proxy` blocks for `watch.vrg.rocks, jellyfin.vrg.rocks` (`http://jellyfin:8096`) and `metal.vrg.rocks` (`http://host.docker.internal:8097`):
  ```caddy
  reverse_proxy http://jellyfin:8096 {
      transport http {
          read_buffer 32768
          write_buffer 32768
          keepalive 120s
      }
  }
  ```
* Both streaming vhosts skip `import optimize`, so Caddy does not spend CPU compressing video.

### 3. Cloudflare Challenge Solver (Done)
* `byparr` replaces `flaresolverr` as the active solver on port `8191`, with network alias `flaresolverr`. Prowlarr's `http://flaresolverr:8191` setting is unchanged.
* `flaresolverr` remains under `profiles: ["standby"]` as a fallback and costs no resources while stopped.

---

## 7. Pillar 6: Media Automation & Playback Optimization

### 1. Recyclarr TRaSH Guides Automation (Declared, Not Started)
* `recyclarr` is declared in `compose/media.yml` under `profiles: ["standby"]` with `CRON_SCHEDULE: "@daily"` and `user: "${PUID}:${PGID}"`. Start it with `docker compose --profile standby up -d recyclarr` after writing its config:
  - **Radarr:** `UHD Bluray + WEB` profile with Dolby Vision fallback, HDR10+, lossless audio preferences, and low-bitrate filter rules.
  - **Sonarr:** `WEB-1080p` / `WEB-2160p` with release group scoring.

### 2. Jellyfin Playback CPU Protection (Partial)
* **Jellyfin Metal:** `scripts/setup_jellyfin_metal.py --reset` sets `HardwareAccelerationType: videotoolbox`, `EnableThrottling: true`, and `ThrottleDelaySeconds: 120`. Transcodes run on the M1 Pro media engine instead of CPU cores.
* **Jellyfin Container:** In `config/jellyfin/encoding.xml`:
  - Set `<EnableThrottling>true</EnableThrottling>` and `<ThrottleDelaySeconds>120</ThrottleDelaySeconds>`.
  - Prevents remote 4K software transcodes from pegging the 8-core M1 Pro at 100% CPU. Not verified since the August audit.

---

## 8. Prioritized Implementation Roadmap

| Priority | Action Item | Target Component | Complexity | Expected Benefit | Status (2026-10-17) |
| :---: | :--- | :--- | :---: | :--- | :--- |
| **P1** | Add Container DNS (`1.1.1.1`, `9.9.9.9`) | `compose/media.yml`, `compose/download.yml` | Low | Fixes RuTracker & indexer scrape timeouts immediately. | **Done** |
| **P1** | Enable Jellyfin Transcode Throttling | `config/jellyfin/encoding.xml`, `scripts/setup_jellyfin_metal.py` | Low | Prevents CPU exhaustion during media playback. | **Partial** (Metal done, container unverified) |
| **P1** | Replace FlareSolverr with Byparr | `compose/media.yml`, `Caddyfile` | Low | Solves Cloudflare Turnstile challenges for Prowlarr. | **Done** |
| **P1** | Crash-consistent backups | `scripts/backup.sh`, `config/rclone/filter.txt.example` | Medium | No torn PostgreSQL or SQLite WAL state in the cloud. Point-in-time archive. | **Done** |
| **P2** | Tune Paperless OCR Workers (2T / 2W) | `compose/paperless.yml` | Low | Estimated **65% faster** document processing on M1 Pro. | **Done** |
| **P2** | Tune PostgreSQL Buffers (256MB) | `compose/core.yml`, `compose/paperless.yml` | Medium | Faster Authentik SSO and full-text document searches. | **Done** |
| **P2** | Tune Authentik Web Workers | `compose/core.yml` | Low | Bounded Gunicorn concurrency on 16 GB host. | **Done** |
| **P2** | Setup Automated Recyclarr TRaSH Sync | `compose/media.yml` | Medium | Fetches top-tier media and blocks bad releases. | **Declared** (standby profile) |
| **P2** | Complete `/data/torrents` migration | qBittorrent, Cross-Seed, Radarr settings | Medium | One path namespace, no remote path mappings. | **Staged** |
| **P3** | Setup External Mount Health Watcher | `scripts/check_mounts.sh` (proposed) | Low | Heals detached USB mounts on macOS wake. | Open |
| **P3** | Servarr SQLite runtime pragmas | Radarr, Sonarr, Prowlarr, Bazarr | Medium | Fewer `database is locked` errors. | Open |
