# 02. Storage, Volumes & Persistence Topology

> **Scope:** Physical and virtual storage architecture, container volume bindings across all 29 active and 16 standby/ops services, cross-filesystem APFS hardlink and ExFAT relative symlink mechanics, and the Two-Tier Disaster Recovery & Backup Strategy on `Sol`.  
> **Host Root:** `/Users/vrg/Documents/Sol` (`DOCKER_BASE_DIR`)  
> **External Storage Devices:** `/Volumes/PANOPTICON` (`EXTERNAL_DRIVE_00`, mounted 2 TB ExFAT USB drive), `/Volumes/PHOENIX` (`EXTERNAL_DRIVE_01`, standby)  
> **Tier 1 State Backup Targets (Backrest + Restic):** `/Volumes/PANOPTICON/backups/sol-restic` (`local-panopticon`) and `rclone:OneDrive:Sol-Restic` (`onedrive-cloud`)  
> **Tier 2 Blueprint Backup Target (GitHub):** `https://github.com/varungupta3009/Sol` (lean, zero-secret declarative IaC blueprint)  
> **Exclude Rules:** [`config/backrest/excludes.txt.example`](../../config/backrest/excludes.txt.example) (`config/backrest/excludes.txt`) and [`config/rclone/filter.txt.example`](../../config/rclone/filter.txt.example)  
> **Last Synced to Ground Truth:** 2026-10-20  

---

## 1. Storage Taxonomy & Physical Hierarchy

Sol keeps high-frequency transactional data (SQLite and PostgreSQL databases, container configs, document OCR indexes, and active workspace state) on the internal Apple Silicon NVMe SSD (`APFS`). Multi-terabyte bulk media and long-term seed payloads span the internal SSD (`./data/media`, `./data/torrents`) and external mass storage (`/Volumes/PANOPTICON/{media,torrents}`).

```
/Users/vrg/Documents/Sol (Internal APFS NVMe SSD Base)
├── compose/                     --> 8 modular domain Compose files (core, monitoring, media, download, paperless, knowledge, coding, utilities)
├── config/                      --> Container runtime configurations, XML/YAML/TOML configs, Servarr/Jellyfin/QUI/Seerr SQLite DBs
│   ├── auth/                    --> users.json (local), users.json.example (tracked)
│   ├── backrest/                --> config.json, excludes.txt (local) + *.example (tracked)
│   ├── glance/                  --> Tracked glance.yml, user.css, sol.svg
│   ├── qui/                     --> qui.db + tracked tracker_registry.json
│   └── rclone/                  --> rclone.conf (secret), filter.txt (local), filter.txt.example (tracked)
├── data/                        --> Application state, document archives, relational/SQLite DBs, local media & downloads
│   ├── backups/                 --> Staged PostgreSQL dumps (paperless_db.sql.gz, airtrail_db.sql.gz, coder_db.sql.gz),
│   │   │                            coder_home.tar.gz, coder_volume_name.txt, and symlinks_manifest.tsv (1,459 symlinks)
│   │   └── sqlite/              --> 29 clean WAL-complete SQLite .backup snapshots (PRAGMA journal_mode=DELETE, 0 sidecars)
│   ├── media/                   --> Internal fast SSD media storage (movies, tv, music, books, home-videos, preshows)
│   ├── torrents/                --> Internal APFS torrent payloads, saved .torrent metafiles (files/), cross-seed-links, qui-links
│   ├── paperless/               --> consume, data, db (PostgreSQL 17.11 Alpine musl hosting paperless + airtrail), export, media, redis, scripts
│   ├── lldap/                   --> users.db (Rust LDAP directory SQLite DB)
│   ├── tinyauth/                --> tinyauth.db (sessions & pre-seeded oidc_consents), whitelist.txt, oidc/key.pem
│   ├── arcane/                  --> arcane.db (SQLite WAL mode) & stack definitions
│   ├── backrest/                --> data/ (oplog.sqlite, kvdb.sqlite, tasklogs) & cache/ (excluded from Restic)
│   ├── homebox/                 --> homebox.db (SQLite WAL mode) & uploaded asset attachments
│   ├── ignis/                   --> Obsidian vaults/, data/, obsidian/
│   ├── readeck/                 --> config.toml & data/db.sqlite3 (read-later archive)
│   ├── pocketbase/              --> data.db & auxiliary.db (Go + SQLite sandbox)
│   ├── enclosed/                -->Encrypted notes & file drops storage
│   ├── airtrail/                --> Uploaded flight attachments (relational data lives in paperless-db 'airtrail' DB)
│   ├── copyparty/               --> Shared uploads root
│   ├── ntfy/                    --> var/cache/ntfy message queue & attachment cache
│   └── caddy/                   --> Let's Encrypt TLS certificates, ACME state, and locks
├── web/                         --> 9 static web apps (/fam, /scan, /aysynbm, /tools, /chef, /pdf, /speed, /draw, /mi)
├── quartz/                      --> Quartz v4 digital garden (quartz/public mounted into caddy as /mind:ro)
├── scripts/                     --> 9 active operational scripts + launchd/*.plist + archive/*
├── coder/                       --> Terraform Coder v2 workspace template (main.tf)
├── docs/                        --> Master architecture & audit documentation (system_state/00-11)
├── logs/                        --> LaunchAgent & operational logs (db_stage.log, identity_sync.log)
└── /Volumes/PANOPTICON (Ext)    --> 2 TB ExFAT USB drive: media/{movies,tv}, torrents/{movies,tv,cross-seed-links,qui-links}, backups/sol-restic
```

---

## 2. Master Container Mount Matrix (29 Active Containers)

The following table indexes every bind mount, volume, and `tmpfs` mount across all 29 active containers:

| Service | Host Source Path / Tmpfs | Container Mount Path | Mode | Classification / Purpose |
| :--- | :--- | :--- | :---: | :--- |
| **`caddy`** | `${DOCKER_BASE_DIR}/Caddyfile` | `/etc/caddy/Caddyfile` | `ro` | Edge Reverse Proxy Rules |
| | `${DOCKER_DATA_DIR}/caddy` | `/data` | `rw` | Let's Encrypt TLS certs & ACME keys |
| | `${DOCKER_CONFIG_DIR}/caddy` | `/config` | `rw` | Caddy runtime JSON state (`autosave.json`) |
| | `${DOCKER_BASE_DIR}/quartz/public` | `/mind` | `ro` | Quartz Digital Garden static HTML |
| | `${DOCKER_BASE_DIR}/web/fam` | `/fam` | `ro` | Family Data Vault static app (`vault.enc`) |
| | `${DOCKER_BASE_DIR}/web/scan` | `/scan` | `ro` | Homebox Barcode Scanner PWA |
| | `${DOCKER_BASE_DIR}/web/aysynbm` | `/aysynbm` | `ro` | Async Bookmark Manager static app |
| | `${DOCKER_BASE_DIR}/web/tools` | `/tools` | `ro` | IT-Tools static bundle |
| | `${DOCKER_BASE_DIR}/web/chef` | `/chef` | `ro` | CyberChef static bundle |
| | `${DOCKER_BASE_DIR}/web/pdf` | `/pdf` | `ro` | BentoPDF static bundle |
| | `${DOCKER_BASE_DIR}/web/speed` | `/speed` | `ro` | OpenSpeedTest static bundle |
| | `${DOCKER_BASE_DIR}/web/draw` | `/draw` | `ro` | Excalidraw static bundle |
| | `${DOCKER_BASE_DIR}/web/mi` | `/mi` | `ro` | MediaInfo WebASM + `/mi/rom` NES bundle |
| **`tinyauth`** | `${DOCKER_DATA_DIR}/tinyauth` | `/data` | `rw` | `tinyauth.db`, `whitelist.txt`, `oidc/key.pem` |
| **`lldap`** | `${DOCKER_DATA_DIR}/lldap` | `/data` | `rw` | `users.db` (LLDAP user/group directory) |
| **`arcane`** | `/var/run/docker.sock` | `/var/run/docker.sock` | `rw` | Host Docker container & stack orchestration |
| | `${DOCKER_DATA_DIR}/arcane` | `/app/data` | `rw` | `arcane.db` (SQLite WAL mode) & projects |
| **`glance`** | `${DOCKER_CONFIG_DIR}/glance/config` | `/app/config` | `rw` | Dashboard configuration (`glance.yml`) |
| | `${DOCKER_CONFIG_DIR}/glance/assets` | `/app/assets` | `rw` | Custom CSS & SVG branding (`user.css`, `sol.svg`) |
| | `${EXTERNAL_DRIVE_00}` | `/media/panopticon` | `ro` | External drive disk capacity telemetry |
| | `/var/run/docker.sock` | `/var/run/docker.sock` | `ro` | Container health & status inspection |
| | `/etc/localtime` | `/etc/localtime` | `ro` | Host local clock sync |
| **`jellyfin`** | `${DOCKER_CONFIG_DIR}/jellyfin` | `/config` | `rw` | `jellyfin.db`, plugins, metadata |
| | `${DOCKER_DATA_DIR}/media` | `/media/internal` | `rw` | Internal APFS SSD media library |
| | `${EXTERNAL_DRIVE_00}` | `/media/external` | `rw` | External USB media library (`/Volumes/PANOPTICON`) |
| | *RAM `tmpfs`* (`size=2g,uid=501,gid=20`) | `/tmp/jellyfin` | `rw` | Trickplay & transcode frame buffers in RAM |
| **`seerr`** | `${DOCKER_CONFIG_DIR}/seerr` | `/app/config` | `rw` | `db/db.sqlite3` & `settings.json` |
| **`radarr`** | `${DOCKER_CONFIG_DIR}/radarr` | `/config` | `rw` | `radarr.db`, `custom_scripts/`, `config.xml` |
| | `${DOCKER_DATA_DIR}` | `/data` | `rw` | Unified APFS root (`/data/torrents` <-> `/data/media`) |
| | `${EXTERNAL_DRIVE_00}` | `/external` | `rw` | Unified ExFAT root (`/external/torrents` <-> `/external/media`) |
| **`sonarr`** | `${DOCKER_CONFIG_DIR}/sonarr` | `/config` | `rw` | `sonarr.db`, `custom_scripts/`, `config.xml` |
| | `${DOCKER_DATA_DIR}` | `/data` | `rw` | Unified APFS root |
| | `${EXTERNAL_DRIVE_00}` | `/external` | `rw` | Unified ExFAT root |
| **`bazarr`** | `${DOCKER_CONFIG_DIR}/bazarr` | `/config` | `rw` | `db/bazarr.db` & `config/config.yaml` |
| | `${DOCKER_DATA_DIR}` | `/data` | `rw` | Internal media subtitle access |
| | `${EXTERNAL_DRIVE_00}` | `/external` | `rw` | External media subtitle access |
| **`lidarr`** | `${DOCKER_CONFIG_DIR}/lidarr` | `/config` | `rw` | `lidarr.db` & `config.xml` |
| | `${DOCKER_DATA_DIR}` | `/data` | `rw` | Internal music & torrent root |
| | `${EXTERNAL_DRIVE_00}` | `/external` | `rw` | External music & torrent root |
| **`prowlarr`** | `${DOCKER_CONFIG_DIR}/prowlarr` | `/config` | `rw` | `prowlarr.db`, `Definitions/`, `config.xml` |
| **`byparr`** | *RAM `tmpfs`* (`size=512m,exec,mode=1777`) | `/tmp` | `rw` | Ephemeral Camoufox/Firefox profile scratch (`shm_size: 1gb`) |
| **`qbittorrent`** | `${DOCKER_CONFIG_DIR}/qbittorrent` | `/config` | `rw` | `qBittorrent.conf`, `BT_backup/`, `scripts/torrent_finished.py` |
| | `${DOCKER_DATA_DIR}` | `/data` | `rw` | Internal APFS torrents (`/data/torrents`) & media (`/data/media`) |
| | `${EXTERNAL_DRIVE_00}` | `/external` | `rw` | External ExFAT torrents (`/external/torrents`) & media (`/external/media`) |
| **`qui`** | `${DOCKER_CONFIG_DIR}/qui` | `/config` | `rw` | `qui.db` & `tracker_registry.json` |
| | `${DOCKER_DATA_DIR}` | `/data` | `rw` | Internal cross-seed symlink tree (`/data/torrents/qui-links`) |
| | `${EXTERNAL_DRIVE_00}` | `/external` | `rw` | External cross-seed symlink tree (`/external/torrents/qui-links`) |
| **`paperless-webserver`** | `${DOCKER_CONFIG_DIR}/paperless` | `/usr/src/paperless/config` | `rw` | Paperless runtime configuration |
| | `${DOCKER_DATA_DIR}/paperless/data` | `/usr/src/paperless/data` | `rw` | Search index, classification model, Celery schedule |
| | `${DOCKER_DATA_DIR}/paperless/media` | `/usr/src/paperless/media` | `rw` | Archived PDFs, originals, and thumbnails |
| | `${DOCKER_DATA_DIR}/paperless/export` | `/usr/src/paperless/export` | `rw` | Document export staging |
| | `${DOCKER_DATA_DIR}/paperless/consume` | `/usr/src/paperless/consume` | `rw` | Recursive document intake drop folder |
| | `${DOCKER_DATA_DIR}/paperless/scripts` | `/usr/src/paperless/scripts` | `rw` | `pre-consumption.py`, `ntfy_notify.sh`, `passwords.txt` (`0600`) |
| **`paperless-broker`** | `${DOCKER_DATA_DIR}/paperless/redis` | `/data` | `rw` | Redis 8 persistence (`dump.rdb`) |
| **`paperless-db`** | `${DOCKER_DATA_DIR}/paperless/db` | `/var/lib/postgresql/data` | `rw` | PostgreSQL 17.11 Alpine (`musl`) cluster (`paperless` + `airtrail` DBs) |
| **`ignis`** | `${DOCKER_DATA_DIR}/ignis/vaults` | `/vaults` | `rw` | Obsidian markdown vaults |
| | `${DOCKER_DATA_DIR}/ignis/data` | `/app/data` | `rw` | Ignis application state |
| | `${DOCKER_DATA_DIR}/ignis/obsidian` | `/app/obsidian-app` | `rw` | Obsidian core application assets |
| **`readeck`** | `${DOCKER_DATA_DIR}/readeck` | `/readeck` | `rw` | `config.toml`, `data/db.sqlite3`, extracted article archives |
| **`code-server`** | `${DOCKER_CONFIG_DIR}/code-server` | `/config` | `rw` | VS Code settings, extensions, state |
| | `${DOCKER_BASE_DIR}` | `/Server` | `rw` | Sol repository root |
| | `/Users/vrg/Documents` | `/Documents` | `rw` | Host Documents workspace |
| **`coder`** | `/var/run/docker.sock` | `/var/run/docker.sock` | `rw` | Docker workspace provisioning (`group_add: ["0"]`) |
| | `${DOCKER_CONFIG_DIR}/coder` | `/home/coder/.config` | `rw` | Embedded PostgreSQL 16 & Coder state |
| | `${DOCKER_BASE_DIR}` | `/Sol` | `rw` | Sol repository & `coder/main.tf` template |
| **`pocketbase`** | `${DOCKER_DATA_DIR}/pocketbase` | `/pb_data` | `rw` | `data.db` & `auxiliary.db` |
| **`copyparty`** | `${DOCKER_CONFIG_DIR}/copyparty` | `/cfg` | `rw` | `copyparty.conf` & session state |
| | `${DOCKER_DATA_DIR}/copyparty` | `/w/copyparty` | `rw` | Dedicated upload root |
| | `${DOCKER_DATA_DIR}/media` | `/w/media` | `rw` | Internal media file browser |
| | `${DOCKER_DATA_DIR}/torrents` | `/w/torrents` | `rw` | Internal torrent file browser |
| | `${EXTERNAL_DRIVE_00}` | `/w/external` | `rw` | External drive file browser |
| **`ntfy`** | `${DOCKER_DATA_DIR}/ntfy/var/cache/ntfy` | `/var/cache/ntfy` | `rw` | Persistent notification cache & attachments |
| | `${DOCKER_CONFIG_DIR}/ntfy/etc/ntfy` | `/etc/ntfy` | `rw` | `server.yml` configuration |
| **`homebox`** | `${DOCKER_DATA_DIR}/homebox` | `/data/` | `rw` | `homebox.db` & inventory item photos |
| **`backrest`** | `${DOCKER_CONFIG_DIR}/backrest` | `/config` | `rw` | `config.json` & `excludes.txt` |
| | `${DOCKER_DATA_DIR}/backrest/data` | `/data` | `rw` | `oplog.sqlite`, `kvdb.sqlite`, `tasklogs/` |
| | `${DOCKER_DATA_DIR}/backrest/cache` | `/cache` | `rw` | Local Restic chunk cache (excluded from backup) |
| | `${DOCKER_CONFIG_DIR}/rclone` | `/rclone` | `rw` | `rclone.conf` for `rclone:OneDrive:Sol-Restic` |
| | `${DOCKER_BASE_DIR}` | `/userdata/sol` | `rw` | Full Sol root directory for backup & restore |
| | `${EXTERNAL_DRIVE_00}/backups/sol-restic` | `/repos/local-panopticon` | `rw` | Local encrypted Restic repository on PANOPTICON |
| **`enclosed`** | `${DOCKER_DATA_DIR}/enclosed` | `/app/.data` | `rw` | Encrypted note & file drop storage |
| **`airtrail`** | `${DOCKER_DATA_DIR}/airtrail` | `/app/uploads` | `rw` | Boarding pass & aircraft uploads |

---

## 3. Standby & Ops Profile Mount Matrix (16 Containers)

| Service | Host Source Path | Container Mount Path | Mode | Purpose |
| :--- | :--- | :--- | :---: | :--- |
| **`gatus`** | `${DOCKER_CONFIG_DIR}/gatus` | `/config` | `rw` | Endpoint definitions |
| **`dozzle`** | `/var/run/docker.sock` | `/var/run/docker.sock` | `ro` | Container log streaming |
| **`beszel`** | `${DOCKER_DATA_DIR}/beszel` | `/beszel_data` | `rw` | Metrics hub SQLite DB (`data.db`) |
| **`beszel-agent`** | `/var/run/docker.sock` | `/var/run/docker.sock` | `ro` | Container resource telemetry |
| | `${DOCKER_DATA_DIR}/beszel_agent` | `/var/lib/beszel-agent` | `rw` | Agent identity state |
| **`recyclarr`** | `${DOCKER_CONFIG_DIR}/recyclarr` | `/config` | `rw` | TRaSH Guides sync config |
| **`wizarr`** | `${DOCKER_CONFIG_DIR}/wizarr` | `/data` | `rw` | `database/database.db` |
| **`unpackerr`** | `${DOCKER_CONFIG_DIR}/unpackerr` | `/config` | `rw` | Archive extractor config |
| | `${DOCKER_DATA_DIR}` | `/data` | `rw` | Watches `/data/torrents` |
| | `${EXTERNAL_DRIVE_00}` | `/external` | `rw` | External archives |
| **`paperless-ai`** | `${DOCKER_DATA_DIR}/paperless-ai` | `/app/data` | `rw` | AI vector index & state |
| **`leafwiki`** | `${DOCKER_DATA_DIR}/leafwiki` | `/app/data` | `rw` | Markdown files & 6 SQLite DBs |
| **`kavita`** | `${DOCKER_CONFIG_DIR}/kavita` | `/config` | `rw` | Reader database |
| | `${DOCKER_DATA_DIR}` | `/data` | `rw` | E-book & manga library root |
| **`vaultwarden`** | `${DOCKER_CONFIG_DIR}/vaultwarden` | `/data/` | `rw` | `db.sqlite3` & RSA keys |
| **`n8n`** | `${DOCKER_CONFIG_DIR}/n8n` | `/home/node/.n8n` | `rw` | Workflow definitions & credentials |
| | `${DOCKER_DATA_DIR}/n8n` | `/files` | `rw` | Workflow file I/O |
| **`homeassistant`** | `${DOCKER_CONFIG_DIR}/homeassistant` | `/config` | `rw` | Automations & state |
| | `/etc/localtime`, `/run/dbus` | `/etc/localtime`, `/run/dbus` | `ro` | Clock & D-Bus |
| **`rclone`** (`ops`) | `${DOCKER_CONFIG_DIR}/rclone` | `/config/rclone` | `rw` | `rclone.conf`, `filter.txt` |
| | `${DOCKER_BASE_DIR}` | `/source` | `ro` | Backup source tree |
| | `${DOCKER_LOGS_DIR}` | `/logs` | `rw` | Sync logs |

`paperless-gotenberg` and `paperless-tika` are stateless and declare no host volumes.

---

## 4. Zero-Copy Media Import & Cross-Seeding Architecture (APFS Hardlinks + ExFAT Relative Symlinks)

1. **Internal SSD (`APFS` — `/data/torrents` <-> `/data/media`):**
   - `qbittorrent`, `qui`, `radarr`, `sonarr`, `bazarr`, and `lidarr` all mount `${DOCKER_DATA_DIR}` (`/Users/vrg/Documents/Sol/data`) at `/data`.
   - Because `/data/torrents` and `/data/media` share a single container mount point on APFS, imports on internal storage execute via **instant zero-copy atomic hardlinks**.
2. **External Mass Storage (`ExFAT` — `/Volumes/PANOPTICON`):**
   - ExFAT does not support POSIX hardlinks (`link(2)` returns `EPERM`/`ENOSYS`), so standard Servarr imports would perform a slow multi-gigabyte physical file copy across USB, doubling disk consumption.
   - **Option A Pre-Import Relative Symlink Pipeline (`scripts/torrent_finished.py` + `scripts/arr_symlink_dedupe.sh`):**
     - When a torrent finishes in `qbittorrent`, `/config/scripts/torrent_finished.py` computes the relative path (`../../../torrents/movies/...` or `../../../../torrents/tv/...`) and pre-creates a **relative symlink** inside `/external/media/{movies,tv}/...` before triggering Radarr/Sonarr `RescanMovie`/`RescanSeries` + `DownloadedMoviesScan`/`DownloadedEpisodesScan`.
     - Because the symlink is **relative** (`../../../torrents/...`), it resolves identically inside `radarr`/`sonarr`/`bazarr`/`qbittorrent` (mounted at `/external`), inside `jellyfin` (mounted at `/media/external`), inside `copyparty` (mounted at `/w/external`), and on the macOS host (`/Volumes/PANOPTICON`)!
     - As a defense-in-depth safety net, Radarr and Sonarr also register `scripts/arr_symlink_dedupe.sh` (`OnDownload` / `OnUpgrade`), which verifies `case "$DEST" in /external/media/*)` and replaces any physical copy on `/external/media/*` with a relative symlink (`realpath -m --relative-to="$DIR" "$REAL_SRC"`).
3. **QUI Native Cross-Seeding (`qui-links` & `cross-seed-links`):**
   - `qui` scans Prowlarr Torznab indexers and injects matched cross-seeds into `qbittorrent` using symlinks in `/data/torrents/qui-links` and `/external/torrents/qui-links` (alongside preserved historical symlinks in `cross-seed-links`), achieving 100% zero-copy multi-tracker seeding.

---

## 5. Two-Tier Disaster Recovery, Backup & Restore Strategy

| Tier | Target | Engine & Cadence | Purpose & Guarantees |
| :--- | :--- | :--- | :--- |
| **Tier 1: Full Server State Backup** | **1a. Local External Drive:** `/Volumes/PANOPTICON/backups/sol-restic` (`local-panopticon`)<br>**1b. Cloud Off-Site:** `rclone:OneDrive:Sol-Restic` (`onedrive-cloud`) | **Backrest (`v1.14.1`) + Restic (`0.19.1`)** + [`scripts/stage_db_backups.sh`](../../scripts/stage_db_backups.sh)<br>DB Staging (`com.vrg.sol.db-stage`): `02:45` & `14:45` IST<br>Local Restic: `03:00` & `15:00` IST<br>OneDrive Restic: `03:30` IST | Captures **100% of server state** in `/Users/vrg/Documents/Sol` (`.env` secrets, live PostgreSQL dumps for `paperless`, `airtrail`, and `coder`, 29 WAL-complete SQLite snapshots, `.torrent`/`.fastresume` files, Paperless PDFs, Obsidian vaults, `web/fam` `vault.enc`, Coder home volume archive, and the 1,459-entry media symlink manifest) while excluding bulk media files, raw torrent payloads, logs, and regenerable caches. |
| **Tier 2: Declarative Blueprint Backup** | **GitHub Repository:** `varungupta3009/Sol` (`origin/main`) | **Git / Jujutsu (`jj`)**<br>On every architectural or configuration change | Tracks a **lean, zero-secret declarative blueprint** (`docker-compose.yml`, `compose/*.yml`, `Caddyfile`, `ports.json`, `.env.example`, `config/glance/**`, `config/qui/tracker_registry.json`, `config/auth/users.json.example`, `config/backrest/*.example`, `config/rclone/filter.txt.example`, `coder/main.tf`, `scripts/*`, `scripts/launchd/*.plist`, and `docs/*`). |

### Tier 1 Pre-Backup Staging Pipeline ([`scripts/stage_db_backups.sh`](../../scripts/stage_db_backups.sh))

Executed automatically at `02:45` and `14:45` IST by `/Users/vrg/Library/LaunchAgents/com.vrg.sol.db-stage.plist` (invoked via `/opt/homebrew/bin/python3` so `launchd` holds macOS TCC permission for `~/Documents`):

| Step | Action | Output / Guarantee |
| :--- | :--- | :--- |
| **1. Paperless & AirTrail PostgreSQL Dumps** | Runs `pg_dump --clean --if-exists` inside `paperless-db` (`postgres:17-alpine`) for both `paperless` and `airtrail` | Written atomically via `.tmp` rename to `data/backups/paperless_db.sql.gz` (`~788 KB`) and `data/backups/airtrail_db.sql.gz` (`~2.7 MB`). |
| **2. Coder Embedded PostgreSQL Dump** | Runs `pg_dump -h ::1 -p 43235 -U coder -d coder --clean --if-exists \| grep -v '^SET transaction_timeout'` | Written atomically to `data/backups/coder_db.sql.gz` (`~95 KB`), 100% compatible with Coder's embedded PostgreSQL 16. |
| **3. Clean VirtioFS-Safe SQLite Snapshots** | Wipes `./data/backups/sqlite/*`, scans active/standby directories (excluding `logs.db`, `cache.db`, `auxiliary.db`, `up2k.db`, `MediaCover*`), copies `.db` + `-wal` to a local temp dir, runs `sqlite3 .backup`, sets `PRAGMA journal_mode=DELETE;`, and deletes any `-wal`/`-shm` sidecars | Materializes **29 clean, single-file, WAL-complete SQLite snapshots** in `data/backups/sqlite/` with zero `-wal`/`-shm` sidecar files and zero deleted-service leftovers. |
| **4. TCC-Free Media & Cross-Seed Symlink Manifest** | Scans `/sol_data/{media,torrents/cross-seed-links,torrents/qui-links}` and `/panopticon/{media,torrents/cross-seed-links,torrents/qui-links}` inside an OrbStack `redis:8-alpine` container (bypassing macOS `kTCCServiceSystemPolicyRemovableVolumes` blocks on `/Volumes/PANOPTICON`) | Exports `1,459` `<link_path>\t<target_path>` rows to `data/backups/symlinks_manifest.tsv` (`~277 KB`). |
| **5. Coder Workspace Volume Archive** | Records the `coder-*-home` Docker volume name in `data/backups/coder_volume_name.txt` and archives it via `redis:8-alpine` | Written atomically to `data/backups/coder_home.tar.gz` (`~171 KB`) and `data/backups/coder_volume_name.txt`. |

### Bare-Metal Disaster Recovery Playbook ([`scripts/restore.sh`](../../scripts/restore.sh))

In the event of a complete Mac reset, restore the entire Sol server with three commands:

```bash
# 1. Clone the Tier 2 declarative blueprint from GitHub
git clone https://github.com/varungupta3009/Sol.git /Users/vrg/Documents/Sol && cd /Users/vrg/Documents/Sol

# 2. Preview available Tier 1 Restic snapshots (runs ghcr.io/garethgeorge/backrest:latest directly, working even before .env exists on disk)
./scripts/restore.sh --dry-run

# 3. Restore latest Restic snapshot, install static tools & LaunchAgents, recreate all 1,459 media symlinks,
#    restore all 29 SQLite DBs + Paperless/AirTrail/Coder PostgreSQL dumps + Coder home volume, and start all 29 active services
./scripts/restore.sh --restore-dbs --start-stack
```
