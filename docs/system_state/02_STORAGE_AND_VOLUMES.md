# 02. Storage, Volumes & Persistence Topology

> **Scope:** Detailed physical and virtual storage architecture, container volume bindings, cross-filesystem linking mechanisms, and disaster recovery backup classifications on `Sol`.  
> **Host Root:** `/Users/vrg/Documents/Sol`  
> **External Storage Devices:** `/Volumes/PANOPTICON`, `/Volumes/PHOENIX`  
> **Backup Remote Target:** `OneDrive:Sol` via Rclone  

---

## 1. Storage Taxonomy & Physical Hierarchy

The storage architecture of Sol separates high-frequency transactional data (SQLite/PostgreSQL databases, configs, document OCR pipelines) residing on the internal fast SSD from multi-terabyte bulk media and downloads distributed across external mass drives.

```
/Users/vrg/Documents/Sol (Internal SSD Base)
├── compose/                     --> Modular domain Compose files (core, media, download, etc.)
├── config/                      --> Container runtime configurations, XML configs, SQLite DBs
├── data/                        --> Application state, document storage, local media & downloads
│   ├── backups/                 --> Compressed live PostgreSQL database dumps (.sql.gz)
│   ├── media/                   --> Internal fast SSD media storage (preshows, movies, tv, music, books)
│   ├── torrents/                --> Active download payload staging & symlink trees
│   │   └── files/               --> Saved .torrent files repository
│   ├── paperless/               --> Document archives, media assets, OCR databases, hooks
│   ├── authentik/               --> PostgreSQL 16 relational auth cluster
│   ├── arcane/                  --> Arcane management SQLite database
│   ├── homebox/                 --> Homebox asset database and uploaded receipt images
│   ├── ignis/                   --> Obsidian vaults and sync state
│   ├── leafwiki/                --> LeafWiki SQLite databases and document roots
│   └── caddy/                   --> TLS ACME certificates, runtime storage, and locks
├── web/                         --> Static web frontends (/fam, /scan, /aysynbm, /mind)
├── scripts/                     --> Automation runners (backup.sh, restore.sh, test_cross_seed.sh)
├── quartz/                      --> Quartz digital garden source and public static build
├── docs/                        --> System architecture documentation and archived stacks
├── logs/                        --> Operational audit logs, rclone backup logs
└── /Volumes/PANOPTICON (Ext)    --> Mass storage media repository (Movies, TV, Music, Downloads)
```

---

## 2. Master Container Mount Matrix

The following table provides an exhaustive index of all directory and socket mounts across the Sol container ecosystem.

| Service | Host Source Path | Container Mount Path | Mode | Classification / Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **`caddy`** | `./Caddyfile` | `/etc/caddy/Caddyfile` | `ro` | Edge Reverse Proxy Rules |
| | `${DOCKER_DATA_DIR}/caddy` | `/data` | `rw` | Let's Encrypt TLS certs & ACME keys |
| | `${DOCKER_CONFIG_DIR}/caddy` | `/config` | `rw` | Caddy runtime JSON state |
| | `${DOCKER_BASE_DIR}/quartz/public` | `/mind` | `ro` | Quartz Digital Garden static HTML |
| | `${DOCKER_BASE_DIR}/web/fam` | `/fam` | `ro` | Family Data Vault static frontend |
| | `${DOCKER_BASE_DIR}/web/scan` | `/scan` | `ro` | Homebox mobile scanner PWA |
| | `${DOCKER_BASE_DIR}/web/aysynbm` | `/aysynbm` | `ro` | Async Bookmark Manager static HTML |
| **`authentik-postgresql`** | `${DOCKER_DATA_DIR}/authentik` | `/var/lib/postgresql/data` | `rw` | Relational Auth Database (Postgres 16) |
| **`authentik-server`** | `${DOCKER_CONFIG_DIR}/authentik/data` | `/data` | `rw` | Authentik media & static cache |
| | `${DOCKER_CONFIG_DIR}/authentik/custom-templates` | `/templates` | `rw` | Custom Jinja/HTML outpost templates |
| **`authentik-worker`** | `/var/run/docker.sock` | `/var/run/docker.sock` | `rw` | Docker API for Outpost integrations |
| | `${DOCKER_CONFIG_DIR}/authentik/data` | `/data` | `rw` | Authentik worker media & cache |
| | `${DOCKER_CONFIG_DIR}/authentik/certs` | `/certs` | `rw` | Ingress certificates & signing keys |
| | `${DOCKER_CONFIG_DIR}/authentik/custom-templates` | `/templates` | `rw` | Custom Jinja/HTML templates |
| **`glance`** | `${DOCKER_CONFIG_DIR}/glance/config` | `/app/config` | `rw` | Dashboard configuration (`glance.yml`) |
| | `${DOCKER_CONFIG_DIR}/glance/assets` | `/app/assets` | `rw` | Custom branding, icons (`sol.svg`) |
| | `/var/run/docker.sock` | `/var/run/docker.sock` | `ro` | Container status monitoring |
| | `/etc/timezone` | `/etc/timezone` | `ro` | Host timezone sync |
| | `/etc/localtime` | `/etc/localtime` | `ro` | Host local clock sync |
| **`arcane`** | `/var/run/docker.sock` | `/var/run/docker.sock` | `rw` | Host Docker container & stack orchestration |
| | `${DOCKER_DATA_DIR}/arcane` | `/app/data` | `rw` | SQLite DB (`arcane.db`), stack templates |
| **`jellyfin`** | `${DOCKER_CONFIG_DIR}/jellyfin` | `/config` | `rw` | Media database, plugins, transcode cache |
| | `${DOCKER_DATA_DIR}/media` | `/media/internal` | `rw` | Fast SSD internal media repository |
| | `${EXTERNAL_DRIVE_00}` | `/media/external` | `rw` | Mass storage external media (`/Volumes/PANOPTICON`) |
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
| **`qbittorrent`** | `${DOCKER_CONFIG_DIR}/qbittorrent` | `/config` | `rw` | qBittorrent.conf, scripts, fastresume data |
| | `${DOCKER_DATA_DIR}/torrents` | `/downloads` | `rw` | In-progress & completed torrent payloads |
| | `${EXTERNAL_DRIVE_00}` | `/external` | `rw` | Direct seeding on external mass drive |
| **`cross-seed`** | `${DOCKER_CONFIG_DIR}/cross-seed` | `/config` | `rw` | Daemon config (`config.js`), cross-seed DB |
| | `${DOCKER_DATA_DIR}/torrents` | `/downloads` | `rw` | Internal torrent linking root |
| | `${EXTERNAL_DRIVE_00}` | `/external` | `rw` | External torrent linking root |
| **`paperless-webserver`** | `${DOCKER_CONFIG_DIR}/paperless` | `/usr/src/paperless/config` | `rw` | Paperless runtime configuration |
| | `${DOCKER_DATA_DIR}/paperless/data` | `/usr/src/paperless/data` | `rw` | Search index, classification models |
| | `${DOCKER_DATA_DIR}/paperless/media` | `/usr/src/paperless/media` | `rw` | Stored PDF documents, archives & thumbnails |
| | `${DOCKER_DATA_DIR}/paperless/export` | `/usr/src/paperless/export` | `rw` | Document export target |
| | `${DOCKER_DATA_DIR}/paperless/consume` | `/usr/src/paperless/consume` | `rw` | Drop directory for incoming scan ingestion |
| | `${DOCKER_DATA_DIR}/paperless/scripts` | `/usr/src/paperless/scripts` | `rw` | Pre/Post consumption hooks & passwords |
| **`paperless-broker`** | `${DOCKER_DATA_DIR}/paperless/redis` | `/data` | `rw` | Redis persistence dump (`dump.rdb`) |
| **`paperless-db`** | `${DOCKER_DATA_DIR}/paperless/db` | `/var/lib/postgresql/data` | `rw` | Paperless PostgreSQL 17 database cluster |
| **`ignis`** | `${DOCKER_DATA_DIR}/ignis/vaults` | `/vaults` | `rw` | Obsidian markdown vaults |
| | `${DOCKER_DATA_DIR}/ignis/data` | `/app/data` | `rw` | Ignis application database & settings |
| | `${DOCKER_DATA_DIR}/ignis/obsidian` | `/app/obsidian-app` | `rw` | Obsidian core application data |
| **`code-server`** | `${DOCKER_CONFIG_DIR}/code-server` | `/config` | `rw` | VSCode settings, extensions, user history |
| | `${DOCKER_BASE_DIR}` | `/Server` | `rw` | Host Sol repository root |
| **`coder`** | `/var/run/docker.sock` | `/var/run/docker.sock` | `rw` | Terraform Docker container orchestration |
| | `${DOCKER_CONFIG_DIR}/coder` | `/home/coder/.config` | `rw` | Coder database, sessions, certificates |
| | `${DOCKER_BASE_DIR}` | `/Sol` | `rw` | Host Sol repository root |
| **`copyparty`** | `${DOCKER_CONFIG_DIR}/copyparty` | `/cfg:z` | `rw` | `copyparty.conf`, salts, session DB |
| | `${DOCKER_DATA_DIR}/copyparty` | `/w/copyparty:z` | `rw` | Public/authenticated user upload volume |
| | `${DOCKER_DATA_DIR}/media` | `/w/media:z` | `rw` | Internal media file browser mount |
| | `${DOCKER_DATA_DIR}/torrents` | `/w/torrents:z` | `rw` | Torrent storage file browser mount |
| | `${EXTERNAL_DRIVE_00}` | `/w/external:z` | `rw` | External drive file browser mount |
| **`homebox`** | `${DOCKER_DATA_DIR}/homebox` | `/data/` | `rw` | SQLite database (`homebox.db`) & photos |
| **`ntfy`** | `${DOCKER_DATA_DIR}/ntfy/var/cache/ntfy`| `/var/cache/ntfy` | `rw` | Persistent message queue cache & attachments |
| | `${DOCKER_CONFIG_DIR}/ntfy/etc/ntfy` | `/etc/ntfy` | `rw` | `server.yml` configuration directory |

---

## 3. Atomic Moves, Hardlinks & Symlink Architecture

### The Single-Mount Rule for *arr Suite
In standard container setups, mounting downloads to `/downloads` and media to `/movies` or `/tv` causes Docker to treat them as separate virtual filesystems. When Radarr or Sonarr imports a finished download, it executes a slow, I/O-heavy file copy followed by a delete.

On Sol, this is optimized by mounting the entire host `${DOCKER_DATA_DIR}` (`/Users/vrg/Documents/Sol/data`) into Radarr, Sonarr, Bazarr, and Lidarr as `/data`:
- Downloads reside in `/data/torrents/...`
- Media libraries reside in `/data/media/...`
- Because both paths exist on the identical container mount point on the same physical SSD, the Linux kernel performs **instantaneous zero-copy atomic hardlinks and inode renames**.

### Cross-Seeding Symlink Architecture
Cross-seeding searches multiple indexers for identical file payloads to seed across several private trackers simultaneously.
- When cross-seeding internal downloads (`/downloads/cross-seed-links`), hardlinks are physically supported on the host APFS filesystem.
- When cross-seeding across external drives mounted via macOS (`/Volumes/PANOPTICON`), hardlinks across mount boundaries fail.
- **Architectural Solution:** As verified in `scripts/test_cross_seed.sh` and configured in `config/cross-seed/config.js`, Cross-Seed uses `linkType: "symlink"` pointing into dedicated link folders:
  - `/downloads/cross-seed-links/`
  - `/external/cross-seed-links/`

---

## 4. Disaster Recovery, Backup & Complete Restore Strategy

Sol utilizes an automated cloud backup pipeline (`scripts/backup.sh`) backed by an **Rclone** filter rule engine (`config/rclone/filter.txt`) that synchronizes all essential server state directly to Microsoft OneDrive (`OneDrive:Sol`).

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
          - All .torrent and .fastresume Files (Everywhere)         - Bulk Video: data/media/movies/**
          - All Compose Stacks (compose/*.yml)                      - Bulk TV: data/media/tv/**
          - Master Orchestrator: docker-compose.yml                 - Bulk Music & E-Books
          - Environment Secrets: .env, .env.example                 - Torrent Payload Chunks & Video Dumps
          - Caddy Ingress: Caddyfile, ports.json                    - Jellyfin Metadata: config/jellyfin/data/metadata/**
          - Preshow Media: data/media/preshows/**                   - Jellyfin Trickplay: config/jellyfin/data/data/trickplay/**
          - Database Dumps: data/backups/*.sql.gz                   - Code-Server Binaries: config/code-server/extensions/**
          - Paperless Documents: data/paperless/media/**            - Paperless Redis Queue: data/paperless/redis/**
          - Paperless Index & Scripts: data/paperless/data/**       - Quartz Node Modules: quartz/node_modules/**
          - Obsidian Notes: data/ignis/vaults/**                    - System Logs & Caches: **/logs/**, **/.cache/**, *.tmp
          - Homebox & Arcane SQLite Databases                       - OS Metadata & Sockets: .DS_Store, **/*.sock
          - All Servarr DBs (Radarr, Sonarr, Prowlarr, Bazarr)      - Local Pre-Refactor Snapshot: _backup_pre_refactor/**
          - Static Web Frontends (web/**) & Scripts (scripts/**)
```

### Complete Rclone Filter Rules (`config/rclone/filter.txt`)
```
# --- 1. Special Inclusions (Must precede exclusions) ---
+ **/*.torrent
+ **/*.fastresume
+ config/qbittorrent/qBittorrent/BT_backup/**
+ config/cross-seed/torrent_cache/**
+ data/torrents/files/*.torrent
+ data/media/preshows/**
+ config/code-server/data/User/**
+ config/code-server/*.yaml
+ config/code-server/*.json

# --- 2. Bulk Media & Torrent Payload Exclusions ---
- data/media/movies/**
- data/media/tv/**
- data/media/music/**
- data/media/books/**
- data/torrents/**

# --- 3. Container Caches & Ephemeral State ---
- config/jellyfin/data/metadata/**
- config/jellyfin/data/data/trickplay/**
- config/jellyfin/data/transcodes/**
- config/jellyfin/data/temp/**
- config/jellyfin/cache/**
- config/code-server/extensions/**
- config/code-server/.cache/**
- data/paperless/redis/**
- quartz/node_modules/**
- quartz/.github/**
- quartz/docs/**
- quartz/package-lock.json
- _backup_pre_refactor/**

# --- 4. System Trash, Ephemeral Logs, Sockets & Caches ---
- .DS_Store
- **/._*
- Thumbs.db
- **/*.tmp
- **/*.temp
- **/*.sock
- **/.Trash/**
- **/node_modules/**
- **/log/**
- **/logs/**
- **/*.log
- **/logs.db*
- **/UpdateLogs/**
- **/cache/**
- **/.cache/**

# --- 5. Catch-All Inclusion ---
+ **
```

### Disaster Recovery Playbook (`scripts/restore.sh`)

In the event of total hardware loss, restoring the entire server to a fresh machine requires only three commands:

```bash
# 1. Clone/navigate to base directory on the new machine
mkdir -p /Users/vrg/Documents/Sol && cd /Users/vrg/Documents/Sol

# 2. Run the automated recovery script
./scripts/restore.sh

# 3. Launch the complete container ecosystem
docker compose up -d
```
