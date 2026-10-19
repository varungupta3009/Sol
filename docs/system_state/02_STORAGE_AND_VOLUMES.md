# 02. Storage, Volumes & Persistence Topology

> **Scope:** Physical and virtual storage architecture, container volume bindings, cross-filesystem linking mechanisms, and the Two-Tier Disaster Recovery & Backup Strategy on `Sol`.  
> **Host Root:** `/Users/vrg/Documents/Sol` (`DOCKER_BASE_DIR`)  
> **External Storage Devices:** `/Volumes/PANOPTICON` (`EXTERNAL_DRIVE_00`, mounted), `/Volumes/PHOENIX` (`EXTERNAL_DRIVE_01`, standby)  
> **Tier 1 State Backup Targets (Backrest + Restic):** `/Volumes/PANOPTICON/backups/sol-restic` (`local-panopticon`) and `rclone:OneDrive:Sol-Restic` (`onedrive-cloud`)  
> **Tier 2 Blueprint Backup Target (GitHub):** `https://github.com/varungupta3009/Sol` (lean, zero-secret declarative IaC blueprint)  
> **Exclude Rules:** [`config/backrest/excludes.txt.example`](../../config/backrest/excludes.txt.example) (`config/backrest/excludes.txt`) and [`config/rclone/filter.txt.example`](../../config/rclone/filter.txt.example)  
> **Last Synced to Ground Truth:** 2026-10-19  

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

## 5. Two-Tier Disaster Recovery, Backup & Restore Strategy

Sol separates disaster recovery into two complementary tiers so that neither cloud storage nor Git history carries unnecessary bloat or exposed secrets:

| Tier | Target | Engine & Cadence | Purpose & Guarantees |
| :--- | :--- | :--- | :--- |
| **Tier 1: Full Server State Backup** | **1a. Local External Drive:** `/Volumes/PANOPTICON/backups/sol-restic` (`local-panopticon`)<br>**1b. Cloud Off-Site:** `rclone:OneDrive:Sol-Restic` (`onedrive-cloud`) | **Backrest (`v1.14.1`) + Restic (`0.19.1`)** + [`scripts/stage_db_backups.sh`](../../scripts/stage_db_backups.sh)<br>Local: twice daily (`03:00` & `15:00` IST)<br>OneDrive: daily (`03:30` IST) | Captures **100% of server state** in `/Users/vrg/Documents/Sol` (`.env` secrets, live PostgreSQL dumps, WAL-complete SQLite snapshots, `.torrent`/`.fastresume` files, Paperless PDFs, Obsidian vaults, Coder home volume, and the media symlink manifest) while excluding bulk media files, raw torrent payloads, logs, and regenerable caches. After a complete Mac wipe and restore (with media files present on disk), **100% of containers, databases, users, and configurations come back online identically to the moment of backup**. |
| **Tier 2: Declarative Blueprint Backup** | **GitHub Repository:** `varungupta3009/Sol` (`origin/main`) | **Jujutsu (`jj`) / Git**<br>On every architectural or configuration change | Tracks a **lean, zero-secret declarative blueprint** (`docker-compose.yml`, `compose/*.yml`, `Caddyfile`, `ports.json`, `.env.example`, `config/glance/**`, `config/qui/tracker_registry.json`, `config/auth/users.json`, `config/backrest/*.example`, `config/rclone/filter.txt.example`, `coder/main.tf`, `scripts/*`, and `docs/*`). Allows spinning up and configuring the entire architecture from scratch on a clean host without needing any runtime data volumes. |

---

### Tier 1 Pre-Backup Staging & Restic Pipeline ([`scripts/stage_db_backups.sh`](../../scripts/stage_db_backups.sh) & [`scripts/backup.sh`](../../scripts/backup.sh))

Because Backrest runs inside an isolated container without host Docker socket access, [`scripts/stage_db_backups.sh`](../../scripts/stage_db_backups.sh) executes on the macOS host (automatically via `com.vrg.sol.db-stage.plist` at `02:45` and `14:45` IST, and at Step 1 of [`scripts/backup.sh`](../../scripts/backup.sh)) to materialize crash-consistent database and volume artifacts in `./data/backups/` before Backrest snapshots `/userdata/sol`:

| Step | Action | Output / Behavior |
| :--- | :--- | :--- |
| **1. PostgreSQL Logical Dumps** | Dumps `paperless-db` (`paperless` and `airtrail` databases), `coder` (embedded PostgreSQL on `::1:43235`), and `authentik-postgresql` (if running) via `pg_dump --clean --if-exists \| gzip` | Written atomically via `.tmp` rename to `data/backups/paperless_db.sql.gz`, `data/backups/airtrail_db.sql.gz`, `data/backups/coder_db.sql.gz`, and `data/backups/authentik_db.sql.gz`. |
| **2. VirtioFS-Safe SQLite Snapshots** | Finds all `*.db`, `*.sqlite`, and `*.sqlite3` files across `./config` and `./data/{arcane,tinyauth,lldap,readeck,pocketbase,enclosed,ignis,ntfy,copyparty,homebox,beszel,leafwiki}` (excluding Servarr `logs.db`), copies `.db` + `-wal` (without `-shm`) to a local temp directory, and runs `sqlite3 .backup` | Produces single-file, WAL-checkpointed SQLite snapshots in `data/backups/sqlite/<path_with___>` without touching guest Linux VM `-shm` shared-memory files. |
| **3. Media & Cross-Seed Symlink Manifest** | Scans `./data/media`, `./data/torrents/{cross-seed-links,qui-links}`, and `/Volumes/PANOPTICON/{media,torrents/cross-seed-links,torrents/qui-links}` for all symbolic links | Exports `<link_path>\t<target_path>` to `data/backups/symlinks_manifest.tsv` (`391+` symlinks) so the entire media library symlink tree can be recreated without backing up multi-terabyte video files. |
| **4. Coder Workspace Volume Archive** | Archives the persistent Docker named volume `coder-*-home` (excluding `.cache`, `.cargo/registry`, `.rustup/toolchains`, and cached VSIXs) | Written atomically to `data/backups/coder_home.tar.gz`. |
| **5. Encrypted Restic Snapshot & Prune** | Backrest (`https://backrest.vrg.rocks`) and [`scripts/backup.sh`](../../scripts/backup.sh) run `restic backup /userdata/sol --exclude-file /config/excludes.txt` to `/repos/local-panopticon` and `rclone:OneDrive:Sol-Restic` | Deduplicated, AES-256/Poly1305 encrypted chunks with retention policy `7 daily / 4 weekly / 6 monthly` and automated weekly prune/check schedules. |

### Data Classification: Critical State (Included) vs. Bulk / Transient Fluff (Excluded)

```
                                  +---------------------------------------+
                                  |    Sol Server Host Directory Root     |
                                  +-------------------+-------------------+
                                                      |
                         +----------------------------+----------------------------+
                         |                                                         |
                         v                                                         v
          [ TIER 1: INCLUDED SERVER STATE ]                        [ EXCLUDED: MEDIA, LOGS & FLUFF ]
          (Snapshotted via Backrest/Restic)                        (Filtered via config/backrest/excludes.txt)
          ---------------------------------                        -------------------------------------------
          - Staged DB Dumps: data/backups/*.sql.gz                 - Bulk Media: data/media/{movies,tv,music,books,home-videos}
          - WAL-Complete SQLite: data/backups/sqlite/*             - Torrent Payloads: data/torrents/{movies,tv,books,music,temp,incomplete}
          - Symlink Tree: data/backups/symlinks_manifest.tsv       - Torrent Link Trees: data/torrents/{cross-seed-links,qui-links}
          - Coder Home Volume: data/backups/coder_home.tar.gz      - Live PG Clusters: data/authentik, data/paperless/db, config/coder/coderv2/postgres
          - Saved .torrent Files: data/torrents/files/**           - Live Redis Queue: data/paperless/redis
          - qBittorrent State: config/qbittorrent/BT_backup/**     - Live SQLite Journals & Log DBs: *-wal, *-shm, *.db-journal, logs.db*
          - Cinema Preshows: data/media/preshows/**                - Jellyfin Caches/Metadata/Trickplay: cache, temp, transcodes, trickplay, metadata
          - Paperless Archive: data/paperless/{media,data,scripts} - Servarr & Prowlarr Fluff: MediaCover, config/prowlarr/Definitions
          - Identity & Auth: data/lldap, data/tinyauth, config/auth- Static Upstream Bundles: web/{pdf,chef,draw,speed,tools} (rebuilt via sync_static_tools.sh)
          - App Data: data/{ignis,arcane,pocketbase,readeck,airtrail}- Node & Build Caches: quartz/{node_modules,public,.quartz-cache}, code-server/extensions
          - Personal Web & Quartz Source: web/{fam,scan,aysynbm,mi}- All Logs & OS Trash: logs, log, *.log*, .DS_Store, ._*, .Spotlight-V100, .Trashes
          - All Declarative IaC, Scripts, Docs & Live .env Secrets
```

### Complete Backrest / Restic Exclude Rules ([`config/backrest/excludes.txt.example`](../../config/backrest/excludes.txt.example))

Both Backrest plans (`sol-local-daily` and `sol-onedrive-cloud`) and [`scripts/backup.sh`](../../scripts/backup.sh) apply these exact exclude patterns when snapshotting `/userdata/sol`:

```text
# 1. Bulk Media & Raw Torrent Payloads (data/torrents/files & data/media/preshows are INCLUDED)
/userdata/sol/data/torrents/movies
/userdata/sol/data/torrents/tv
/userdata/sol/data/torrents/books
/userdata/sol/data/torrents/music
/userdata/sol/data/torrents/temp
/userdata/sol/data/torrents/incomplete
/userdata/sol/data/torrents/cross-seed-links
/userdata/sol/data/torrents/qui-links
/userdata/sol/data/media/movies
/userdata/sol/data/media/tv
/userdata/sol/data/media/music
/userdata/sol/data/media/books
/userdata/sol/data/media/home-videos

# 2. Live Relational Database & Redis Data Directories (Backed up via data/backups/*.sql.gz)
/userdata/sol/data/authentik
/userdata/sol/data/paperless/db
/userdata/sol/data/paperless/redis
/userdata/sol/config/coder/coderv2/postgres

# 3. Live SQLite WAL / SHM Journals & Log DBs (Atomic snapshots live in data/backups/sqlite/)
*-wal
*-shm
*.db-journal
logs.db
logs.db-wal
logs.db-shm

# 4. Backrest & Restic Local Cache
/userdata/sol/data/backrest/cache

# 5. Reproducible Node Modules, Static Tool Bundles & Transcode/Trickplay/Metadata Caches
/userdata/sol/quartz/node_modules
/userdata/sol/quartz/public
/userdata/sol/quartz/.quartz-cache
/userdata/sol/web/pdf
/userdata/sol/web/chef
/userdata/sol/web/draw
/userdata/sol/web/speed
/userdata/sol/web/tools
/userdata/sol/web/fam_backup_20260913
/userdata/sol/config/jellyfin/cache
/userdata/sol/config/jellyfin/data/temp
/userdata/sol/config/jellyfin/data/transcodes
/userdata/sol/config/jellyfin/data/data/trickplay
/userdata/sol/config/jellyfin/data/metadata
/userdata/sol/config/jellyfin_metal/cache
/userdata/sol/config/jellyfin_metal/data/temp
/userdata/sol/config/jellyfin_metal/data/transcodes
/userdata/sol/config/jellyfin_metal/data/data/trickplay
/userdata/sol/config/jellyfin_metal/data/metadata
/userdata/sol/config/plex/Library/Application Support/Plex Media Server/Cache
/userdata/sol/config/plex/Library/Application Support/Plex Media Server/Codecs
/userdata/sol/config/plex/Library/Application Support/Plex Media Server/Crash Reports
/userdata/sol/config/plex/Library/Application Support/Plex Media Server/Diagnostics
/userdata/sol/config/plex/Library/Application Support/Plex Media Server/Logs
/userdata/sol/config/plex/Library/Application Support/Plex Media Server/Media
/userdata/sol/config/plex/Library/Application Support/Plex Media Server/Metadata
/userdata/sol/config/plex/Library/Application Support/Plex Media Server/Plug-in Support/Caches
/userdata/sol/config/code-server/extensions
/userdata/sol/config/code-server/.cache
/userdata/sol/config/code-server/Library/Caches
/userdata/sol/config/prowlarr/Definitions
/userdata/sol/data/ntfy/var/cache
/userdata/sol/.hist
/userdata/sol/priv/.hist
/userdata/sol/_backup_pre_refactor
/userdata/sol/docs/archive
MediaCover
.terraform

# 6. Ephemeral Container & Host Logs
/userdata/sol/logs
logs
log
Logs
*.log
*.log.*

# 7. macOS Metadata & Temporary Files
.DS_Store
._*
.Spotlight-V100
.Trashes
Thumbs.db
*.tmp
*.temp
*.swp
*.sock
```

### Bare-Metal Disaster Recovery Playbook ([`scripts/restore.sh`](../../scripts/restore.sh))

| Step | Action |
| :--- | :--- |
| **1. Snapshot Pull** | Restores the latest (or specified `--snapshot <id>`) Restic snapshot from `/Volumes/PANOPTICON/backups/sol-restic` (`--from-local`, default when mounted) or `rclone:OneDrive:Sol-Restic` (`--from-cloud`). Supports `--dry-run` to list snapshots without modifying disk, and `--legacy-rclone` as a fallback for older `OneDrive:Sol` mirrors. |
| **2. Structure, Templates & Static Tools** | Creates required directories, seeds `config/backrest/excludes.txt`, `config/backrest/config.json`, and `config/rclone/filter.txt` from their `.example` templates if missing, and runs [`scripts/sync_static_tools.sh`](../../scripts/sync_static_tools.sh) to repopulate `web/{tools,chef,pdf,speed,draw,mi}`. |
| **3. Symlink Tree Reconstruction** | Reads `data/backups/symlinks_manifest.tsv` and recreates every missing relative media and cross-seed symlink across `./data/media`, `/Volumes/PANOPTICON/media`, and `cross-seed-links` / `qui-links`. |
| **4. SQLite, PostgreSQL & Coder Volume Restore** | Restores WAL-complete SQLite snapshots from `data/backups/sqlite/`, imports `paperless_db.sql.gz`, `airtrail_db.sql.gz`, and `authentik_db.sql.gz` into PostgreSQL, restores `coder_home.tar.gz` into the `coder-*-home` Docker volume, and validates + starts the 29 active containers (`--start-stack`). |

In the event of a total Mac reset, restore the entire server with four commands:

```bash
# 1. Clone the Tier 2 declarative blueprint from GitHub (and place rclone.conf in config/rclone/ if restoring from OneDrive)
git clone https://github.com/varungupta3009/Sol.git /Users/vrg/Documents/Sol && cd /Users/vrg/Documents/Sol

# 2. Preview available Tier 1 Restic snapshots (auto-selects local PANOPTICON or pass --from-cloud for OneDrive)
./scripts/restore.sh --dry-run

# 3. Restore latest Restic snapshot, rebuild PostgreSQL & SQLite DBs, recreate all media symlinks, and start all 29 active services
./scripts/restore.sh --restore-dbs --start-stack

# 4. Relaunch native Jellyfin Metal (preserves restored jellyfin.db without --reset)
python3 ./scripts/setup_jellyfin_metal.py
```
