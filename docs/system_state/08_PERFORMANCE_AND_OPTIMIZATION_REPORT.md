# 08. Sol Server Performance, Resilience & Optimization Master Report

> **Target Architecture:** Apple Silicon M1 Pro (`dash.vrg.rocks`, 8 Cores: 6P + 2E) | 16 GB Unified Memory | macOS Sequoia (OrbStack / Docker Engine)  
> **Host Path:** `/Users/vrg/Documents/Sol`  
> **Last Synced to Ground Truth:** 2026-10-20 (Post-Phase-2 31-Agent Swarm Audit & Full-Stack Hardening)  

---

## 1. Executive Summary: Live Telemetry & Resource Profile (2026-10-20)

Following the October 2026 architectural overhaul and the October 20, 2026 31-agent swarm audit, Sol runs **29 active containers (`29/29` `(healthy)`)** and **10 static web applications** in **`1.63 GiB` (`1,664.4 MiB`) of total container RAM**—a **42% memory reduction** compared to the August 2026 24-container baseline (`~2.8 GiB`), while expanding the active platform by 5 containers and 6 static web apps:

```text
+-------------------------------------------------------------------------------------------------+
|                            M1 PRO UNIFIED MEMORY PROFILE (16.0 GiB)                             |
+-------------------------------------------------------------------------------------------------+
| [ macOS Kernel & Desktop ]   [ OrbStack VM: 29 Active Containers ]   [ Unified Page Cache / IO ]|
|       ~4.2 GiB RAM                ~1.63 GiB RAM (20.8% of VM Cap)          ~10.1 GiB Free/Cache |
|                                   + 10 Zero-RAM Static Web Apps                                 |
+-------------------------------------------------------------------------------------------------+
```

### Live Container Telemetry (`docker stats --no-stream`, 2026-10-20)

| Container | Domain Stack | Health Status | CPU % | Memory Usage | % of 7.82 GiB VM | PIDs | Key Optimization Applied |
| :--- | :--- | :---: | ---: | ---: | ---: | ---: | :--- |
| **`lldap`** | `core.yml` | `healthy` | `0.04%` | **`600 KiB`** | `0.01%` | 5 | Rust LDAP directory replacing Authentik user store |
| **`paperless-broker`** | `paperless.yml` | `healthy` | `2.25%` | **`5.98 MiB`** | `0.07%` | 6 | `redis:8-alpine` with `--maxmemory 256mb --maxmemory-policy volatile-lru` |
| **`glance`** | `monitoring.yml` | `healthy` | `0.00%` | **`7.23 MiB`** | `0.09%` | 7 | Go single-binary homepage + `/api/healthz` probe |
| **`tinyauth`** | `core.yml` | `healthy` | `0.00%` | **`8.98 MiB`** | `0.11%` | 13 | Go forward-auth + 7 OIDC clients (replaces `~900 MiB` Authentik) |
| **`backrest`** | `utilities.yml` | `healthy` | `0.00%` | **`9.77 MiB`** | `0.12%` | 20 | Go Restic scheduler + WebUI |
| **`pocketbase`** | `coding.yml` | `healthy` | `0.00%` | **`9.78 MiB`** | `0.12%` | 13 | Go + SQLite backend (`logs.minLevel=4` stops `/api/health` WAL churn) |
| **`ignis`** | `knowledge.yml` | `healthy` | `0.00%` | **`10.86 MiB`** | `0.14%` | 11 | Express vault sync server + `/api/version` healthcheck |
| **`enclosed`** | `utilities.yml` | `healthy` | `0.06%` | **`11.09 MiB`** | `0.14%` | 11 | Hono encrypted notes server |
| **`ntfy`** | `utilities.yml` | `healthy` | `0.06%` | **`13.16 MiB`** | `0.16%` | 11 | Go pub/sub server + SQLite `WAL` startup pragmas |
| **`homebox`** | `utilities.yml` | `healthy` | `0.09%` | **`14.09 MiB`** | `0.18%` | 13 | Go inventory server (`v0.26.2`) |
| **`code-server`** | `coding.yml` | `healthy` | `0.00%` | **`16.26 MiB`** | `0.20%` | 32 | Idle browser VS Code server + `/healthz` check |
| **`airtrail`** | `utilities.yml` | `healthy` | `0.00%` | **`18.20 MiB`** | `0.23%` | 11 | SvelteKit flight log sharing `paperless-db` (zero extra DB container) |
| **`readeck`** | `knowledge.yml` | `healthy` | `0.00%` | **`22.94 MiB`** | `0.29%` | 11 | Go bookmark/article archiver + native OIDC |
| **`paperless-db`** | `paperless.yml` | `healthy` | `0.30%` | **`24.22 MiB`** | `0.30%` | 8 | Migrated to `postgres:17-alpine` (`musl`), hosts `paperless` + `airtrail` |
| **`qbittorrent`** | `download.yml` | `healthy` | `2.10%` | **`31.42 MiB`** | `0.39%` | 19 | `150` active torrents across `/data` and `/external` |
| **`caddy`** | `core.yml` | `healthy` | `0.00%` | **`31.61 MiB`** | `0.39%` | 24 | Serves 33 vhosts + 10 static web apps (`0 MiB` extra container RAM) |
| **`qui`** | `download.yml` | `healthy` | `0.90%` | **`34.34 MiB`** | `0.43%` | 13 | Go web UI + 30m cross-seed + 10 FUP rules (replaces Node `cross-seed`) |
| **`byparr`** | `media.yml` | `healthy` | `0.26%` | **`35.39 MiB`** | `0.44%` | 7 | `/openapi.json` healthcheck + `/tmp` `tmpfs` + `BLOCK_MEDIA=true` |
| **`arcane`** | `core.yml` | `healthy` | `0.53%` | **`64.84 MiB`** | `0.81%` | 29 | Distroless Go Docker manager + SQLite `WAL` |
| **`seerr`** | `media.yml` | `healthy` | `0.00%` | **`67.22 MiB`** | `0.84%` | 31 | Clean Jellyfin sync (0 TMDb errors) |
| **`coder`** | `coding.yml` | `healthy` | `1.56%` | **`70.91 MiB`** | `0.89%` | 24 | `CODER_CLUSTER_HOST=127.0.0.1` (embedded NATS) + `group_add: ["0"]` |
| **`bazarr`** | `media.yml` | `healthy` | `0.35%` | **`71.70 MiB`** | `0.90%` | 128 | 4 active subtitle providers, `profileId=1` across all media |
| **`copyparty`** | `utilities.yml` | `healthy` | `0.20%` | **`86.80 MiB`** | `1.08%` | 30 | `noidx` excludes `.Spotlight-V100`, `._*`, and Restic `backups` |
| **`lidarr`** | `media.yml` | `healthy` | `0.12%` | **`109.70 MiB`** | `1.37%` | 27 | `LogLevel=info`, `/ping` healthcheck |
| **`sonarr`** | `media.yml` | `healthy` | `0.31%` | **`116.60 MiB`** | `1.46%` | 27 | `LogLevel=info`, 1,379 relative symlinks |
| **`prowlarr`** | `media.yml` | `healthy` | `1.36%` | **`138.90 MiB`** | `1.74%` | 26 | `LogLevel=info`, `LimeTorrents` disabled, `90s` Byparr timeout |
| **`radarr`** | `media.yml` | `healthy` | `1.29%` | **`143.30 MiB`** | `1.79%` | 24 | `LogLevel=info`, 38 relative symlinks + 1 APFS hardlink |
| **`paperless-webserver`** | `paperless.yml` | `healthy` | `0.60%` | **`151.80 MiB`** | `1.90%` | 24 | `2` Celery workers × `2` threads, `eng+hin+kan+pan` OCR |
| **`jellyfin`** | `media.yml` | `healthy` | `0.10%` | **`336.80 MiB`** | `4.21%` | 36 | `2 GiB` `/tmp/jellyfin` `tmpfs` (`uid=501:20`) + `Optimistic` SQLite lock |
| **Total (`29` Active)** | **8 Stacks** | **`29/29` Healthy** | **`~10%` Idle** | **`1,664.4 MiB` (`1.63 GiB`)** | **`20.8%`** | **631** | **15 `standby` + 1 `ops` containers consume `0 B` RAM** |

---

## 2. Six-Pillar Optimization Status Matrix (All Complete)

| Pillar | Optimization Item | Status | Verified Implementation (2026-10-20) |
| :--- | :--- | :---: | :--- |
| **1. Storage & TCC Resilience** | Eliminate macOS TCC `Exit 126` & removable volume hangs | **Done** | `com.vrg.sol.db-stage.plist` invokes `/opt/homebrew/bin/python3` without `WorkingDirectory` in `~/Documents`; `stage_db_backups.sh` scans `/Volumes/PANOPTICON` via OrbStack `redis:8-alpine` (`~12s`, zero TCC prompts). |
| **1. Storage & TCC Resilience** | Eliminate SSD write amplification (`byparr`, `jellyfin`, `pocketbase`) | **Done** | `byparr` `/openapi.json` healthcheck + `/tmp` `tmpfs` saves **~65 GB/day** SSD reads & **~4 GB/day** writes; `jellyfin` mounts `2 GiB` `/tmp/jellyfin` `tmpfs` (`uid=501:20`); `pocketbase` `logs.minLevel=4` eliminates **4,320/day** `/api/health` SQLite writes. |
| **2. Identity & Concurrency** | Replace Authentik with Tinyauth v5 + LLDAP + `<50ms` Sync | **Done** | Saved `~885 MiB` RAM; `scripts/identity_sync.py` queries `users.db?immutable=1` directly and exits in **`45.5 ms`** via SHA-256 digest when unchanged (eliminating the `WatchPaths` JWT write loop). |
| **2. Identity & Concurrency** | Paperless M1 Pro concurrency & Redis memory bounds | **Done** | `PAPERLESS_TASK_WORKERS: 2`, `PAPERLESS_THREADS_PER_WORKER: 2`, `PAPERLESS_OCR_LANGUAGE: eng+hin+kan+pan`, and `paperless-broker` capped at `--maxmemory 256mb --maxmemory-policy volatile-lru`. |
| **3. Database Engine Tuning** | Migrate `paperless-db` to `postgres:17-alpine` + share with `airtrail` | **Done** | `paperless-db` runs `postgres:17-alpine` (`24.2 MiB` RAM) with `shared_buffers=256MB`, `effective_cache_size=1GB`, `work_mem=16MB`, serving both `paperless` and `airtrail`. |
| **3. Database Engine Tuning** | SQLite locking & WAL pragmas (`jellyfin`, `ntfy`, `arcane`, `stage_db_backups.sh`) | **Done** | `jellyfin` `database.xml` set to `Optimistic`; `ntfy` `server.yml` runs `WAL` + `busy_timeout=5000`; `stage_db_backups.sh` converts all 29 staged SQLite backups to `journal_mode=DELETE` with zero `-wal`/`-shm` sidecars. |
| **4. Zero-Copy Media Logistics** | Unified `/data` + `/external` & ExFAT relative symlink pipeline | **Done** | Legacy `/downloads` mount retired across all containers; `torrent_finished.py` + `arr_symlink_dedupe.sh` maintain `1,417` zero-copy relative symlinks on `/Volumes/PANOPTICON` (`0` broken symlinks). |
| **5. Network, DNS & Ingress** | Container DNS overrides, HTTP/3 streaming buffers & edge ACLs | **Done** | `1.1.1.1`/`9.9.9.9` on all media/download containers; `32 KiB` streaming buffers on Jellyfin; 17 admin-locked `TINYAUTH_APPS_*` domains; `route` block in `(static_site)` preventing unauthenticated path probing. |
| **6. Healthchecks & Automation** | 100% Docker `healthcheck` coverage & QUI native FUP engine | **Done** | All **29/29** active containers have verified Docker healthchecks; `qui` enforces 25 tracker tags and 10 FUP upload/ratio rules across all `150` torrents; Servarr `LogLevel` set to `info` (~300 MB debug logs purged). |

---

## 3. High-Impact I/O & Longevity Optimizations Detail

### 3.1 Eliminating `byparr` 65 GB/Day Idle SSD Churn (`compose/media.yml`)
* **Root Cause Discovered in Audit:** Upstream `ghcr.io/thephaseless/byparr:latest` (`v3.0.4`) ships with a Dockerfile `HEALTHCHECK` hitting `GET /health` every 15 minutes. In `src/endpoints.py`, `/health` launches `Xvfb :99` and 7 patched Firefox (`675 MB`) processes, writes a fresh ~40 MB profile to `/tmp` on the APFS SSD, and fetches `https://google.com`—accumulating **`36.1 GB` Block Reads and `2.12 GB` Block Writes in 13 hours** on an idle server.
* **Implemented Fix:**
  - Overrode `healthcheck` in `compose/media.yml` to probe `curl -fsS http://127.0.0.1:8191/openapi.json >/dev/null || exit 1` (`60s` interval, zero browser launches).
  - Mounted `tmpfs: ["/tmp:size=512m,exec,mode=1777"]` and `shm_size: 1gb` so real Prowlarr Turnstile solves write ephemeral Firefox profiles exclusively to RAM.
  - Enabled `BLOCK_MEDIA: "true"` to abort image, font, and media downloads during challenge solving.

### 3.2 Eliminating `jellyfin` `/tmp/jellyfin` Permission Exceptions & SQLite 500s (`compose/media.yml`)
* **Root Cause Discovered in Audit:** `compose/media.yml` previously mounted `/tmp/jellyfin:size=512m` with default `root:root` (`0755`) ownership, causing `uid=501(abc)` inside `jellyfin` to fail with `System.UnauthorizedAccessException: Access to the path '/tmp/jellyfin/...' is denied` during `TrickplayManager` and `Dynamic Image Provider` runs. Meanwhile, `<LockingBehavior>NoLock</LockingBehavior>` in `database.xml` caused `SQLite Error 5` HTTP 500s on concurrent `GET /Items` requests.
* **Implemented Fix:**
  - Updated `tmpfs` to `/tmp/jellyfin:size=2g,uid=501,gid=20,mode=0755` (verified `abc:dialout (501:20) 755` inside the container).
  - Updated `config/jellyfin/database.xml` to `<LockingBehavior>Optimistic</LockingBehavior>`.

### 3.3 Eliminating `lldap` `WatchPaths` Self-Triggering Loop (`scripts/identity_sync.py`)
* **Root Cause Discovered in Audit:** `com.vrg.sol.identity-sync.plist` watches `/Users/vrg/Documents/Sol/data/lldap` (`WatchPaths`). Previously, `identity_sync.py` authenticated to LLDAP via `POST /auth/simple/login`, which inserted a new JWT session row into `data/lldap/users.db` on every run—modifying the watched directory and re-triggering `launchd` in a recurring loop (accumulating 59 headless `admin` sessions in `jwt_storage`).
* **Implemented Fix:**
  - `scripts/identity_sync.py` now reads `file:/Users/vrg/Documents/Sol/data/lldap/users.db?immutable=1` directly via `sqlite3`, computes a SHA-256 digest of LLDAP users/groups/attributes + `.env` `mtime`, and exits `0` in **`45.5 ms`** with zero disk writes whenever state is unchanged.

### 3.4 Eliminating `pocketbase` `/api/health` WAL Write Amplification (`data/pocketbase/`)
* **Root Cause Discovered in Audit:** PocketBase's default `logs.minLevel = 0` (`INFO`) logged every 30-second Docker healthcheck and 60-second Glance monitor probe (`4,320` rows/day) into `auxiliary.db`, growing `auxiliary.db-wal` to `4.13 MB` (`1.73 GB` Block I/O reads) and staging `auxiliary.db` into Restic backups.
* **Implemented Fix:**
  - Set `logs.minLevel = 4` (`WARN`) in `data/pocketbase/data.db` (`_params`), purged `2,534` `/api/health` rows in `auxiliary.db` + `PRAGMA wal_checkpoint(TRUNCATE)`, and excluded `auxiliary.db*` in `scripts/stage_db_backups.sh` and `config/backrest/excludes.txt`.
