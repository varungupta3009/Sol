# Sol Home Server (`dash.vrg.rocks`): Complete Historical Archaeology & Evolution (2018 to October 2026)

> **Target Host:** `dash.vrg.rocks` (Apple MacBook Pro 14-inch, 2021, Apple M1 Pro, 10-core CPU, 16 GB Unified Memory, macOS Tahoe 26.2 `25C56`, `/Users/vrg/Documents/Sol`)
> **Repository:** `github.com:varungupta3009/Sol.git`
> **Last Updated:** 2026-10-20

---

## 1. Executive Summary

Although the Git and Jujutsu repository in `/Users/vrg/Documents/Sol` was initialized on **2026-08-22** (`63f7fce`), forensic excavation across `/Users/vrg/Documents/Sol/docs/archive/*`, macOS APFS and ExFAT inode birth timestamps (`stat -f "%SB"`), SQLite and PostgreSQL primary keys (`?immutable=1`), and qBittorrent Bencode `.fastresume` files establishes that **Sol was created on 2025-05-02 at 08:11:53 IST** under the directory name `/Users/vrg/Documents/Home Server`, backed by external media directories dating back to **2018-10-14**.

Over 18 months, the server evolved through four distinct architectural eras:

1. **Era 1 (May 2 to June 15, 2025):** Genesis on M1 Pro macOS (`Home Server`), Plex Media Server, Overseerr, Authelia + Redis, Nginx Proxy Manager to Caddy migration, `*.hyd.vrg.rocks` to `*.vrg.rocks` domain cutover, Homarr, Syncthing, and the initial Servarr + qBittorrent stack.
2. **Era 2 (June 16 to December 31, 2025):** Open-source media and document cutover from Plex + Overseerr to **Jellyfin + Jellyseerr** (`2025-06-16` / `2025-06-19`), **Paperless-ngx** deployment (`2025-07-07`), **Quettamind** Quartz digital garden (`2025-07-25`), Beszel + Uptime Kuma + Dockge (`2025-07-26`), Copyparty (`2025-09-07`), Vaultwarden (`2025-10-06`), rclone OneDrive backups (`2025-10-19`), Homebox (`2025-12-01`), Paperless-AI (`2025-12-02`), and Cross-Seed (`2025-12-15`).
3. **Era 3 (January to September 2026):** Adoption of **ntfy** (`2026-01-17`), **Glance** + custom `sol.svg` (`2026-01-18`), **Arcane** (`2026-01-30`), **Coder** cloud workspaces (`2026-01-31`), static web PWAs (`scan`, `fam`, `aysynbm`), the `/Volumes/PANOPTICON` 2 TB ExFAT drive (`2026-05-09`), `qbit_manage` (`2026-05-10`), cutover from Authelia to **Authentik** (`2026-07-21`), the 8-file modular `compose/*.yml` refactor (`2026-08-17`), native **Jellyfin Metal** VideoToolbox (`2026-08-22`), Git/Jujutsu initialization (`2026-08-22`), and migration from Jellyseerr to unified **Seerr v3.5.0** (`2026-09-13`).
4. **Era 4 (October 17 to 20, 2026):** Cross-family `/double-agent` audit, `profiles: ["standby"]` formalization, **Byparr** replacing FlareSolverr, **Option A** zero-copy ExFAT relative symlink architecture (`torrent_finished.py` + `arr_symlink_dedupe.sh`, reclaiming `111.4 GiB` SSD), `postgres:17-alpine` migration, **Qui v1.32.0** replacing `cross-seed` + `qbit_manage` + `flood` (26-tracker registry, 10 FUP bandwidth rules, 150 tagged torrents), **Wave 1** 6-app Zero-Container Static Suite (`tools`, `chef`, `pdf`, `speed`, `draw`, `mi`), **Wave 2** deletion of 13 legacy and superseded services (`dockge`, `uptime-kuma`, `homarr`, `qbit_manage`, `flood`, `calibre`, `calibre-web`, `rclone-gui`, `authentik-*`, `flaresolverr`, `cross-seed`), **Wave 3** lean containers (`readeck`, `enclosed`, `pocketbase`, `airtrail`), **Unified Identity Spine** (`tinyauth` v5.2.0 0-click Google OAuth/OIDC + `lldap` + `<50ms` `identity_sync.py`), **2-Tier Disaster Recovery** (`Backrest` + `Restic` to PANOPTICON and OneDrive + LaunchAgents), and the **October 20, 2026 31-Agent Swarm Audit** bringing all **29 active containers** to `(healthy)`.

---

## 2. Pre-Server External Media Origins (2018 to 2023)

Before Sol existed as a containerized server, Varun curated a personal film and television archive on external storage (originally mounted as `/Volumes/Backup Plus/Media Drive` and later consolidated onto `/Volumes/PANOPTICON`):

| Directory / Artifact | Birth Timestamp (IST) | Forensic Source | Historical Significance |
| :--- | :--- | :--- | :--- |
| `/Volumes/PANOPTICON/Movies` | `2018-10-14 15:47:59` | `stat -f "%SB"` on `/Volumes/PANOPTICON/Movies` | Oldest surviving directory in the Sol ecosystem and origin of Varun's personal movie library (~7 years prior to Sol). |
| `/Volumes/PANOPTICON/TV Shows` | `2023-04-03 20:59:48` | `stat -f "%SB"` on `/Volumes/PANOPTICON/TV Shows` | Origin of the external TV Shows library. |
| `/Volumes/PANOPTICON/Pre-Show` | `2023-05-27 21:26:47` | `stat -f "%SB"` on `/Volumes/PANOPTICON/Pre-Show` | Custom cinema pre-show bumpers and trailers collection (`433 MB`). |
| `com.plexapp.plugins.library.db` schema | `2023-05-10 02:27:05 UTC` | `MIN(created_at)` in `metadata_items` (`config/plex/...`) | Base Plex library template epoch carried into the May 2025 Plex installation. |

---

## 3. Era 1: Genesis on M1 Pro macOS (May 2 to June 15, 2025)

### 3.1 Day 1 (`2025-05-02`): Birth of `/Users/vrg/Documents/Home Server`
Forensic shell history (`docs/archive/history-250918.txt` lines 1413 to 1455) and APFS directory birth timestamps (`stat -f "%SB"`) reconstruct the creation of the server on **May 2, 2025**:

- **`2025-05-02 08:11:53 IST`:** Root `docker-compose.yml` created inside `/Users/vrg/Documents/Home Server` (later renamed in-place to `/Users/vrg/Documents/Sol`, preserving inode birth timestamps).
- **`2025-05-02 08:37:04 IST`:** `config/homarr` (`appdata/db/db.sqlite`, `appdata/redis`, `appdata/trusted-certificates`) created as the server's first dashboard (`ghcr.io/homarr-labs/homarr:latest` on port `7575`).
- **`2025-05-02 22:01:56 IST` (`16:31:56 UTC`):** Earliest `media` table row (`id=1`, `createdAt = 2025-05-02 16:31:56`) recorded in Overseerr (`sctx/overseerr:latest`, port `5050:5055`).
- **`2025-05-02 22:18:13 to 22:26:16 IST`:** Creation of the TRaSH-aligned directory skeleton (`mkdir -p data/{torrents/{books,movies,music,tv},media/{books,movies,music,tv}}` and `mkdir -p config/{radarr,sonarr,lidarr,readarr,prowlarr,bazarr,qbittorrent,plex,jellyfin,overseerr,jellyseerr,homarr}` in `docs/archive/history-250918.txt` lines 1449 to 1455).
- **`2025-05-02 22:38:34 IST` (`17:08:34 UTC`):** `config/radarr` and `config/sonarr` initialized. Earliest TV series added to `sonarr.db` (`Series.Added`) at **`2025-05-02 17:18:32Z`**.

### 3.2 Days 2 to 7 (`2025-05-03` to `2025-05-10`): Servarr, qBittorrent, Plex & Overseerr Go Live
- **`2025-05-03 18:51:18 IST` (`13:21:18Z`):** First movie added to `radarr.db` (`Movies.Added`).
- **`2025-05-03 19:52:26 IST`:** `config/qbittorrent` initialized (`lscr.io/linuxserver/qbittorrent:latest`, WebUI on `:8080`, BitTorrent peer port `:6881`, later changed to `:42069`).
- **`2025-05-03 20:56:40 IST` (`15:26:40Z`):** `config/prowlarr` initialized. Within 16 minutes, the first 4 indexers were configured in `prowlarr.db` (`Indexers` table):
  1. `1337x` (`2025-05-03 15:36:31Z`)
  2. `IPTorrents` (`2025-05-03 15:40:49Z`)
  3. `The Pirate Bay` (`2025-05-03 15:41:13Z`)
  4. `LimeTorrents` (`2025-05-03 15:42:26Z`)
- **`2025-05-08 17:11:25Z` & `19:20:28Z`:** First automated grabs and imports recorded in `radarr.db` (`Nosferatu.2024.Hybrid.2160p.WEB-DL.DV.HDR.DDP5.1.Atmos.H265-AOC`) and `sonarr.db` (`Oswald S01 WEBRip AAC2.0 1080p x265-PoF`).
- **`2025-05-09 16:10:29 IST` (`10:40:29Z`):** `config/plex` initialized inside Docker (`plexinc/pms-docker:latest`, port `32400`) after migrating metadata from native macOS `$HOME/Library/Application Support/Plex Media Server/` via `rsync` (`history-250918.txt` line 1438). First items added to Plex library section at `2025-05-09 10:45:10 UTC` (*A Minecraft Movie*, *American Fiction*, *Anatomy of a Fall*, *Anora*, *The Apprentice*, *BlackBerry*, *Blink Twice*).
- **`2025-05-10 15:33:12 IST` (`10:03:12 UTC`):** First user `media_request` submitted in Overseerr (`2025-05-10 10:03:12`, preserved in `config/seerr/db/db.sqlite3` via `scripts/archive/merge_overseerr_history.py`).
- **`2025-05-12 22:55:48Z` & `2025-05-15 13:01:56Z`:** Oldest surviving active torrents in `config/qbittorrent/qBittorrent/BT_backup/*.fastresume`:
  1. `0fc70ba3d3b66f9f9566e22c55a0714492c1de3d.fastresume`: *The Dark Knight 2008 NORDiC REMUX 2160p* (`added_time = 1747090548` / `2025-05-12T22:55:48Z`)
  2. `ce63e548cd83e543ebae3a78dc40af4e2d56e989.fastresume`: *Cloudy With A Chance Of Meatballs 3D 2009* (`added_time = 1747314116` / `2025-05-15T13:01:56Z`)
- **`2025-05-19 22:39:33 IST`:** `config/bazarr` (`:6767`) and `config/lidarr` (`:8686`) created. `Milkie` added to Prowlarr (`15:46:30Z`), followed by `RuTracker.org` and `3D Torrents` on `2025-05-24`.
- **`2025-06-01 17:03:34 IST`:** `config/syncthing` (`:8384`) and `data/syncthing` (`hostname: Aperture`) deployed to sync Varun's Obsidian knowledge vault across devices.

### 3.3 Early Ingress, Domain Cutover (`*.hyd.vrg.rocks` to `*.vrg.rocks`), and Authelia SSO
Forensic evidence in `docs/archive/docker-compose-archive.yml` and `docs/archive/Caddyfile.txt` captures the early networking and identity evolution:
- **Nginx Proxy Manager to Caddy:** Sol initially tested `nginx-proxy-manager` (`jc21/nginx-proxy-manager:latest`, ports `80/443/81`), `filebrowser` (`9876:80`), `readarr` (`8787`), `obsidian-remote` (`12080`), and `obsidian` KasmVNC (`3000`). NPM was replaced with a custom **`caddy`** container (`caddy-cloudflare` with Cloudflare DNS-01 ACME challenge).
- **Domain Migration (`*.hyd.vrg.rocks` to `*.vrg.rocks`):** `docs/archive/Caddyfile.txt` lines 47 to 53 preserve the commented wildcard redirect block from the original Hyderabad subdomain namespace (`*.hyd.vrg.rocks`) to `*.vrg.rocks`.
- **Authelia (`auth.vrg.rocks`):** Prior to Authentik and Tinyauth, SSO was powered by **`authelia`** (`authelia/authelia:latest` on `:9091`) + **`authelia-redis`** (`redis:7-alpine`) using file-based secrets (`AUTHELIA_IDENTITY_VALIDATION_RESET_PASSWORD_JWT_SECRET_FILE`, `SESSION_SECRET_FILE`, `STORAGE_ENCRYPTION_KEY_FILE`) and two Caddy snippets inside `docs/archive/Caddyfile.txt`: `(authelia)` (enforcing 2FA forward-auth) and `(authelia_auto)` (bypassing `GET /api*` for Servarr mobile clients). Static personal apps (`mind.vrg.rocks`, `fam.vrg.rocks`, `scan.vrg.rocks`) used Caddy `basic_auth` (`VRG` bcrypt hash).

---

## 4. Era 2: Open-Source Media & Document Cutover (June 16 to December 31, 2025)

### 4.1 The Media Cutover: Plex + Overseerr to Jellyfin + Jellyseerr (`2025-06-16` to `2025-07-06`)
- **`2025-06-16 23:11:24 IST` (`17:41:24Z`):** `config/jellyfin` (`lscr.io/linuxserver/jellyfin:latest`, port `8096`) created (`device.txt`, `system.xml`, `encoding.xml`).
- **`2025-06-16 17:42:32Z`:** First row written to `jellyfin.db` (`ActivityLogs`: `Password has been changed for user VRG`), followed 8 minutes later (`17:50:39Z`) by the first Jellyfin video playback (*1408* and *Anora* on Chrome macOS).
- **`2025-06-19 23:45:01 IST` (`18:15:01Z`):** `config/jellyseerr` (`fallenbagel/jellyseerr:latest`, later renamed `config/seerr`) initialized on `:5055`. The primary admin account (`18:15:23Z`) and the first household member account (`18:19:45Z`) registered immediately.
- **`2025-06-30 02:55:17Z`:** `MyAnonamouse` added to Prowlarr for audiobooks and e-books.
- **`2025-07-05 to 2025-07-06`:** Final Plex database backup (`com.plexapp.plugins.library.db-2025-07-05`) and final Plex server log entry (`Jul 6 18:59:55 2025`) before `plex` and `overseerr` were retired. On the same weekend (`2025-07-05 23:29:47` & `23:31:43`), `config/code-server` (`:8443`) and `config/calibre` (`:8082/:8181`) were created.

### 4.2 Paperless-ngx & Persistent Caddy (`2025-07-07` to `2025-07-08`)
- **`2025-07-07 07:08:51 IST`:** `config/paperless` and `data/paperless` (`consume`, `data`, `db`, `export`, `media`, `redis`) created (via `install-paperless-ngx.sh` in `history-250918.txt` line 1579), backed by `paperless-db` (`postgres:17`), `paperless-broker` (`redis:8`), `paperless-gotenberg`, and `paperless-tika`.
- **`2025-07-07 08:15:48 IST`:** `config/caddy` and `data/caddy` formalized under `/Users/vrg/Documents/Sol`.
- **`2025-07-08 19:05:28Z`:** First documents ingested into `paperless-db` (`documents_document` table):
  - `id=1`: `HYD - CMB` (`added = 2025-07-08 19:05:28.234848+00`)
  - `id=2`: `CMB - HYD` (`added = 2025-07-08 19:05:29.527359+00`)
  - `id=3`: `Sri Lanka ETA` (`added = 2025-07-08 19:16:37.211641+00`)

### 4.3 Quettamind Digital Garden & Initial Monitoring Stack (`2025-07-25` to `2025-07-26`)
- **`2025-07-25 23:20:49 IST`:** `quartz/` cloned and configured (`npx quartz create`, symlinked `quartz/content` to `data/syncthing/Quettamind`, and built via `npx quartz build` in `history-250918.txt` lines 1663 to 1752) to serve `mind.vrg.rocks` directly from Caddy.
- **`2025-07-26 12:58:26 to 13:17:27 IST`:** Monitoring and management triad deployed:
  - `data/beszel` (`12:58:26`) + `data/beszel_agent` (`13:17:27`) (`henrygd/beszel` on `:8090`)
  - `data/uptime-kuma` (`12:58:27`) (`louislam/uptime-kuma` on `:3001`, first monitor `Jellyfin` created at `2025-07-26 07:33:13 UTC`)
  - `data/dockge` (`12:58:27`) (`louislam/dockge` on `:5001`)

### 4.4 Autumn/Winter 2025 Service Wave (`2025-09-07` to `2025-12-15`)
- **`2025-09-07 21:56:20 IST`:** `config/copyparty`, `data/copyparty`, and `/Users/vrg/Documents/Sol/priv` created (`copyparty/ac:latest` on `:3923`, `files.vrg.rocks`), replacing FileBrowser and Syncthing with WebDAV and HTTP file sharing.
- **`2025-09-18`:** Snapshot of interactive shell history saved to `docs/archive/history-250918.txt`.
- **`2025-09-24 23:51:40 IST`:** `config/flood` (`jesec/flood` on `:42024`) created.
- **`2025-09-27 18:01:30 IST`:** `config/kavita` (`:5000`) and `config/calibre-web` (`:8083`) created.
- **`2025-10-04`:** `config/wizarr` (`12:35:46`, `:5690`) and `config/n8n` + `data/n8n` (`19:21:02`, `:5678`) created.
- **`2025-10-06 17:18:22 IST` (`12:04:24Z`):** `config/vaultwarden` (`vaultwarden/server:latest`, `:8222`, `vault.vrg.rocks`) created. The primary admin user registered in `db.sqlite3` at `2025-10-06 12:04:24Z` (official Bitwarden Self-Host was evaluated via `bitwarden.env` on `2025-10-17 17:38:51` and discarded in favor of Vaultwarden).
- **`2025-10-19 21:59:06 IST`:** `config/rclone` (`filter.txt`) and `logs/` created for automated `rclone sync` backups to Microsoft OneDrive (`OneDrive:Sol`).
- **`2025-11-09 10:37:06 IST`:** `config/homeassistant` (`:8123`) created.
- **`2025-12-01 12:51:13 IST` (`07:24:58Z`):** `data/homebox` (`ghcr.io/sysadminsmedia/homebox:latest`, `:7745`, `inv.vrg.rocks`) initialized (`Living Room`, `Bedroom`, `Kitchen`, `Office`, `Garage` locations created at `07:24:58Z`, first item `Google Pixel Buds Pro 2 (Hazel)` cataloged `2025-12-13 18:36:17Z`).
- **`2025-12-02 18:57:30 IST`:** `data/paperless-ai` (`clusterzx/paperless-ai`, `:3000`) created.
- **`2025-12-15 14:59:36 IST`:** `config/cross-seed` (`ghcr.io/cross-seed/cross-seed`, `:2468`) created.

---

## 5. Era 3: Modern Dashboards, Workspaces, Authentik SSO & Modular Git Refactor (January to September 2026)

### 5.1 January 2026: ntfy, Glance, Arcane & Coder
- **`2026-01-17 18:31:03 IST`:** `config/ntfy`, `data/ntfy` (`binwiederhier/ntfy`, `:8095`, `ntfy.vrg.rocks`), and `config/qbittorrent/scripts/ntfy_notify.sh` created for real-time webhook push notifications.
- **`2026-01-18 11:14:42 IST`:** `config/glance` (`glanceapp/glance`, `:8080`, `dash.vrg.rocks`) and custom vector branding `sol.svg` (`18:01:40`) created, superseding Homarr.
- **`2026-01-30 18:58:54 IST` (`13:28:55Z`):** `data/arcane` (`ghcr.io/ofkm/arcane`, `:3552`, `arcane.vrg.rocks`) created (`VRG` user registered in `arcane.db` at `13:28:55Z`), superseding Dockge.
- **`2026-01-31 17:51:18 to 18:32:12 IST`:** `config/coder`, `coder/` Terraform templates (`coder/main.tf`), and `docs/archive/docker-compose-coder.yml` created to launch **`coder`** (`ghcr.io/coder/coder`, `:7080`, `coder.vrg.rocks`) alongside `coder-workspace-main`.

### 5.2 Spring and Summer 2026: Static Web PWAs, `/Volumes/PANOPTICON`, `qbit_manage`, and Authentik Cutover
- **`2026-04-08 10:44:30 IST`:** `web/scan` (`scan.vrg.rocks`, zero-dependency Homebox barcode scanner PWA) created.
- **`2026-05-09 19:02:50 IST`:** 2 TB external ExFAT drive mounted as **`/Volumes/PANOPTICON`** (`cross-seed-links` created at `23:21:42`).
- **`2026-05-10 13:48:54 IST`:** `config/qbit_manage` created. Early `Caddyfile.txt` snapshot archived (`2026-05-17 15:59:54`).
- **`2026-06-18 21:57:36 IST`:** `data/leafwiki` created.
- **`2026-07-21 08:45:01 to 08:54:40 IST`:** **Cutover from Authelia to Authentik (`2025.6.3`):**
  - Monolithic `docker-compose.yml` was backed up to `docs/archive/docker-compose-archive.yml` (`08:45:01`) and `docs/archive/docker-compose-backup.yml` (`08:47:20`), and `docs/archive/authentik-compose.yml` (`08:54:40`) was authored to deploy `authentik-server`, `authentik-worker`, `authentik-postgresql` (`postgres:16-alpine`), and `authentik-redis`.
- **`2026-07-24 11:49:40 IST`:** `web/aysynbm` (`aysynbm.vrg.rocks`, *"Are You Sure You Need Buy More?"* financial reflection PWA) created.

### 5.3 August and September 2026: Modular Compose Refactor, Native Jellyfin Metal, Git Init & Seerr v3.5.0
- **`2026-08-14 20:09:47 IST`:** `data/ignis` (`ignis.vrg.rocks` Obsidian vault sync) created.
- **`2026-08-17 13:50:48 to 15:03:20 IST`:** **Compose Modularization:**
  - The 922-line monolithic `docker-compose.yml` was refactored into a 12-line root orchestrator using Docker Compose V2 `include:` across 8 domain files in `compose/` (`core.yml`, `monitoring.yml`, `media.yml`, `download.yml`, `paperless.yml`, `knowledge.yml`, `coding.yml`, `utilities.yml`).
  - `scripts/`, `web/`, and `docs/` directories were created, and standalone `paperless.env` was archived (`13:57:32`).
- **`2026-08-22 19:58:33 IST`:** Native macOS **`jellyfin-metal`** (`config/jellyfin_metal`, port `8097`) initialized on Apple Silicon macOS for bare-metal Apple `VideoToolbox` hardware transcoding.
- **`2026-08-22 21:01:36 IST`:** **Git (`63f7fce`) and Jujutsu (`.jj`) initialized** in `/Users/vrg/Documents/Sol` and pushed to `github.com:varungupta3009/Sol.git`, followed by the initial `docs/system_state/00` to `08` documentation suite (`44bf0e9` on `2026-08-23`).
- **`2026-09-13 10:49:03 IST` (`29a2513`):** Migrated `jellyseerr` (`fallenbagel/jellyseerr:latest`) to the unified **`seerr`** image (`ghcr.io/seerr-team/seerr:latest`, v3.5.0) and renamed `config/jellyseerr` to `config/seerr`.

---

## 6. Era 4: The October 2026 Architectural Renaissance & 31-Agent Swarm Audit (October 17 to 20, 2026)

Between **2026-10-17** and **2026-10-20**, Sol underwent a full-stack transformation across 22 Git commits (`0d1fe74` through `53d95e2`) followed by a 31-agent verification and hardening audit:

### 6.1 Cross-Family `/double-agent` Audit & Compose Hardening (`2026-10-17`, `0d1fe74` & `a84bb28`)
- Converted 26 commented-out YAML service blocks across `compose/*.yml` into Docker Compose services gated by `profiles: ["standby"]`.
- Replaced unmaintained `flaresolverr` with **`byparr`** (`ghcr.io/thephaseless/byparr:latest`) using network alias `flaresolverr` for drop-in Prowlarr compatibility.
- Added `x-logging` JSON log rotation (`max-size: 10m`, `max-file: 3`) across all 8 compose files.
- Upgraded **`glance`** into a 3-page declarative Command Center (`Sol` at `/sol`, `Stats & Ops` at `/stats`, `Radar` at `/radar`) with custom Catppuccin Mocha and GM3 styling (`config/glance/assets/user.css`).

### 6.2 Storage Restructuring, `111.4 GiB` SSD Reclamation & Option A ExFAT Symlink Architecture (`2026-10-18` to `19`, `f70987e` & `53d95e2`)
- Reclaimed `111.4 GiB` on the internal 500 GB APFS SSD by deduplicating dual copies (*The Dark Knight*, *Cloudy with a Chance of Meatballs 2*), migrating *Star Wars Episode IV 3D* to external storage, and restructuring `/Volumes/PANOPTICON` into TRaSH-aligned `/Volumes/PANOPTICON/torrents/{movies,tv,cross-seed-links}` and `/Volumes/PANOPTICON/media/{movies,tv}`.
- Solved the ExFAT no-hardlink limitation (`Errno 45: Operation not supported`) via **Option A (`scripts/torrent_finished.py` and `scripts/arr_symlink_dedupe.sh`)**: disabled built-in `Completed Download Handling` in Radarr and Sonarr (`enableCompletedDownloadHandling = false`). When a torrent finishes on `/external/torrents`, qBittorrent creates relative symlinks in `/external/media/{movies,tv}` and triggers Radarr, Sonarr, and Jellyfin API refreshes while qBittorrent seeds the payload in `/external/torrents`.
- Hardened all 4 external TV series directories (`H1` to `H5`: *Impractical Jokers*, *Kochikame: Tokyo Beat Cops*, *Oswald*, *Shin Chan*) from directory symlinks into real directories containing per-file relative symlinks, added `realpath` equality and directory-symlink abort guards, and configured `/external/media/.recycle` (`14`-day retention) in Sonarr and Radarr.

### 6.3 Database Repairs, Postgres 17 Alpine Migration & Historical Overseerr Merge (`2026-10-18`, `f70987e` & `75796b2`)
- Migrated `paperless-db` from Debian `postgres:17` (glibc) to `postgres:17-alpine` (`PG 17.11` musl) via full `pg_dump` and `psql` reload, saving ~190 MB disk and eliminating glibc/musl collation warnings.
- Repaired corrupted `homebox.db` (`updated_at` nil scan errors) and promoted **`homebox`** (`inv.vrg.rocks`) from standby back to active production.
- Repaired `prowlarr.db`, `arcane.db`, and `cross-seed.db`.
- Authored and executed `scripts/archive/merge_overseerr_history.py` (`75796b2`), merging 10 historical May/June 2025 Overseerr requests into `config/seerr/db/db.sqlite3` (bringing `media_request` count to `43` and backdating `41` `media.createdAt` rows to `2025-05-02`).

### 6.4 Qui v1.32.0 Deployment & `/downloads` Retirement (`2026-10-18` to `19`, `3f79221` & `53d95e2`)
- Deployed **`qui`** (`ghcr.io/autobrr/qui:v1.32.0`, `qui.vrg.rocks`, `:7476`) as the single-binary Go qBittorrent web interface, cross-seed engine, and tracker rules daemon.
- Rewrote all 289 qBittorrent `.fastresume` entries to use `/data/torrents` and `/external/torrents`, retiring the legacy `/downloads` bind mount.
- Built `config/qui/tracker_registry.json` (26 tracker codes), configured 25 Tracker Customizations, 10 automated FUP bandwidth-throttling rules, and tagged `150/150` torrents.

### 6.5 Wave 1 to 3 Container Consolidation (`2026-10-19` to `20`, `614c7f6`, `0dd2ba9`, `55a365f`)
- **Wave 1 (6 Zero-Container Static Web Apps, `0 MiB` RAM):** Deployed `tools.vrg.rocks` (IT-Tools), `chef.vrg.rocks` (CyberChef v10.19.4), `pdf.vrg.rocks` (BentoPDF WASM), `speed.vrg.rocks` (OpenSpeedTest), `draw.vrg.rocks` (Excalidraw), and `mi.vrg.rocks` (MediaInfo Web WASM) via `scripts/sync_static_tools.sh` and Caddy `file_server`.
- **Wave 2 ( Purge of 13 Legacy & Superseded Services):** Permanently removed `dockge`, `uptime-kuma`, `homarr`, `qbit_manage`, `flood`, `calibre`, `calibre-web`, `rclone-gui`, `authentik-postgresql`, `authentik-server`, `authentik-worker`, `flaresolverr`, and `cross-seed` from `compose/*.yml` and `ports.json`, and deleted their leftover runtime directories (`config/{jellyfin_metal,plex,cross-seed,homarr,calibre,calibre-web,qbit_manage,syncthing,flood}` and `data/{uptime-kuma,dockge,syncthing,authentik}`), reclaiming over `13.5 GB` of disk space.
- **Wave 3 (4 Lean Active Containers, `~110 MiB` total RAM):** Deployed **`readeck`** (`links.vrg.rocks`, `:8000`), **`enclosed`** (`send.vrg.rocks`, `:8787`), **`pocketbase`** (`pb.vrg.rocks`, `:8090`), and **`airtrail`** (`fly.vrg.rocks`, `:3000`, sharing `paperless-db`).

### 6.6 Unified Identity Spine: `tinyauth` v5.2.0 + `lldap` (`2026-10-19` to `20`, `b188240` & `53d95e2`)
- Replaced the 3-container Authentik stack (`~502 MiB` RAM) with **`tinyauth` v5.2.0** (`ghcr.io/tinyauthapp/tinyauth:v5`, `~29 MiB` RAM, `auth.vrg.rocks`) and **`lldap`** (`ghcr.io/lldap/lldap:stable`, `~12 MiB` RAM, `ldap.vrg.rocks`).
- Configured 0-click Google OAuth (`TINYAUTH_OAUTH_AUTOREDIRECT=google`), per-app admin ACLs (`TINYAUTH_APPS_*_OAUTH_WHITELIST`), native OIDC Provider endpoints for 7 apps (`paperless-ngx`, `arcane`, `homebox`, `airtrail`, `coder`, `readeck`, `jellyfin`), and automated one-way provisioning (`lldap` to `config/auth/users.json` to downstream apps) via `scripts/identity_sync.py` and macOS `launchd` (`scripts/launchd/com.vrg.sol.identity-sync.plist`).

### 6.7 2-Tier Disaster Recovery & October 20, 2026 31-Agent Swarm Audit (`2026-10-19` to `20`)
- Replaced raw `rclone sync` backups with **`backrest`** (`ghcr.io/garethgeorge/backrest:latest`, `backrest.vrg.rocks`, `:9898`) orchestrating encrypted, deduplicated **Restic** snapshots to Tier 1 local (`/Volumes/PANOPTICON/backups/sol-restic` at `03:30 IST`) and Tier 2 cloud (`rclone:OneDrive:Sol-Restic` at `04:00 IST`), preceded by `scripts/stage_db_backups.sh` (`scripts/launchd/com.vrg.sol.db-stage.plist` at `03:00 IST`).
- On **2026-10-20**, a 31-agent swarm audited every container, script, database, and route on `dash.vrg.rocks` and executed live remediations:
  - Added Docker healthchecks across all 29 active containers (`29/29` reporting `(healthy)`).
  - Eliminated macOS `launchd` TCC permission blocks on `~/Documents` (`kTCCServiceSystemPolicyDocumentsFolder`) and `/Volumes/PANOPTICON` (`kTCCServiceSystemPolicyRemovableVolumes`) by invoking `stage_db_backups.sh` via `/opt/homebrew/bin/python3` and scanning symlinks through an ephemeral `redis:8-alpine` container over OrbStack VirtioFS (`~12s` runtime, `Exit 0`).
  - Replaced `identity_sync.py` HTTP/GraphQL polling with direct read-only SQLite reads (`?immutable=1`) and a `<50ms` SHA-256 fast-path check, stopping the `WatchPaths` self-triggering write loop on `data/lldap/users.db`.
  - Fixed `coder` Docker socket GID (`group_add: ["0"]`) and pushed the `sol-workspace` Terraform template live.
  - Fixed `jellyfin` `/tmp/jellyfin` tmpfs permissions (`uid=501,gid=20`), switched `database.xml` to `Optimistic` locking, moved misplaced home video files out of `/media/internal/movies`, re-pointed 7 cross-seed symlinks, linked *The Sixth Sense (1999)* in Radarr, and converted `/Users/vrg/Documents/Sol/web/fam` from an external symlink into a real directory copy so Restic backs up `vault.enc`.

---

## 7. Forensic Evidence Ledgers

### 7.1 Archive Files Excavated (`dash.vrg.rocks:/Users/vrg/Documents/Sol/docs/archive/`)

| File | Birth / Modified Date | Lines / Size | Forensic Contents & Historical Proof |
| :--- | :--- | :--- | :--- |
| `Caddyfile.txt` | `2026-05-17 15:59:54` | 150 lines (`3.4 KB`) | Proves early **Authelia** (`(authelia)` & `(authelia_auto)` snippets on `authelia:9091`), legacy `*.hyd.vrg.rocks` to `*.vrg.rocks` domain redirect, `basic_auth` (`VRG`) on `mind`, `fam`, `scan`, and routes for `plex` (`32400`), `overseerr` (`5050`), `homarr` (`7575`), `syncthing` (`8384`), `calibre` (`8082`), `calibre-web` (`8083`), `flood` (`42024`), `dockge` (`5001`), `uptime-kuma` (`3001`), `n8n` (`5678`), `wizarr` (`5690`), and `leafwiki` (`8085`). |
| `authentik-compose.yml` | `2026-07-21 08:54:40` | 73 lines (`2.3 KB`) | Standalone draft used during the `2026-07-21` cutover from Authelia to Authentik (`2025.6.3`), including `authentik-postgresql` (`postgres:16-alpine`) and `authentik-redis` (before Redis was dropped in Authentik 2025.10). |
| `bitwarden.env` | `2025-10-17 17:38:51` | 16 lines (`608 B`) | Proves evaluation of official Bitwarden Unified/Self-Host (`bw.vrg.rocks`) on Oct 17, 2025, 11 days after deploying `vaultwarden` (`vault.vrg.rocks`). |
| `docker-compose-archive.yml` | `2026-07-21 08:45:01` | 751 lines (`26.9 KB`) | Complete pre-Authentik monolithic compose file. Contains active `authelia` + `authelia-redis`, `jellyseerr`, `copyparty`, `flood`, `kavita`, `wizarr`, `n8n`, `vaultwarden`, `homeassistant`, `homebox`, `paperless-ai`, `cross-seed`, `ntfy`, `glance`, `arcane`, `leafwiki`, and commented-out Era 1 relics (`nginx-proxy-manager`, `filebrowser`, `obsidian-remote`, `obsidian`, `plex`, `overseerr`, `readarr`) mounting `/Volumes/Backup Plus/Media Drive`. |
| `docker-compose-backup.yml` | `2026-07-21 08:47:20` | 922 lines (`34.0 KB`) | Snapshot taken 2 minutes after `docker-compose-archive.yml` prior to splitting into `compose/*.yml` on `2026-08-17`. Adds `authentik-postgresql`, `authentik-server`, `authentik-worker`, and `ignis`. |
| `docker-compose-coder.yml` | `2026-01-31 18:24:15` | 81 lines (`2.6 KB`) | Initial standalone compose spec for `coder` (`ghcr.io/coder/coder:latest` on `:7080`) and embedded Postgres (`coder-db`) before merging into `compose/coding.yml`. |
| `history-250918.txt` | `2025-09-18` (copied `2026-08-17`) | 999 lines (`31.8 KB`) | Zsh command history from May to September 2025. Captures `cd Documents/Home\ Server` (line 1413), `mkdir -p data/... config/...` (lines 1449 to 1455), `rsync` of native Plex Media Server to Docker (line 1438), `install-paperless-ngx.sh` (line 1579), `dot_clean /Volumes/Backup\ Plus` (line 1618), and `Quettamind` Quartz build (lines 1663 to 1752). |
| `paperless.env` | `2025-07-07` (archived `2026-08-17`) | 51 lines (`1.5 KB`) | Original Paperless-ngx environment file (`PAPERLESS_URL=https://docs.vrg.rocks`, `PAPERLESS_TIME_ZONE=Asia/Kolkata`, `PAPERLESS_OCR_LANGUAGE=eng`) before consolidation into root `.env`. |
| `FLASH_LOCAL_VERIFICATION_RUNBOOK.md` | `2026-10-17` (archived `2026-10-20`) | 233 lines (`71.2 KB`) | Deterministic host verification playbook executed on `2026-10-18` to complete the initial `/double-agent` cutover. |

### 7.2 Earliest Database Records Across Persistent Services (`?immutable=1`)

| Database / Store | Table / Key | Earliest Timestamp (UTC) | Latest / Total Count | First Historical Record Details |
| :--- | :--- | :--- | :--- | :--- |
| **Seerr / Overseerr** (`config/seerr/db/db.sqlite3`) | `media` / `media_request` | `2025-05-02 16:31:56` (`media`) / `2025-05-10 10:03:12` (`media_request`) | `55` media / `43` requests (`4` users) | Backdated `media` rows from Day 1 (`2025-05-02`). 10 Overseerr requests (`2025-05-10` to `2025-06-15`) merged into Jellyseerr/Seerr (`2025-06-19`+). |
| **Sonarr** (`config/sonarr/sonarr.db`) | `Series` / `History` | `2025-05-02 17:18:32Z` (`Series`) / `2025-05-08 19:20:28Z` (`History`) | `36` series / `3,551` history rows | First series added `2025-05-02` (50 mins after `config/sonarr` birth). First import *Oswald S01* (`2025-05-08`). |
| **Radarr** (`config/radarr/radarr.db`) | `Movies` / `History` | `2025-05-03 13:21:18Z` (`Movies`) / `2025-05-08 17:11:25Z` (`History`) | `102` movies / `970` history rows | First movie added `2025-05-03`. First grab/import *Nosferatu (2024)* (`2025-05-08`). |
| **Prowlarr** (`config/prowlarr/prowlarr.db`) | `Indexers` / `History` | `2025-05-03 15:36:31Z` (`Indexers`) | `19` indexers / `31,203` queries | `1337x` (`15:36:31Z`), `IPTorrents` (`15:40:49Z`), `The Pirate Bay` (`15:41:13Z`), `LimeTorrents` (`15:42:26Z`). |
| **Plex (Retired)** (`config/plex/.../com.plexapp.plugins.library.db`) | `metadata_items.added_at` | `2025-05-09 10:45:10` | `1,303` metadata items (frozen `2025-07-05`) | *A Minecraft Movie*, *American Fiction*, *Anatomy of a Fall*, *Anora* added on `2025-05-09`. Decommissioned `2025-07-06` and directory removed `2026-10-20`. |
| **qBittorrent** (`BT_backup/*.fastresume`) | Bencode `added_time` | `2025-05-12 22:55:48Z` (`1747090548`) | `150` active `.fastresume` torrents | *The Dark Knight 2008 NORDiC REMUX 2160p* (`2025-05-12`), *Cloudy With A Chance Of Meatballs 3D* (`2025-05-15`). |
| **Jellyfin** (`config/jellyfin/data/data/jellyfin.db`) | `ActivityLogs` / `BaseItems` | `2025-06-16 17:42:32Z` | `289` activity logs / `2,066` base items (`4` users) | `Password has been changed for user VRG` (`17:42:32Z`). First playback *1408* & *Anora* (`17:50:39Z`). |
| **Paperless-ngx** (`paperless-db` PostgreSQL 17.11) | `documents_document` / `auth_user` | `2025-07-08 19:05:28Z` (`added`) | `290` documents (`3` users) | `id=1` `HYD - CMB` (`19:05:28Z`), `id=2` `CMB - HYD` (`19:05:29Z`), `id=3` `Sri Lanka ETA` (`19:16:37Z`). |
| **Vaultwarden** (`config/vaultwarden/db.sqlite3`) | `users.created_at` | `2025-10-06 12:04:24` | `1` user (`VRG`) | Active password vault since Oct 6, 2025 (now in `standby` profile). |
| **Homebox** (`data/homebox/homebox.db`) | `locations` / `items` | `2025-12-01 07:24:58Z` | `7` locations / `1` item (`2` users) | Default locations created `2025-12-01`. `Google Pixel Buds Pro 2 (Hazel)` added `2025-12-13 18:36:17Z`. |
| **Arcane** (`data/arcane/arcane.db`) | `users.created_at` | `2026-01-30 13:28:55Z` | `1` user (`VRG`) | Container management UI initialized Jan 30, 2026. |
| **LLDAP** (`data/lldap/users.db`) | `users.creation_date` | `2026-10-19 04:01:20Z` | `4` users / `3` groups | `admin` (`04:01:20Z`), `vrg` (`04:05:14Z`), and 3 household member accounts (`04:05:14Z` to `14:04:41Z`). |

### 7.3 Git Commit History Ledger (`2026-08-22` to `2026-10-20`)

| Commit | Timestamp (IST) | Summary |
| :--- | :--- | :--- |
| `63f7fce` | `2026-08-22 21:01:36` | `feat: initial declarative infrastructure & disaster recovery setup` |
| `35b8d83` | `2026-08-22 21:33:07` | `feat(media): document and automate native macOS Jellyfin Metal instance` |
| `44bf0e9` | `2026-08-23 19:21:05` | `docs: add comprehensive system state architecture documentation (00-08)` |
| `29a2513` | `2026-09-13 10:49:03` | `feat(media): migrate jellyseerr to unified seerr v3.5.0` |
| `0d1fe74` | `2026-10-17 17:44:22` | `feat: October 2026 architectural hardening, profiles, and Byparr migration` |
| `a84bb28` | `2026-10-17 19:14:58` | `feat(glance): overhaul dashboard into 3-page command center & add Task 4B` |
| `f70987e` | `2026-10-18 13:18:10` | `feat(storage): complete PANOPTICON restructuring, zero-copy symlink automation & live verification` |
| `5b568de` | `2026-10-18 17:27:30` | `feat: repair live containers, overhaul 3-page Glance dashboard, and add Mega Optimization Roadmap` |
| `3f79221` | `2026-10-18 19:19:52` | `feat(download,backup): deploy qui v1.32, overhaul backup to Backrest+Restic, and prune 12.46 GB bloat` |
| `75796b2` | `2026-10-18 19:57:54` | `feat(seerr): merge historical Overseerr requests into active Seerr DB and retire legacy directories` |
| `614c7f6` | `2026-10-19 06:05:19` | `feat(web): deploy Wave 1 zero-container static suite (tools, chef, pdf, speed, draw, mi)` |
| `0dd2ba9` | `2026-10-19 06:24:03` | `chore(compose): Wave 2 standby bloat cleanup (remove 8 superseded services)` |
| `55a365f` | `2026-10-19 07:03:04` | `feat(stack): deploy Wave 3 lean services (readeck, enclosed, pocketbase, airtrail)` |
| `b188240` | `2026-10-19 08:11:13` | `feat(auth): cut over *.vrg.rocks from Authentik to Tinyauth v5 with 0-click Google SSO & OIDC` |
| `2ff0526` | `2026-10-19 10:51:38` | `feat(auth): deploy lldap and unify single-email identity across all apps` |
| `53d95e2` | `2026-10-19 20:08:57` | `feat: complete qui cross-seed & FUP automation, lldap identity sync, symlink hardening, and 2-tier Backrest+Restic DR` |

---

## 8. Legacy Authentik Architecture & Reconstruction Specification

Authentik (`2026.5.3`) served as Sol's identity provider from **2026-07-21** until **2026-10-19**, when it was replaced by `tinyauth:v5` + `lldap` (saving `~502 MiB` of idle RAM and removing background worker CPU polling) and deleted from `compose/core.yml` during the October 20, 2026 cleanup. Its `224 MB` local PostgreSQL cluster (`data/authentik`) and `13 MB` SQL dump (`data/backups/authentik_db.sql.gz`) were removed after recording the exact reconstruction blueprint below.

### 8.1 Container Definitions (Former `compose/core.yml` Blocks)

```yaml
  authentik-postgresql:
    container_name: authentik-postgresql
    image: docker.io/library/postgres:16-alpine
    restart: unless-stopped
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
    environment:
      POSTGRES_PASSWORD: ${PG_PASS:?database password required}
      POSTGRES_USER: ${PG_USER:-authentik}
      POSTGRES_DB: ${PG_DB:-authentik}
    volumes:
      - ${DOCKER_DATA_DIR}/authentik/database:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -d $${POSTGRES_DB} -U $${POSTGRES_USER}"]
      start_period: 20s
      interval: 30s
      retries: 5
      timeout: 5s

  authentik-server:
    container_name: authentik-server
    image: ${AUTHENTIK_IMAGE:-ghcr.io/goauthentik/server}:${AUTHENTIK_TAG:-2026.5.3}
    restart: unless-stopped
    command: server
    environment:
      AUTHENTIK_POSTGRESQL__HOST: authentik-postgresql
      AUTHENTIK_POSTGRESQL__USER: ${PG_USER:-authentik}
      AUTHENTIK_POSTGRESQL__NAME: ${PG_DB:-authentik}
      AUTHENTIK_POSTGRESQL__PASSWORD: ${PG_PASS}
      AUTHENTIK_SECRET_KEY: ${AUTHENTIK_SECRET_KEY:?secret key required}
      AUTHENTIK_WEB__WORKERS: 2
    volumes:
      - ${DOCKER_DATA_DIR}/authentik/media:/media
      - ${DOCKER_DATA_DIR}/authentik/custom-templates:/templates
    ports:
      - "127.0.0.1:9000:9000"
      - "127.0.0.1:9443:9443"
    depends_on:
      authentik-postgresql:
        condition: service_healthy

  authentik-worker:
    container_name: authentik-worker
    image: ${AUTHENTIK_IMAGE:-ghcr.io/goauthentik/server}:${AUTHENTIK_TAG:-2026.5.3}
    restart: unless-stopped
    command: worker
    environment:
      AUTHENTIK_POSTGRESQL__HOST: authentik-postgresql
      AUTHENTIK_POSTGRESQL__USER: ${PG_USER:-authentik}
      AUTHENTIK_POSTGRESQL__NAME: ${PG_DB:-authentik}
      AUTHENTIK_POSTGRESQL__PASSWORD: ${PG_PASS}
      AUTHENTIK_SECRET_KEY: ${AUTHENTIK_SECRET_KEY:?secret key required}
      AUTHENTIK_WORKER__CONCURRENCY: 2
    volumes:
      - ${DOCKER_DATA_DIR}/authentik/media:/media
      - ${DOCKER_DATA_DIR}/authentik/certs:/certs
      - ${DOCKER_DATA_DIR}/authentik/custom-templates:/templates
    depends_on:
      authentik-postgresql:
        condition: service_healthy
```

### 8.2 Upstream Google OAuth Source & 0-Click Identification Stage

To redirect unauthenticated requests straight to `accounts.google.com` without rendering an Authentik login form:

1. **OAuth Source (`authentik_sources_oauth_oauthsource`):**
   - **Name / Slug:** `Google` / `google` (`enabled = true`, `promoted = true`)
   - **Provider Type:** `google` (`pkce = S256`, `authorization_code_auth_method = basic_auth`)
   - **User Matching Mode:** `email_link` (links OAuth logins to existing Authentik users by email)
   - **Authentication Flow:** `default-source-authentication`
   - **Enrollment Flow:** `default-source-enrollment`
   - **Consumer Key / Secret:** `${GOOGLE_OAUTH_CLIENT_ID}` / `${GOOGLE_OAUTH_CLIENT_SECRET}`
   - **Google Cloud Authorized Redirect URI:** `https://auth.vrg.rocks/source/oauth/callback/google/`
2. **Identification Stage (`default-authentication-identification`):**
   - **`user_fields`:** `{}` (empty array, disabling the username/password input box)
   - **Sources:** `Google` (with `promoted = true` on the Google source)
   - **Effect:** Because `user_fields` is empty and `Google` is promoted, hitting `default-authentication-flow` immediately returns an `HTTP 302` redirect to `https://accounts.google.com/o/oauth2/v2/auth`.
3. **User Login Stage (`default-authentication-login`):**
   - **`session_duration`:** `seconds=0`
   - **`remember_device`:** `days=30` (`enable_remember_me = true`)
4. **Authorization Flow:**
   - All providers bound to `default-provider-authorization-implicit-consent` (0 stages, skipping per-app consent screens).

### 8.3 Applications, Providers & Embedded Outpost

| Application (`slug`) | Provider Name (`id`) | Type & Mode | Key Parameters & Redirect URIs |
| :--- | :--- | :--- | :--- |
| **`Sol` (`sol`)** | `Caddy` (`id=3`) | `ProxyProvider` (`forward_domain`) | `external_host: https://auth.vrg.rocks`, `cookie_domain: vrg.rocks`, `access_token_validity: hours=24`, `refresh_token_validity: days=30`, `intercept_header_auth: true`. Bound to `authentik Embedded Outpost` (`type=proxy`, `authentik_host=https://auth.vrg.rocks/`). Policy binding: `Admins` group on application `Sol`. |
| **`Paperless-ngx` (`paperless-ngx`)** | `Provider for Paperless-ngx` (`id=7`) | `OAuth2Provider` (`confidential`) | `sub_mode: hashed_user_id`, `issuer_mode: per_provider`, `include_claims_in_id_token: true`, `access_code_validity: minutes=1`, `access_token_validity: minutes=5`, `refresh_token_validity: days=30`. Scopes: `openid`, `email`, `profile`. Strict Redirect URI: `https://docs.vrg.rocks/accounts/oidc/authentik/login/callback/`. Discovery URL: `https://auth.vrg.rocks/application/o/paperless-ngx/.well-known/openid-configuration`. |
| **`Arcane` (`arcane`)** | `Provider for Arcane` (`id=9`) | `OAuth2Provider` (`confidential`) | `sub_mode: hashed_user_id`, `issuer_mode: per_provider`, `include_claims_in_id_token: true`, `access_code_validity: minutes=1`, `access_token_validity: minutes=5`, `refresh_token_validity: days=30`. Scopes: `openid`, `profile`, custom `Arcane Email Scope`. Strict Redirect URI: `https://arcane.vrg.rocks/auth/oidc/callback`. Issuer URL: `https://auth.vrg.rocks/application/o/arcane`. |
| **`Jellyfin` (`jellyfin`)** | `Provider for Jellyfin` (`id=5`) | `LDAPProvider` (unused) | `base_dn: dc=company,dc=com`, `bind_mode: cached`, `search_mode: cached` (never connected to an LDAP outpost). |

### 8.4 Legacy Caddy Forward-Auth Snippet (`Caddyfile`)

```caddyfile
(forward_auth) {
	forward_auth authentik-server:9000 {
		uri /outpost.goauthentik.io/auth/caddy
		copy_headers X-Authentik-Username X-Authentik-Groups X-Authentik-Entitlements X-Authentik-Email X-Authentik-Name X-Authentik-Uid X-Authentik-Jwt X-Authentik-Meta-Jwks X-Authentik-Meta-Outpost X-Authentik-Meta-Provider X-Authentik-Meta-App X-Authentik-Meta-Version
		trusted_proxies private_ranges
	}
}
```
