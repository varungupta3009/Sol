# 02. Storage, Volumes & Persistence Topology

> **Scope:** Physical and virtual storage architecture, container volume bindings, cross-filesystem linking mechanisms, and disaster recovery backup classifications on `Sol`.  
> **Host Root:** `/Users/vrg/Documents/Sol` (`DOCKER_BASE_DIR`)  
> **External Storage Devices:** `/Volumes/PANOPTICON` (`EXTERNAL_DRIVE_00`, mounted), `/Volumes/PHOENIX` (`EXTERNAL_DRIVE_01`, mounted only in standby `qbit_manage`)  
> **Backup Remote Target:** `OneDrive:Sol` via Rclone, with point-in-time archive `OneDrive:Sol-archive/<TIMESTAMP>`  
> **Filter Rules:** `config/rclone/filter.txt` (local copy) or tracked fallback `config/rclone/filter.txt.example`  
> **Last Synced to Ground Truth:** 2026-10-17  

---

## 1. Storage Taxonomy & Physical Hierarchy

Sol keeps high-frequency transactional data (SQLite and PostgreSQL databases, configs, document OCR pipelines) on the internal SSD. Multi-terabyte bulk media and downloads sit on external mass drives.

```
/Users/vrg/Documents/Sol (Internal SSD Base)
├── compose/                     --> Modular domain Compose files (core, media, download, etc.)
├── config/                      --> Container runtime configurations, XML configs, SQLite DBs
│   ├── jellyfin_metal/          --> Native macOS Jellyfin Metal config, data (jellyfin.db), cache, log
│   └── rclone/                  --> rclone.conf, filter.txt (local), filter.txt.example (tracked)
├── data/                        --> Application state, document storage, local media & downloads
│   ├── backups/                 --> Compressed live PostgreSQL dumps (authentik_db.sql.gz, paperless_db.sql.gz)
│   │   └── sqlite/              --> Atomic online SQLite .backup snapshots (relative path with '/' encoded as '__')
│   ├── media/                   --> Internal fast SSD media storage (preshows, movies, tv, music, books)
│   ├── torrents/                --> Active download payload staging & symlink trees
│   │   └── files/               --> Saved .torrent files repository
│   ├── paperless/               --> Document archives, media assets, OCR databases, hooks
│   ├── authentik/               --> PostgreSQL 16 relational auth cluster (excluded from rclone)
│   ├── arcane/                  --> Arcane management SQLite database
│   ├── homebox/                 --> Homebox asset database and uploaded receipt images (standby, pending SQLite repair)
│   ├── ignis/                   --> Obsidian vaults and sync state
│   ├── leafwiki/                --> LeafWiki SQLite databases and document roots (standby)
│   └── caddy/                   --> TLS ACME certificates, runtime storage, and locks
├── web/                         --> Static web frontends (/fam, /scan, /aysynbm, /mind)
├── scripts/                     --> Automation runners (backup.sh, restore.sh, setup_jellyfin_metal.py, test_cross_seed.sh)
├── quartz/                      --> Quartz digital garden source and public static build
├── docs/                        --> System architecture documentation and archived stacks
├── logs/                        --> Operational audit logs, rclone backup logs (DOCKER_LOGS_DIR)
├── /Volumes/PANOPTICON (Ext)    --> Mass storage media repository (Movies, TV, Music, Downloads)
└── /Volumes/PHOENIX (Ext)       --> Secondary drive (EXTERNAL_DRIVE_01), commented out on all active services
```

---

## 2. Master Container Mount Matrix (Active Profile)

The following table indexes every directory and socket mount across the 24 active containers.

| Service | Host Source Path | Container Mount Path | Mode | Classification / Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **`caddy`** | `${DOCKER_BASE_DIR}/Caddyfile` | `/etc/caddy/Caddyfile` | `ro` | Edge Reverse Proxy Rules |
| | `${DOCKER_DATA_DIR}/caddy` | `/data` | `rw` | Let's Encrypt TLS certs & ACME keys |
| | `${DOCKER_CONFIG_DIR}/caddy` | `/config` | `rw` | Caddy runtime JSON state |
| | `${DOCKER_BASE_DIR}/quartz/public` | `/mind` | `ro` | Quartz Digital Garden static HTML |
| | `${DOCKER_BASE_DIR}/web/fam` | `/fam` | `ro` | Family Data Vault static frontend |
| | `${DOCKER_BASE_DIR}/web/scan` | `/scan` | `ro` | Homebox mobile scanner PWA |
| | `${DOCKER_BASE_DIR}/web/aysynbm` | `/aysynbm` | `ro` | Async Bookmark Manager static HTML |
| **`authentik-postgresql`** | `${DOCKER_DATA_DIR}/authentik` | `/var/lib/postgresql/data` | `rw` | Relational Auth Database (Postgres 16) |
| **`authentik-server`** | `${DOCKER_CONFIG_DIR}/authentik/data` | `/data` | `rw` | Authentik media & static cache |
| | `${DOCKER_CONFIG_DIR}/authentik/custom-templates` | `/templates` | `rw` | Custom Jinja/HTML outpost templates |
| **`authentik-worker`** | `${DOCKER_CONFIG_DIR}/authentik/data` | `/data` | `rw` | Authentik worker media & cache |
| | `${DOCKER_CONFIG_DIR}/authentik/certs` | `/certs` | `rw` | Ingress certificates & signing keys |
| | `${DOCKER_CONFIG_DIR}/authentik/custom-templates` | `/templates` | `rw` | Custom Jinja/HTML templates |
| **`arcane`** | `/var/run/docker.sock` | `/var/run/docker.sock` | `rw` | Host Docker container & stack orchestration |
| | `${DOCKER_DATA_DIR}/arcane` | `/app/data` | `rw` | SQLite DB (`arcane.db`, WAL mode), stack templates |
| **`glance`** | `${DOCKER_CONFIG_DIR}/glance/config` | `/app/config` | `rw` | Dashboard configuration (`glance.yml`) |
| | `${DOCKER_CONFIG_DIR}/glance/assets` | `/app/assets` | `rw` | Custom branding, icons (`sol.svg`) |
| | `/var/run/docker.sock` | `/var/run/docker.sock` | `ro` | Container status monitoring |
| | `/etc/localtime` | `/etc/localtime` | `ro` | Host local clock sync |
| **`jellyfin`** | `${DOCKER_CONFIG_DIR}/jellyfin` | `/config` | `rw` | Media database, plugins, transcode cache |
| | `${DOCKER_DATA_DIR}/media` | `/media/internal` | `rw` | Fast SSD internal media repository |
| | `${EXTERNAL_DRIVE_00}` | `/media/external` | `rw` | Mass storage external media (`/Volumes/PANOPTICON`) |
| **`seerr`** | `${DOCKER_CONFIG_DIR}/seerr` | `/app/config` | `rw` | SQLite database and `settings.json` |
| **`radarr`** | `${DOCKER_CONFIG_DIR}/radarr` | `/config` | `rw` | Radarr SQLite DB, logs, XML configs |
| | `${DOCKER_DATA_DIR}` | `/data` | `rw` | Unified data root (hardlinks & atomic moves) |
| | `${EXTERNAL_DRIVE_00}` | `/external` | `rw` | External movie root |
| **`sonarr`** | `${DOCKER_CONFIG_DIR}/sonarr` | `/config` | `rw` | Sonarr SQLite DB, logs, XML configs |
| | `${DOCKER_DATA_DIR}` | `/data` | `rw` | Unified data root (hardlinks & atomic moves) |
| | `${EXTERNAL_DRIVE_00}` | `/external` | `rw` | External TV shows root |
| **`bazarr`** | `${DOCKER_CONFIG_DIR}/bazarr` | `/config` | `rw` | Subtitle engine database & settings |
| | `${DOCKER_DATA_DIR}` | `/data` | `rw` | Internal media files access |
| | `${EXTERNAL_DRIVE_00}` | `/external` | `rw` | External media files access |
| **`lidarr`** | `${DOCKER_CONFIG_DIR}/lidarr` | `/config` | `rw` | Music automation database & settings |
| | `${DOCKER_DATA_DIR}` | `/data` | `rw` | Internal music & download access |
| | `${EXTERNAL_DRIVE_00}` | `/external` | `rw` | External music library access |
| **`prowlarr`** | `${DOCKER_CONFIG_DIR}/prowlarr` | `/config` | `rw` | Tracker definitions, API keys, SQLite DB |
| **`byparr`** | *(none)* | *(none)* | N/A | Stateless challenge solver |
| **`qbittorrent`** | `${DOCKER_CONFIG_DIR}/qbittorrent` | `/config` | `rw` | qBittorrent.conf, scripts, fastresume data |
| | `${DOCKER_DATA_DIR}/torrents` | `/downloads` | `rw` | In-progress & completed torrent payloads (current save root) |
| | `${DOCKER_DATA_DIR}` | `/data` | `rw` | Unified root staged for zero-downtime migration to `/data/torrents` |
| | `${EXTERNAL_DRIVE_00}` | `/external` | `rw` | Direct seeding on external mass drive |
| **`cross-seed`** | `${DOCKER_CONFIG_DIR}/cross-seed` | `/config` | `rw` | Daemon config (`config.js`), cross-seed DB |
| | `${DOCKER_DATA_DIR}/torrents` | `/downloads` | `rw` | Internal torrent linking root (current `linkDirs`) |
| | `${DOCKER_DATA_DIR}` | `/data` | `rw` | Library-wide `dataDirs` scanning of `/data/torrents` and `/data/media` |
| | `${EXTERNAL_DRIVE_00}` | `/external` | `rw` | External torrent linking root |
| **`paperless-webserver`** | `${DOCKER_CONFIG_DIR}/paperless` | `/usr/src/paperless/config` | `rw` | Paperless runtime configuration |
| | `${DOCKER_DATA_DIR}/paperless/data` | `/usr/src/paperless/data` | `rw` | Search index, classification models |
| | `${DOCKER_DATA_DIR}/paperless/media` | `/usr/src/paperless/media` | `rw` | Stored PDF documents, archives & thumbnails |
| | `${DOCKER_DATA_DIR}/paperless/export` | `/usr/src/paperless/export` | `rw` | Document export target |
| | `${DOCKER_DATA_DIR}/paperless/consume` | `/usr/src/paperless/consume` | `rw` | Drop directory for incoming scan ingestion |
| | `${DOCKER_DATA_DIR}/paperless/scripts` | `/usr/src/paperless/scripts` | `rw` | Pre/Post consumption hooks & passwords |
| **`paperless-broker`** | `${DOCKER_DATA_DIR}/paperless/redis` | `/data` | `rw` | Redis 8 persistence dump (`dump.rdb`) |
| **`paperless-db`** | `${DOCKER_DATA_DIR}/paperless/db` | `/var/lib/postgresql/data` | `rw` | Paperless PostgreSQL 17 cluster (Debian `glibc` collation) |
| **`ignis`** | `${DOCKER_DATA_DIR}/ignis/vaults` | `/vaults` | `rw` | Obsidian markdown vaults |
| | `${DOCKER_DATA_DIR}/ignis/data` | `/app/data` | `rw` | Ignis application database & settings |
| | `${DOCKER_DATA_DIR}/ignis/obsidian` | `/app/obsidian-app` | `rw` | Obsidian core application data |
| **`code-server`** | `${DOCKER_CONFIG_DIR}/code-server` | `/config` | `rw` | VSCode settings, extensions, user history |
| | `${DOCKER_BASE_DIR}` | `/Server` | `rw` | Host Sol repository root |
| | `/Users/vrg/Documents` | `/Documents` | `rw` | Host Documents tree (static absolute path) |
| **`coder`** | `/var/run/docker.sock` | `/var/run/docker.sock` | `rw` | Terraform Docker container orchestration |
| | `${DOCKER_CONFIG_DIR}/coder` | `/home/coder/.config` | `rw` | Coder database, sessions, certificates |
| | `${DOCKER_BASE_DIR}` | `/Sol` | `rw` | Host Sol repository root |
| **`copyparty`** | `${DOCKER_CONFIG_DIR}/copyparty` | `/cfg` | `rw` | `copyparty.conf`, salts, session DB |
| | `${DOCKER_DATA_DIR}/copyparty` | `/w/copyparty` | `rw` | Public/authenticated user upload volume |
| | `${DOCKER_DATA_DIR}/media` | `/w/media` | `rw` | Internal media file browser mount |
| | `${DOCKER_DATA_DIR}/torrents` | `/w/torrents` | `rw` | Torrent storage file browser mount |
| | `${EXTERNAL_DRIVE_00}` | `/w/external` | `rw` | External drive file browser mount |
| **`ntfy`** | `${DOCKER_DATA_DIR}/ntfy/var/cache/ntfy` | `/var/cache/ntfy` | `rw` | Persistent message queue cache & attachments |
| | `${DOCKER_CONFIG_DIR}/ntfy/etc/ntfy` | `/etc/ntfy` | `rw` | `server.yml` configuration directory |

> [!NOTE]
> `authentik-worker` no longer mounts `/var/run/docker.sock`. The active Docker socket consumers are `arcane` (`rw`), `coder` (`rw`), and `glance` (`ro`). Every `${EXTERNAL_DRIVE_01}` mount on active services is commented out. The pre-refactor `:z` SELinux suffix on `copyparty` mounts is not present in `compose/utilities.yml`.

### Native Host (Non-Container) Storage

| Process | Host Path | Purpose |
| :--- | :--- | :--- |
| **`jellyfin-metal`** | `${DOCKER_CONFIG_DIR}/jellyfin_metal` | `network.xml`, server config |
| | `${DOCKER_CONFIG_DIR}/jellyfin_metal/data` | `jellyfin.db` (preserved unless `--reset`) |
| | `${DOCKER_CONFIG_DIR}/jellyfin_metal/cache`, `.../log` | Excluded from rclone |
| | `${DOCKER_DATA_DIR}/media/movies`, `${DOCKER_DATA_DIR}/media/tv` | Library roots (plus `/Volumes/PANOPTICON/Movies`, `/Volumes/PANOPTICON/TV Shows` if present) |

---

## 3. Standby & Ops Profile Mount Matrix

These mounts apply only after `docker compose --profile standby up -d <service>` (or `--profile ops` for `rclone`).

| Service | Host Source Path | Container Mount Path | Mode | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **`recyclarr`** | `${DOCKER_CONFIG_DIR}/recyclarr` | `/config` | `rw` | TRaSH sync config |
| **`wizarr`** | `${DOCKER_CONFIG_DIR}/wizarr` | `/data` | `rw` | Invitation DB |
| **`unpackerr`** | `${DOCKER_CONFIG_DIR}/unpackerr` | `/config` | `rw` | Extractor config |
| | `${DOCKER_DATA_DIR}` | `/data` | `rw` | Watches `UN_FOLDER_0_PATH: /data/torrents` |
| | `${EXTERNAL_DRIVE_00}` | `/external` | `rw` | External archives |
| **`qbit_manage`** | `${DOCKER_CONFIG_DIR}/qbit_manage` | `/config` | `rw` | `config.yml`, logs |
| | `${DOCKER_CONFIG_DIR}/qbittorrent` | `/qbittorrent` | `ro` | qBittorrent state inspection |
| | `${DOCKER_DATA_DIR}/torrents` | `/downloads` | `rw` | Torrent payloads |
| | `${EXTERNAL_DRIVE_00}` | `/external` | `rw` | External payloads |
| | `${EXTERNAL_DRIVE_01}` | `/ext01` | `rw` | `/Volumes/PHOENIX` (only uncommented `EXTERNAL_DRIVE_01` mount) |
| **`flood`** | `${DOCKER_CONFIG_DIR}/flood` | `/config` | `rw` | Flood rundir |
| | `${DOCKER_DATA_DIR}/torrents` | `/data` | `ro` | Torrent payload browsing |
| | `/etc/localtime` | `/etc/localtime` | `ro` | Clock sync |
| **`paperless-ai`** | `${DOCKER_DATA_DIR}/paperless-ai` | `/app/data` | `rw` | AI DB & vector index |
| **`gatus`** | `${DOCKER_CONFIG_DIR}/gatus` | `/config` | `rw` | Endpoint definitions |
| **`dozzle`** | `/var/run/docker.sock` | `/var/run/docker.sock` | `ro` | Log streaming |
| **`beszel`** | `${DOCKER_DATA_DIR}/beszel` | `/beszel_data` | `rw` | Hub data |
| **`beszel-agent`** | `/var/run/docker.sock` | `/var/run/docker.sock` | `ro` | Container metrics |
| | `${DOCKER_DATA_DIR}/beszel_agent` | `/var/lib/beszel-agent` | `rw` | Agent fingerprint |
| **`dockge`** | `/var/run/docker.sock` | `/var/run/docker.sock` | `rw` | Stack control |
| | `${DOCKER_DATA_DIR}/dockge` | `/app/data` | `rw` | Stacks DB |
| | `/opt/stacks` | `/opt/stacks` | `rw` | `DOCKGE_STACKS_DIR` |
| **`uptime-kuma`** | `${DOCKER_DATA_DIR}/uptime-kuma` | `/app/data` | `rw` | `kuma.db` |
| **`homarr`** | `/var/run/docker.sock` | `/var/run/docker.sock` | `ro` | Container discovery |
| | `${DOCKER_CONFIG_DIR}/homarr` | `/appdata` | `rw` | Dashboard state |
| **`leafwiki`** | `${DOCKER_DATA_DIR}/leafwiki` | `/app/data` | `rw` | Wiki DB & markdown |
| **`kavita`** | `${DOCKER_CONFIG_DIR}/kavita` | `/config` | `rw` | Reader DB |
| | `${DOCKER_DATA_DIR}` | `/data` | `rw` | Library root |
| **`calibre`** | `${DOCKER_CONFIG_DIR}/calibre` | `/config` | `rw` | Desktop VM state |
| | `${DOCKER_DATA_DIR}/media/books` | `/books` | `rw` | E-book library |
| **`calibre-web`** | `${DOCKER_CONFIG_DIR}/calibre-web` | `/config` | `rw` | Web reader DB |
| | `${DOCKER_DATA_DIR}/media/books` | `/books` | `rw` | E-book library |
| **`homebox`** | `${DOCKER_DATA_DIR}/homebox` | `/data/` | `rw` | SQLite database (`homebox.db`) & photos (pending repair) |
| **`vaultwarden`** | `${DOCKER_CONFIG_DIR}/vaultwarden` | `/data/` | `rw` | Vault DB |
| **`n8n`** | `${DOCKER_CONFIG_DIR}/n8n` | `/home/node/.n8n` | `rw` | Workflows & credentials |
| | `${DOCKER_DATA_DIR}/n8n` | `/files` | `rw` | Workflow file I/O |
| **`homeassistant`** | `${DOCKER_CONFIG_DIR}/homeassistant` | `/config` | `rw` | Automations & history |
| | `/etc/localtime` | `/etc/localtime` | `ro` | Clock sync |
| | `/run/dbus` | `/run/dbus` | `ro` | Bluetooth / D-Bus |
| **`rclone`** | `${DOCKER_CONFIG_DIR}/rclone` | `/config/rclone` | `rw` | `rclone.conf`, `filter.txt` |
| | `${DOCKER_BASE_DIR}` | `/source` | `ro` | Backup source tree |
| | `${DOCKER_LOGS_DIR}` | `/logs` | `rw` | Sync logs |
| **`rclone-gui`** | `${DOCKER_CONFIG_DIR}/rclone` | `/config/rclone` | `rw` | Shared remote config |
| | `${DOCKER_BASE_DIR}` | `/source` | `ro` | Browse source tree |

`flaresolverr`, `paperless-gotenberg`, and `paperless-tika` declare no volumes.

---

## 4. Atomic Moves, Hardlinks & Symlink Architecture

### The Single-Mount Rule for *arr Suite
Standard container setups mount downloads at `/downloads` and media at `/movies` or `/tv`. Docker then treats them as separate filesystems. When Radarr or Sonarr imports a finished download, it runs a slow, I/O-heavy copy followed by a delete.

Sol mounts the entire host `${DOCKER_DATA_DIR}` (`/Users/vrg/Documents/Sol/data`) into Radarr, Sonarr, Bazarr, and Lidarr as `/data`:
- Downloads reside in `/data/torrents/...`
- Media libraries reside in `/data/media/...`
- Both paths share one container mount point on the same physical SSD, so the kernel performs **instant zero-copy atomic hardlinks and inode renames**.

### Dual Mount Staging on `qbittorrent` and `cross-seed`
Both download services now carry two mounts that point at the same host directory:

```yaml
- ${DOCKER_DATA_DIR}/torrents:/downloads   # current save path and linkDirs root
- ${DOCKER_DATA_DIR}:/data                 # unified root (exposes /data/torrents and /data/media)
```

- `/downloads/<x>` and `/data/torrents/<x>` resolve to the same inode, so no data moves during migration.
- Migration path: repoint qBittorrent save paths and cross-seed `linkDirs` from `/downloads/...` to `/data/torrents/...` per torrent or category. Then remove the `/downloads` mount after all torrents report the new path.
- `scripts/test_cross_seed.sh` checks the unified layout. When both `/data/torrents` and `/data/media` exist, it tests a cross-directory hardlink between them.

### Cross-Seeding Symlink Architecture
Cross-seeding searches multiple indexers for identical file payloads to seed across several private trackers.
- Internal downloads (`/downloads/cross-seed-links`) support hardlinks on the host APFS filesystem.
- External drives mounted through macOS (`/Volumes/PANOPTICON`, ExFAT) do not support hardlinks, and hardlinks across mount boundaries fail.
- **Architectural Solution:** As verified by `scripts/test_cross_seed.sh` and configured in `config/cross-seed/config.js`, Cross-Seed uses `linkType: "symlink"` into dedicated link folders:
  - `/downloads/cross-seed-links/`
  - `/external/cross-seed-links/`
- **Diagnostic Identity:** The script runs `docker exec -u "${PUID:-501}:${PGID:-20}" cross-seed`, so permission results match the daemon's real unprivileged identity (`user: "${PUID}:${PGID}"`) instead of root.

---

## 5. Disaster Recovery, Backup & Restore Strategy

`scripts/backup.sh` runs a three-step pipeline. It ends with a versioned rclone sync of server state to Microsoft OneDrive (`OneDrive:Sol`).

### Backup Pipeline (`scripts/backup.sh`)

| Step | Action | Output / Behavior |
| :--- | :--- | :--- |
| **0. Init** | `set -euo pipefail`, `cd` to Sol root, load `.env` through the safe `load_env` parser (handles quoted values such as `PAPERLESS_OCR_LANGUAGES="hin kan pan"` and single-quoted JSON, strips inline comments only on unquoted values) | `mkdir -p ./logs ./data/backups ./data/backups/sqlite`, log file `logs/backup_<YYYY-MM-DD_HH-MM-SS>.log` |
| **1a. Authentik Dump** | `docker exec authentik-postgresql pg_dump -U ${PG_USER:-authentik} ${PG_DB:-authentik} \| gzip` | Written to `authentik_db.sql.gz.tmp`, then `mv` to `data/backups/authentik_db.sql.gz`. Skipped if the container is not running. |
| **1b. Paperless Dump** | `docker exec paperless-db pg_dump -U ${PAPERLESS_DB_USER:-paperless} ${PAPERLESS_DB_NAME:-paperless} \| gzip` | `data/backups/paperless_db.sql.gz` with the same `.tmp` then `mv` pattern |
| **1c. SQLite Snapshots** | `find ./config ./data/arcane ./data/ignis -maxdepth 4` for `*.db`, `*.sqlite`, `*.sqlite3`, then `sqlite3 <db> ".timeout 5000" ".backup './data/backups/sqlite/<safe_name>'"` | Atomic online copy without the live `-wal` and `-shm` split. `safe_name` replaces `/` with `__`. Skipped if host `sqlite3` CLI is missing. |
| **2. Rclone Sync** | Native host `rclone sync . OneDrive:Sol --config ./config/rclone/rclone.conf --filter-from <filter> --backup-dir OneDrive:Sol-archive/<TIMESTAMP> --links -v --stats 30s --stats-one-line` | Fallback when host rclone or `rclone.conf` is missing: `docker compose --profile ops run --rm rclone sync /source OneDrive:Sol ...` with the same flags |
| **3. Cleanup** | `find ./logs -name "backup_*.log" -mtime +30 -delete` | Prints archive location and log path |

> [!IMPORTANT]
> `--backup-dir` moves every file that the sync would overwrite or delete into `OneDrive:Sol-archive/<TIMESTAMP>`. Each run therefore keeps a point-in-time archive of changed and deleted files instead of discarding them.

### Data Classification: Critical vs. Excluded

```
                                  +---------------------------------------+
                                  |    Sol Server Host Directory Root     |
                                  +-------------------+-------------------+
                                                      |
                         +----------------------------+----------------------------+
                         |                                                         |
                         v                                                         v
          [ CRITICAL BACKUP TARGETS ]                               [ EXCLUDED / TRANSIENT DATA ]
          (Synchronized to OneDrive:Sol)                            (Filtered out via filter.txt)
          ---------------------------------                         ---------------------------------
          - Database Dumps: data/backups/** (incl. sqlite/)         - Live PG Clusters: data/authentik/**
          - Preshow Media: data/media/preshows/**                   - Live PG Clusters: data/paperless/db/**
          - .torrent & .fastresume in data/torrents/**              - Redis Queue: data/paperless/redis/**
          - .torrent & .fastresume in config/qbittorrent/**         - SQLite WAL & SHM: **/*-wal, **/*-shm
          - Cross-Seed Cache: config/cross-seed/torrent_cache/**    - Bulk Media: data/media/** (except preshows)
          - All Compose Stacks (compose/*.yml)                      - Torrent Payloads: data/torrents/** (except metafiles)
          - Master Orchestrator: docker-compose.yml                 - Jellyfin Cache: config/jellyfin/cache/**
          - Environment Secrets: .env, .env.example                 - Jellyfin Transcodes: config/jellyfin/data/transcodes/**
          - Caddy Ingress: Caddyfile, ports.json                    - Jellyfin Metal: config/jellyfin_metal/cache/**, log/**
          - Paperless Documents: data/paperless/media/**            - Service Logs: logs/**, *.log, config/**/logs/**
          - Paperless Index & Scripts: data/paperless/data/**       - *arr Artwork: config/**/MediaCover/**
          - Obsidian Notes: data/ignis/vaults/**                    - Prowlarr Definitions: config/prowlarr/Definitions/**
          - SQLite DB files (config/**, data/arcane, data/ignis)    - ntfy Cache: data/ntfy/var/cache/**
          - All Servarr DBs (Radarr, Sonarr, Prowlarr, Bazarr)      - OS Metadata: .DS_Store, ._*, .Spotlight-V100/**, .Trashes/**
          - Static Web Frontends (web/**) & Scripts (scripts/**)    - Temp & Sockets: *.tmp, *.temp, *.swp, *.sock
          - coder/main.tf, docs/system_state/**                     - Legacy & Build: _backup_pre_refactor/**, docs/archive/**, node_modules/**, .terraform/**
```

### Complete Rclone Filter Rules (`config/rclone/filter.txt.example`)

Rclone evaluates rules top to bottom, and the first matching rule wins. `scripts/backup.sh` uses `config/rclone/filter.txt` if present. It falls back to the tracked `filter.txt.example` (`/source/config/rclone/filter.txt.example` inside the container). `scripts/restore.sh` seeds `filter.txt` from the example when it is missing.

```
# --- 1. OS & Filesystem Metadata Exclusions ---
- .DS_Store
- ._*
- .Spotlight-V100/**
- .Trashes/**
- *.tmp
- *.temp
- *.swp
- *.sock

# --- 2. Live Database Cluster & WAL Lock Exclusions ---
# Live PostgreSQL data directories are excluded because scripts/backup.sh
# generates consistent logical dumps in data/backups/*.sql.gz.
- data/authentik/**
- data/paperless/db/**
- data/paperless/redis/**

# Live SQLite Write-Ahead Logs (-wal) and Shared Memory (-shm) files
# are excluded because scripts/backup.sh creates atomic online snapshots
# via 'sqlite3 .backup' in data/backups/sqlite/ before rclone runs.
- **/*-wal
- **/*-shm

# --- 3. Ephemeral Caches, Logs & Transcode Buffers ---
- logs/**
- *.log
- config/jellyfin/cache/**
- config/jellyfin/data/transcodes/**
- config/jellyfin_metal/cache/**
- config/jellyfin_metal/log/**
- config/**/logs/**
- config/**/MediaCover/**
- config/prowlarr/Definitions/**
- data/ntfy/var/cache/**

# --- 4. Priority Inclusions (Preshows, Database Dumps & Torrent Metafiles) ---
+ data/backups/**
+ data/media/preshows/**
+ data/torrents/**/*.torrent
+ data/torrents/**/*.fastresume
+ config/qbittorrent/**/*.torrent
+ config/qbittorrent/**/*.fastresume
+ config/cross-seed/torrent_cache/**

# --- 5. Bulk Media & Torrent Payload Exclusions ---
- data/media/**
- data/torrents/**

# --- 6. Legacy & Build Exclusions ---
- _backup_pre_refactor/**
- docs/archive/**
- node_modules/**
- .terraform/**

# --- 7. Default Rule: Include All Remaining Config, State & Repo Files ---
+ **
```

> [!NOTE]
> Rule changes from the previous filter: the live PostgreSQL clusters and SQLite `-wal`/`-shm` files are now excluded (dumps and snapshots replace them). Jellyfin `metadata/**` and `trickplay/**`, and code-server `extensions/**`, are no longer excluded, so they now sync. `docs/archive/**` and `.terraform/**` are newly excluded.

### Disaster Recovery Playbook (`scripts/restore.sh`)

| Step | Action |
| :--- | :--- |
| **1. Cloud Pull** | `rclone copy OneDrive:Sol <SOL_ROOT> --links -v --stats 15s`, with `--config ./config/rclone/rclone.conf` if present (else confirms use of global rclone config). `--dry-run` adds `--dry-run` and exits after this step. `--skip-cloud-pull` skips it. Optional arrays expand with the Bash 3.2 `set -u` safe form `${arr[@]+"${arr[@]}"}`. |
| **2. Structure & Secrets** | `mkdir -p ./logs ./data/backups ./data/backups/sqlite ./data/media/preshows ./data/torrents ./data/paperless/consume ./data/paperless/scripts ./config/rclone`. Seeds `filter.txt` from `filter.txt.example`. Creates `.env` from `.env.example` if missing. Loads `.env` with the safe `load_env` parser. `chmod +x ./scripts/*.sh ./scripts/*.py`. |
| **3a. SQLite Restore** | For each file in `data/backups/sqlite/`, decodes `__` back to `/` and copies it into place only if the destination database is missing. |
| **3b. PostgreSQL Import** | Imports when `--restore-dbs` is set, or when `--start-stack` is set and the cluster lacks `PG_VERSION`. Starts the DB container, polls `pg_isready` up to 30 seconds, then runs `gunzip -c ./data/backups/<db>.sql.gz \| docker exec -i <container> psql -U <user> -d <db>`. |
| **4. Validate & Start** | `docker compose -f docker-compose.yml config` syntax check. With `--start-stack`: `docker compose up -d` (24 active containers, no standby profile) and `docker compose ps`. |

In the event of total hardware loss, restore to a fresh machine with these commands:

```bash
# 1. Create/navigate to base directory on the new machine (copy rclone.conf into ./config/rclone/ first)
mkdir -p /Users/vrg/Documents/Sol && cd /Users/vrg/Documents/Sol

# 2. Pull the cloud backup and prepare the tree (preview first with --dry-run)
./scripts/restore.sh --dry-run
./scripts/restore.sh

# 3. Force PostgreSQL dump import and launch the active container ecosystem
./scripts/restore.sh --skip-cloud-pull --restore-dbs --start-stack

# 4. Relaunch native Jellyfin Metal (preserves restored jellyfin.db, no --reset)
python3 ./scripts/setup_jellyfin_metal.py
```
