# 05. System Refactoring & Modular Architecture Migration Plan

> **Host Context:** Apple Silicon M1 Pro macOS (Single-Node Host running OrbStack / Docker)  
> **Workspace Root:** `/Users/vrg/Documents/Sol`  
> **Refactoring Date:** August 2026 (Phase 1 modularization), October 2026 (Phase 2 profiles, hardening & backup integrity)  
> **Safety Guarantee:** Non-destructive migration with dedicated pre-refactor backup at `_backup_pre_refactor/`.  
> **Last Synced to Ground Truth:** 2026-10-17  

---

## 1. Executive Summary & Goals

This document records the architectural refactoring of the **Sol** home server. Phase 1 removed technical debt, split a monolithic 922-line compose file into single-responsibility domain stacks, centralized secrets, and cleaned up root directory clutter for an Apple Silicon M1 Pro macOS host. Phase 2 replaced commented-out YAML with Compose profiles, hardened edge authentication, and made backups crash-consistent.

### Phase 1 Milestones (August 2026)
1. **Docker Compose V2 `include:` Architecture:** Replaced the monolithic `docker-compose.yml` with 8 modular domain files under `compose/`.
2. **Zero-Friction Container DNS:** Retained 100% container-to-container name resolution (`http://radarr:7878`, `http://authentik-server:9000`, `http://glance:8080`, `http://caddy`) across the unified `sol_default` project bridge network without external network workarounds.
3. **Dedicated Paperless Stack:** Extracted `paperless-webserver`, `paperless-broker`, `paperless-db`, and AI/OCR helpers into a dedicated compose file (`compose/paperless.yml`).
4. **Environment & Secrets Hygiene:** Segregated `.env` and `.env.example` into prefixed, app-specific sections and moved inline hardcoded secrets (`arcane` encryption keys) out of YAML.
5. **Zero-Leak Environment Mapping:** Replaced blanket `env_file:` dumps with explicit container-level `environment:` blocks, so no service sees unrelated secrets.
6. **Retired Redundant Files:** Archived `paperless.env`, `bitwarden.env`, and legacy compose files into `docs/archive/`.
7. **Static Web & Script Separation:** Grouped static frontends into `web/` (`web/fam`, `web/scan`, `web/aysynbm`) and automation tasks into `scripts/` (`scripts/backup.sh`, `scripts/restore.sh`, `scripts/setup_jellyfin_metal.py`, `scripts/test_cross_seed.sh`).
8. **Master Port Registry Update:** Refreshed `ports.json` with active, standby, and legacy service allocations, internal ports, host ports, protocols, and FQDNs.

### Phase 2 Milestones (October 2026)
1. **Compose Profiles Replace Commented YAML:** 26 standby/ops containers now carry `profiles: ["standby"]` (or `profiles: ["ops", "standby"]` for `rclone`). `docker compose up -d` starts the 24 active containers. `docker compose --profile standby up -d <service>` starts one standby service.
2. **Caddy Standby Vhosts Commented:** 18 standby vhosts are commented out until their `--profile standby` container starts. 27 site blocks stay active.
3. **Byparr Replaces FlareSolverr:** `byparr` (`ghcr.io/thephaseless/byparr:latest`, port `8191`, network alias `flaresolverr`) is the active Cloudflare Turnstile solver. `flaresolverr` is preserved under `profiles: ["standby"]`.
4. **Edge Auth Hardening:** `dash.vrg.rocks`, `code.vrg.rocks`, `router.vrg.rocks`, `byparr.vrg.rocks`, and `flaresolverr.vrg.rocks` enforce `import authentik`. `qb.vrg.rocks` keeps qBittorrent Native Auth for the Android client. `metal.vrg.rocks` routes native Jellyfin Metal.
5. **Homebox to Standby:** Moved to `profiles: ["standby"]` pending local SQLite database repair. CORS restricted to `Origin https://scan.vrg.rocks`.
6. **Authentik Hardening:** `authentik-server` binds `127.0.0.1:9000` and `127.0.0.1:9443` and sets `AUTHENTIK_WEB__WORKERS: 2`. `authentik-worker` runs without `user: root` and without `/var/run/docker.sock`.
7. **Paperless Tuning:** `paperless-webserver` passes `PAPERLESS_DBNAME`, `PAPERLESS_DBUSER`, `PAPERLESS_DBPASS`, `PAPERLESS_TASK_WORKERS: 2`, `PAPERLESS_THREADS_PER_WORKER: 2`. `paperless-broker` moves to `redis:8-alpine`. `paperless-db` stays on Debian `postgres:17` (`glibc`).
8. **Backup Integrity:** `config/rclone/filter.txt.example` excludes live PostgreSQL clusters and SQLite `-wal`/`-shm` files. `scripts/backup.sh` takes atomic SQLite `.backup` snapshots and archives with `--backup-dir`. `scripts/restore.sh` imports dumps with `psql`.
9. **Download Mount Staging:** `qbittorrent` and `cross-seed` add `${DOCKER_DATA_DIR}:/data` next to `${DOCKER_DATA_DIR}/torrents:/downloads` for a zero-downtime move to unified `/data/torrents`.
10. **Coder & Script Safety:** `coder/default.tf` removed. `coder/main.tf` downloads prebuilt `jj` `v0.28.2` musl binaries. `scripts/setup_jellyfin_metal.py` guards `shutil.rmtree(CONFIG_DIR)` behind `--reset`. `scripts/test_cross_seed.sh` runs as `-u "${PUID:-501}:${PGID:-20}"`. Shell scripts load `.env` with a safe `load_env` parser and use Bash 3.2 `set -u` safe array expansion.

---

## 2. Before & After Architecture Comparison

### Before (Monolithic & Cluttered)
```
/Users/vrg/Documents/Sol/
├── .env, paperless.env, bitwarden.env    # Fragmented secrets across 3+ files
├── docker-compose.yml                    # 922 lines (25 active + 18 commented services mixed)
├── authentik-compose.yml                 # Redundant compose file in root
├── docker-compose-coder.yml              # Redundant compose file in root
├── docker-compose-backup.yml             # Outdated compose file in root
├── docker-compose-archive.yml            # Outdated compose file in root
├── Caddyfile, Caddyfile.txt              # Live and historic configs in root
├── scan/, vault/, aysynbm/               # Static web apps sitting flat in root
├── backup.sh, test_cross_seed.sh         # Shell scripts sitting flat in root
├── config/                               # Runtime configurations
└── data/                                 # Persistent data and databases
```

### After (Modular, Profiled & Declarative)
```
/Users/vrg/Documents/Sol/
├── .env                                  # Unified, app-segregated secrets & parameters
├── .env.example                          # Sanitized template for version control
├── docker-compose.yml                    # Root Compose orchestrator (name: sol) with native 'include:'
├── Caddyfile                             # Live ingress rules, Authentik forward-auth, 18 commented standby vhosts
├── ports.json                            # Authoritative master port & routing registry (status + profile)
├── Sol.code-workspace
│
├── compose/                              # MODULAR DOMAIN STACKS ([..] = profiles: ["standby"])
│   ├── core.yml                          # Ingress & Identity (Caddy, Authentik, Arcane)
│   ├── monitoring.yml                    # Dashboards & Metrics (Glance, [Gatus, Dozzle, Beszel, Beszel-Agent, Dockge, Uptime Kuma, Homarr])
│   ├── media.yml                         # Media & *arr Suite (Jellyfin, Seerr, Radarr, Sonarr, Bazarr, Lidarr, Prowlarr, Byparr, [FlareSolverr, Recyclarr, Wizarr])
│   ├── download.yml                      # Ingestion (qBittorrent, Cross-Seed, [Unpackerr, qbit_manage, Flood])
│   ├── paperless.yml                     # Dedicated Document Stack (Web, Broker, DB, [Gotenberg, Tika, AI])
│   ├── knowledge.yml                     # Digital Notes & Reading (Ignis, [LeafWiki, Kavita, Calibre, Calibre-Web])
│   ├── coding.yml                        # Developer Environments (code-server, Coder)
│   └── utilities.yml                     # Logistics & Storage (Copyparty, ntfy, [Homebox, Vaultwarden, n8n, Home Assistant, Rclone, Rclone GUI])
│
├── web/                                  # STATIC FRONTENDS & APPS
│   ├── mind/                             # Quartz Digital Garden build (/mind) -> quartz/public
│   ├── fam/                              # Family Data Vault static app (/fam)
│   ├── scan/                             # Homebox Mobile Barcode Scanner PWA (/scan)
│   └── aysynbm/                          # Async Bookmark Manager (/aysynbm)
│
├── scripts/                              # MAINTENANCE & AUTOMATION
│   ├── backup.sh                         # PG dumps + SQLite .backup snapshots + versioned OneDrive rclone sync
│   ├── restore.sh                        # Cloud pull, SQLite snapshot restore, psql dump import, stack start
│   ├── setup_jellyfin_metal.py           # Native Jellyfin Metal launcher (destructive reset only with --reset)
│   └── test_cross_seed.sh                # Filesystem & cross-seed permission diagnostic (unprivileged UID:GID)
│
├── coder/                                # Coder v2 Terraform (main.tf only, default.tf removed)
├── config/                               # PERSISTENT CONFIGURATIONS (Paths 100% Intact)
│   └── rclone/filter.txt.example         # Tracked backup filter template
├── data/                                 # PERSISTENT DATA & DATABASES (Paths 100% Intact)
│   └── backups/sqlite/                   # Atomic SQLite snapshots
├── logs/                                 # AUDIT & BACKUP LOG ARCHIVES
│
├── docs/
│   ├── system_state/                     # 00-09 Architectural Documentation
│   ├── FLASH_LOCAL_VERIFICATION_RUNBOOK.md
│   └── archive/                          # Archived historic compose files, paperless.env & logs
│
└── _backup_pre_refactor/                 # Pre-refactoring safety rollback snapshot
```

---

## 3. Detailed Component Breakdown

### 3.1 Domain Compose Stacks (`compose/`)

| Stack File | Active Services | Standby / Ops Services (`profiles:`) | Purpose |
| :--- | :--- | :--- | :--- |
| **`core.yml`** | `caddy`, `authentik-postgresql`, `authentik-server`, `authentik-worker`, `arcane` (5) | None | Core edge routing, authentication, and Docker management. |
| **`monitoring.yml`** | `glance` (1) | `gatus`, `dozzle`, `beszel`, `beszel-agent`, `dockge`, `uptime-kuma`, `homarr` (7) | System health overview, metrics, and homelab dashboards. |
| **`media.yml`** | `jellyfin`, `seerr`, `radarr`, `sonarr`, `bazarr`, `lidarr`, `prowlarr`, `byparr` (8) | `flaresolverr`, `recyclarr`, `wizarr` (3) | Video/music streaming, automated metadata ingestion, challenge solving, and requests. |
| **`download.yml`** | `qbittorrent`, `cross-seed` (2) | `unpackerr`, `qbit_manage`, `flood` (3) | High-throughput BitTorrent client and cross-seed daemon. |
| **`paperless.yml`** | `paperless-webserver`, `paperless-broker`, `paperless-db` (3) | `paperless-gotenberg`, `paperless-tika`, `paperless-ai` (3) | Document OCR, indexing, and archival engine. |
| **`knowledge.yml`** | `ignis` (1) | `leafwiki`, `kavita`, `calibre`, `calibre-web` (4) | Obsidian note synchronization, digital gardens, and e-books. |
| **`coding.yml`** | `code-server`, `coder` (2) | None | Web IDEs and on-demand Terraform container workspaces. |
| **`utilities.yml`** | `copyparty`, `ntfy` (2) | `homebox`, `vaultwarden`, `n8n`, `homeassistant`, `rclone` (`ops`, `standby`), `rclone-gui` (6) | Multi-user file sharing, push notifications, inventory (standby), and backup workers. |
| **Total** | **24** | **26** | Plus native macOS `jellyfin-metal` on port `8097`. |

### 3.2 Profile Mechanics

| Command | Effect |
| :--- | :--- |
| `docker compose up -d` | Starts the 24 active containers. Profiled services are ignored. |
| `docker compose --profile standby up -d <service>` | Starts one standby service. |
| `docker compose --profile ops run --rm rclone <args>` | One-shot rclone task (used by `scripts/backup.sh` fallback). |
| `docker compose --profile standby config` | Validates all 50 service definitions, including standby. |
| `docker compose config` | Validates the active set (used by `scripts/restore.sh`). |

### 3.3 Scripts & Terraform Changes

| File | Change | Safety Effect |
| :--- | :--- | :--- |
| `scripts/backup.sh` | Adds safe `load_env`, `.tmp` dump then `mv`, SQLite `.backup` snapshots to `data/backups/sqlite/`, `--backup-dir OneDrive:Sol-archive/<TIMESTAMP>`, `filter.txt.example` fallback, `--profile ops` container fallback | Crash-consistent DB state in the cloud, point-in-time recovery of overwritten files |
| `scripts/restore.sh` | Adds `--dry-run`, `--skip-cloud-pull`, `--restore-dbs`, `--start-stack`, SQLite snapshot restore, real `psql` dump import, Bash 3.2 safe arrays | Cold-start recovery without manual SQL steps |
| `scripts/setup_jellyfin_metal.py` | `shutil.rmtree(CONFIG_DIR)` only with `--reset`. Default relaunches and preserves `jellyfin.db` | No accidental loss of users, API keys, or watch history |
| `scripts/test_cross_seed.sh` | `docker exec -u "${PUID:-501}:${PGID:-20}"` instead of root, adds unified `/data` hardlink test | Results match the daemon's real permissions |
| `coder/default.tf` | Removed | Eliminates duplicate Terraform resource definitions |
| `coder/main.tf` | Prebuilt `jj` `v0.28.2` musl tarball from GitHub releases, `apt-get install -y curl unzip git tar` | Faster workspace start, no Rust toolchain or `cargo install` |

---

## 4. Technical Answers & Investigation Findings

### Paperless-AI Environment Variable Resolution
* **Question:** Can Paperless-AI environment variables lie outside its directory (`data/paperless-ai/.env`)?
* **Findings:** **Yes.**
  1. `clusterzx/paperless-ai` reads standard container environment variables (`process.env`).
  2. Defining variables centrally in `.env` (or through `compose/paperless.yml`) passes them into the container process on startup.
  3. Paperless-AI generates `/app/data/.env` as a local cache if variables are omitted. Passing environment variables through compose overrides that cache and keeps configuration central.

### Environment Variable Security & Isolation
* With blanket `env_file:` imports removed across `authentik` and `paperless`, each service receives only the parameters mapped under its `environment:` block.
* Unrelated system tokens (for example `BESZEL_AGENT_TOKEN`, `ARCANE_JWT_SECRET`) never reach other containers' environments.
* Host scripts no longer `source ./.env` directly. The `load_env` parser exports only keys that match `^[A-Za-z_][A-Za-z0-9_]*$`, strips surrounding quotes, and strips inline comments only on unquoted values. `.env.example` quotes `PAPERLESS_OCR_LANGUAGES="hin kan pan"` and single-quotes the `PAPERLESS_SOCIALACCOUNT_PROVIDERS` JSON to match.

### Cross-Stack Container Networking
* All compose stacks are included into the root `docker-compose.yml` (project `name: sol`), so Docker assigns every service to the common network `sol_default`. Profiled services join the same network when started.
* Internal DNS hostnames (`authentik-server:9000`, `radarr:7878`, `sonarr:8989`, `glance:8080`, `ntfy:80`, `flaresolverr:8191` via `byparr` alias) resolve across stack boundaries.

### Paperless Database Image Decision
* `paperless-db` stays on Debian `postgres:17` (`glibc`). Moving the existing `data/paperless/db` cluster to `postgres:17-alpine` (`musl`) risks a collation mismatch on text indexes.
* The Alpine move is documented as an optional local trial: `pg_dump` from Debian, start a fresh Alpine cluster, `pg_restore`, then reindex. See `TODO.md` and `docs/FLASH_LOCAL_VERIFICATION_RUNBOOK.md`.

---

## 5. Rollback & Disaster Recovery Procedures

If a rollback is required, a full snapshot of the pre-refactor configuration is saved in `_backup_pre_refactor/`.

### Rollback Commands
To revert all configuration files to their pre-refactored state:
```bash
# 1. Navigate to Sol root
cd /Users/vrg/Documents/Sol

# 2. Restore all pre-refactor files
cp -a _backup_pre_refactor/.env .
cp -a _backup_pre_refactor/docker-compose.yml .
cp -a _backup_pre_refactor/paperless.env .
cp -a _backup_pre_refactor/Caddyfile .
cp -a _backup_pre_refactor/ports.json .
cp -a _backup_pre_refactor/backup.sh .
cp -a _backup_pre_refactor/test_cross_seed.sh .
```
*(Note: Phase 1 did not modify or move any files in `./data` or `./config`, so application databases and state remain 100% intact.)*

### Phase 2 Rollback Notes
* **Profiles:** To run a standby service permanently, delete its `profiles:` line. To return to the old model, comment the whole block instead (not recommended, because commented YAML escapes `docker compose config` validation).
* **Byparr:** `docker compose stop byparr && docker compose --profile standby up -d flaresolverr`. Prowlarr settings need no change.
* **Authentik loopback:** Remove the `127.0.0.1:` prefix in `compose/core.yml` to re-expose `9000` and `9443` on all interfaces.
* **Download mounts:** Removing `${DOCKER_DATA_DIR}:/data` from `qbittorrent` and `cross-seed` is safe while all save paths still use `/downloads`.
* **Cloud archive:** Any file overwritten or deleted by a backup run can be recovered from `OneDrive:Sol-archive/<TIMESTAMP>`.
