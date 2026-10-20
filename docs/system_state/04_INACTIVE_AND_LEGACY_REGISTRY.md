# 04. Standby, Sidelined & Legacy Service Registry

> **Scope:** Audit of every standby service declared with Docker Compose V2 `profiles: ["standby"]` (and `profiles: ["ops"]`) across `compose/*.yml`, the standby native macOS `jellyfin-metal` instance, every commented standby vhost in `Caddyfile`, and every retired/decommissioned Era 1 through Era 4 service removed from active Compose files.  
> **Purpose:** Document historical design decisions, sidelining and retirement rationale, port mappings, and reactivation recipes.  
> **Last Synced to Ground Truth:** 2026-10-20  

---

## 1. Executive Summary of Stack Evolution

Across Eras 1 through 4 (May 2025 to October 2026), the Sol home server evolved through targeted consolidations that reduced total container RAM to `~1.95 GiB` across `29` healthy active containers while expanding capabilities:

1. **Edge Routing & Zero-Container Static Suite:** Migrated from `Nginx Proxy Manager` to `Caddy v2.11.7` (`compose/core.yml`), serving 31 reverse-proxy/redirect site blocks plus 10 static web applications (`mind`, `fam`, `scan`, `aysynbm`, `tools`, `chef`, `pdf`, `speed`, `draw`, `mi`) with `0 MiB` of extra container memory.
2. **Authentication & Unified Directory:** Migrated from `Authelia` (Era 1) to `Authentik` (Era 3) and then in Era 4 (October 2026) to `Tinyauth v5.2.0` (`~29 MiB` RAM) + `LLDAP` (`~12 MiB` RAM) + `scripts/identity_sync.py` (`<50 ms` SQLite SHA-256 fast-path), reclaiming `~502 MiB` of idle RAM previously consumed by `authentik-server`, `authentik-worker`, and `authentik-postgresql`.
3. **Media & Requests:** Migrated from `Plex` + `Overseerr` (Era 1) to `Jellyfin` + `Jellyseerr` (Era 2) and unified `Seerr` v3.5.0 (Era 3/4, with all 43 historical Overseerr requests merged). Native macOS `jellyfin-metal` (`:8097`) is retained in `standby` for bare-metal VideoToolbox benchmarks.
4. **Download & Tracker Automation:** Migrated from `Flood`, `qbit_manage`, and `Cross-Seed` to `QUI v1.32.0` (`qui.vrg.rocks`, ~38 MiB RAM) managing qBittorrent with 26 tracker customization rules and 10 tracker Fair Use Policy (FUP) rules.
5. **Cloudflare Challenge Solving:** Replaced `FlareSolverr` with `Byparr` (`ghcr.io/thephaseless/byparr:latest`, carrying the Docker network alias `flaresolverr` and hardened with `shm_size: 1gb`, `/tmp` tmpfs, `BLOCK_MEDIA: "true"`, and `/openapi.json` healthcheck).
6. **Dashboard, Stack Management & Backups:** Replaced `Homarr`, `Uptime Kuma`, and `Dockge` with `Glance` (`dash.vrg.rocks`) and `Arcane` (`arcane.vrg.rocks`). Replaced legacy `rclone-gui` with `Backrest` + `Restic` (`backrest.vrg.rocks`) backed by automated `launchd` database staging (`com.vrg.sol.db-stage.plist`).

### Inventory Totals (October 20, 2026 Ground Truth)

| Tier | Count | Location |
| :--- | :---: | :--- |
| Active Compose Containers (all `(healthy)`) | `29` | `compose/*.yml` (default profile) |
| Standby Compose Services (`profiles: ["standby"]`) | `15` | `compose/*.yml` (`gatus`, `beszel`, `beszel-agent`, `dozzle`, `recyclarr`, `wizarr`, `unpackerr`, `paperless-gotenberg`, `paperless-tika`, `paperless-ai`, `leafwiki`, `kavita`, `vaultwarden`, `n8n`, `homeassistant`) |
| Ops Compose Task Runner (`profiles: ["ops"]`) | `1` | `compose/utilities.yml` (`rclone`) |
| **Total Declared Compose Services** | **`45`** | Across all 8 `compose/*.yml` files |
| Standby Native macOS Application | `1` | `jellyfin-metal` (`:8097`, `ports.json` `status: "standby"`) |
| Active Zero-Container Static Web Apps | `10` | Served directly by `caddy` (`mind`, `fam`, `scan`, `aysynbm`, `tools`, `chef`, `pdf`, `speed`, `draw`, `mi`) |
| Commented Standby Vhost Blocks | `12` | `Caddyfile` (`status`, `beszel`, `dozzle`, `metal`, `wizarr`, `cs`, `paperless-ai`, `leaf`, `kavita`, `home`, `vault`/`pass`, `n8n`) |
| Retired & Decommissioned Services | `20` | Removed from `compose/*.yml` and `ports.json` (documented in Section 4) |

---

## 2. Standard Reactivation Procedure for Standby Services

Every standby service declared in `compose/*.yml` follows a 3-step activation recipe:

```bash
# 1. Start the specific standby container (always pass the service name explicitly)
docker compose --profile standby up -d <service>

# 2. If the service has a commented vhost in Caddyfile, uncomment it and reload Caddy
docker exec -i caddy caddy reload --config - --adapter caddyfile < /Users/vrg/Documents/Sol/Caddyfile

# 3. Optional: update ports.json "status" from "standby" to "active"
```

> [!WARNING]
> Never run `docker compose --profile standby up -d` without naming a specific service. Omitting the service name starts all 15 standby containers simultaneously, including `homeassistant` (`privileged: true`, `network_mode: host`) and `beszel-agent` (`network_mode: host`).

---

## 3. Active Standby & Ops Services Catalog (16 Compose Services + 1 Native Service)

These 16 Compose services (`15` under `profiles: ["standby"]` and `1` under `profiles: ["ops"]`) and `1` native macOS service (`jellyfin-metal`) remain defined in `compose/*.yml` and `ports.json` for on-demand activation.

### 3.1 Monitoring Standby Services (`compose/monitoring.yml`)

| Service | Image | Internal / Host Port | Commented Vhost | Sidelining Rationale & Reactivation Notes |
| :--- | :--- | :--- | :--- | :--- |
| **`gatus`** | `twinproduction/gatus:latest` | `8080/tcp` (internal) | `status.vrg.rocks` (`import forward_auth`) | Glance (`dash.vrg.rocks` `/sol` and `/stats`) monitors all 26 HTTP endpoints natively. Config persists in `config/gatus`. |
| **`beszel`** | `henrygd/beszel:latest` | `8090/tcp` (internal) | `beszel.vrg.rocks` (`import forward_auth`) | Host and container resource telemetry is surfaced on Glance (`dash.vrg.rocks`). Data persists in `data/beszel`. |
| **`beszel-agent`** | `henrygd/beszel-agent:latest` | `45876/tcp` (`network_mode: host`, `host_port: null` in `ports.json`) | *(None)* | Companion host metrics agent for `beszel`. Requires `BESZEL_AGENT_KEY` and `BESZEL_AGENT_TOKEN` in `.env`. |
| **`dozzle`** | `amir20/dozzle:latest` | `8080/tcp` (internal) | `dozzle.vrg.rocks` (`import forward_auth`) | `Arcane` (`arcane.vrg.rocks`) provides container log streaming and shell access with native Tinyauth OIDC. Keep `import forward_auth` on `dozzle.vrg.rocks` when enabled because `DOZZLE_ENABLE_ACTIONS` and `DOZZLE_ENABLE_SHELL` are `"true"`. |

### 3.2 Media & Download Standby Services (`compose/media.yml`, `compose/download.yml` & Native Host)

| Service | Image / Runtime | Internal / Host Port | Commented Vhost | Sidelining Rationale & Reactivation Notes |
| :--- | :--- | :--- | :--- | :--- |
| **`jellyfin-metal`** *(Native macOS)* | Native macOS `Jellyfin.app` (`scripts/setup_jellyfin_metal.py`) | `8097/tcp` (host) | `metal.vrg.rocks` | Bare-metal Apple Silicon VideoToolbox instance kept on standby while containerized `jellyfin` (`watch.vrg.rocks`, `:8096`) serves production traffic via Direct Play and `/tmp/jellyfin` (`2g` tmpfs). |
| **`recyclarr`** | `ghcr.io/recyclarr/recyclarr:latest` | *(CLI / Cron Daemon)* | *(None)* | TRaSH Guides quality profile and Custom Format sync daemon for Radarr and Sonarr. Config directory: `config/recyclarr`. |
| **`wizarr`** | `ghcr.io/wizarrrr/wizarr:latest` | `5690/tcp` (internal) | `wizarr.vrg.rocks` (`import forward_auth`) | User invitation portal for Jellyfin. Unneeded during steady-state operation because `lldap` + `scripts/identity_sync.py` provisions accounts automatically. Config persists in `config/wizarr`. |
| **`unpackerr`** | `golift/unpackerr:latest` | *(Daemon)* | *(None)* | Archive extractor watching `/data/torrents` for Radarr, Sonarr, and Lidarr. Standby because active trackers deliver unarchived media files. |

### 3.3 Document & Knowledge Standby Services (`compose/paperless.yml`, `compose/knowledge.yml`)

| Service | Image | Internal / Host Port | Commented Vhost | Sidelining Rationale & Reactivation Notes |
| :--- | :--- | :--- | :--- | :--- |
| **`paperless-gotenberg`** | `docker.io/gotenberg/gotenberg:8.20` | `3000/tcp` (internal) | *(None)* | Headless Chromium Office/email converter for Paperless-ngx. Standby to avoid idle Chromium RAM overhead while Paperless processes PDFs directly. |
| **`paperless-tika`** | `docker.io/apache/tika:latest` | `9998/tcp` (internal) | *(None)* | Apache Tika metadata/text extractor for Office documents. Standby alongside `paperless-gotenberg` to avoid idle JVM RAM consumption. |
| **`paperless-ai`** | `clusterzx/paperless-ai:latest` | `3000/tcp` (internal) | `paperless-ai.vrg.rocks` (`import forward_auth`) | LLM-backed document tagger for Paperless-ngx. Standby to avoid continuous background LLM polling and ChromaDB memory usage. State persists in `data/paperless-ai` (backed up in `stage_db_backups.sh`). |
| **`leafwiki`** | `ghcr.io/perber/leafwiki:latest` | `8080/tcp` (internal) | `leaf.vrg.rocks` (`import forward_auth`) | Go markdown wiki. Superseded in daily use by `Ignis` (`ignis.vrg.rocks`) and `Quartz` (`mind.vrg.rocks`). Data persists in `data/leafwiki`. |
| **`kavita`** | `lscr.io/linuxserver/kavita:latest` | `5000/tcp` (internal) | `kavita.vrg.rocks` (`import forward_auth`) | E-book, manga, and PDF reading server. Standby while reading happens on native devices. Config and SQLite DB persist in `config/kavita` (backed up in `stage_db_backups.sh`). |

### 3.4 Utilities Standby & Ops Services (`compose/utilities.yml`)

| Service | Image | Profile & Port | Commented Vhost | Sidelining Rationale & Reactivation Notes |
| :--- | :--- | :--- | :--- | :--- |
| **`vaultwarden`** | `vaultwarden/server:latest` | `standby`, `80/tcp` (internal) | `vault.vrg.rocks`, `pass.vrg.rocks` (`import forward_auth`) | Bitwarden-compatible password server. Standby while primary password management runs externally. Config and DB persist in `config/vaultwarden` (backed up in `stage_db_backups.sh`). |
| **`n8n`** | `docker.n8n.io/n8nio/n8n` | `standby`, `5678/tcp` (internal) | `n8n.vrg.rocks` (`import forward_auth`) | Workflow automation engine. Standby because Sol automations run via deterministic host LaunchAgents (`com.vrg.sol.db-stage`, `com.vrg.sol.identity-sync`) and Python/shell hooks (`torrent_finished.py`, `arr_symlink_dedupe.sh`, `pre-consumption.py`). State persists in `config/n8n` and `data/n8n`. |
| **`homeassistant`** | `ghcr.io/home-assistant/home-assistant:stable` | `standby`, `8123/tcp` (`network_mode: host`) | `home.vrg.rocks` (`import forward_auth`) | Smart home automation hub. Standby while IoT bridges are paused. Config persists in `config/homeassistant`. |
| **`rclone`** | `rclone/rclone:latest` | `ops`, `127.0.0.1:53682` | *(None)* | On-demand CLI and OAuth token helper (`docker compose --profile ops run --rm rclone ...`), used alongside Backrest (`backrest.vrg.rocks`) for OneDrive cloud transport. |

> [!NOTE]
> `homebox` (`inv.vrg.rocks`, `:7745`) was previously listed in standby prior to October 18, 2026. Its SQLite database and Tinyauth OIDC integration were repaired in Era 4, and `homebox` is now an **active `(healthy)` production container** (`compose/utilities.yml`).

---

## 4. Retired & Purged Legacy Services Registry (Era 1 - Era 4)

The 20 services below were permanently retired across Eras 1 through 4. During the October 19-20, 2026 Wave 2 and Phase 2 cleanups, their Compose blocks were removed from `compose/*.yml`, their entries were removed from `ports.json`, and their leftover host directories (`config/{jellyfin_metal,plex,cross-seed,homarr,calibre,calibre-web,qbit_manage,syncthing,flood}`, `data/{authentik,uptime-kuma,dockge,syncthing}`, `data/arcane/arcane.francis.db*`) were deleted from `/Users/vrg/Documents/Sol`.

| Retired Service | Era Retired | Former Image | Successor on Sol | Retirement & Purge Rationale |
| :--- | :---: | :--- | :--- | :--- |
| **`authentik-server`**, **`authentik-worker`**, **`authentik-postgresql`** | Era 4 (`2026-10-19`) | `ghcr.io/goauthentik/server:2026.5.3`, `postgres:16-alpine` | **`tinyauth` v5.2.0** + **`lldap`** + **`identity_sync.py`** | Replaced 3 containers (`~543 MiB` RAM, continuous worker polling, `224 MB` PG cluster) with `tinyauth` (`~29 MiB`) + `lldap` (`~12 MiB`), saving `~502 MiB` RAM while achieving 0-click Google SSO and OIDC/LDAP unification. Blueprint preserved in `11_AUTHENTICATION_AND_SSO_STRATEGY.md` Section 4. |
| **`flaresolverr`** | Era 4 (`2026-10-20`) | `ghcr.io/flaresolverr/flaresolverr:latest` | **`byparr`** (`byparr.vrg.rocks`, alias `flaresolverr`) | Replaced by `byparr`, which handles modern Cloudflare Turnstile challenges. `flaresolverr.vrg.rocks` redirects permanently (`301`) to `https://byparr.vrg.rocks{uri}`. |
| **`cross-seed`** | Era 4 (`2026-10-20`) | `ghcr.io/cross-seed/cross-seed:6` | **`qui` v1.32.0** (`qui.vrg.rocks`) | Retired after re-pointing the 7 recoverable cross-seed symlinks in `data/torrents/cross-seed-links/`. Commented `cs.vrg.rocks` route retained in `Caddyfile` only as a placeholder. |
| **`qbit_manage`** | Era 4 (`2026-10-19`) | `ghcr.io/stuffanthings/qbit_manage:latest` | **`qui` v1.32.0** + **`torrent_finished.py`** | Replaced by QUI's 26-tracker registry and 10 FUP seed/ratio rules plus deterministic post-download symlink automation. |
| **`flood`** | Era 4 (`2026-10-19`) | `jesec/flood:latest` | **`qui` v1.32.0** (`qui.vrg.rocks`) | Replaced by QUI (`~38 MiB` Go binary vs Node.js runtime) alongside native `qb.vrg.rocks`. |
| **`dockge`** | Era 4 (`2026-10-19`) | `louislam/dockge:1` | **`arcane`** (`arcane.vrg.rocks`) | Replaced by Arcane (`getarcaneapp/arcane`), which provides native Tinyauth OIDC and full Compose V2 management. |
| **`uptime-kuma`** | Era 4 (`2026-10-19`) | `louislam/uptime-kuma:1` | **`glance`** (`dash.vrg.rocks`) | Replaced by Glance's native `monitor` widgets (`9` core monitors on `/sol` and `26` full-stack monitors on `/stats`) with zero background SQLite write churn. |
| **`homarr`** | Era 4 (`2026-10-19`) | `ghcr.io/homarr-labs/homarr:latest` | **`glance`** (`dash.vrg.rocks`) | Replaced by declarative YAML configuration in Glance (`config/glance/config/glance.yml`). |
| **`calibre`** & **`calibre-web`** | Era 4 (`2026-10-19`) | `lscr.io/linuxserver/calibre:latest`, `calibre-web:latest` | **`kavita`** (standby) / **`pdf.vrg.rocks`** (BentoPDF) | Removed heavy KasmVNC desktop container (`calibre`) and legacy Python web wrapper (`calibre-web`). |
| **`rclone-gui`** | Era 4 (`2026-10-19`) | `rclone/rclone:latest` (`--rc-web-gui`) | **`backrest`** (`backrest.vrg.rocks`) + **`rclone`** (`ops`) | Replaced by Backrest's web UI for Restic + OneDrive backup orchestration. |
| **`authelia`** & **`authelia-redis`** | Era 3 (`2026-07-21`) | `authelia/authelia:latest`, `redis:alpine` | **`tinyauth` v5.2.0** + **`lldap`** | Era 1-3 YAML forward-auth engine, superseded first by Authentik and now by Tinyauth + LLDAP. |
| **`nginx-proxy-manager`** | Era 1 (`2025-05`) | `jc21/nginx-proxy-manager:latest` | **`caddy`** (`caddy:latest` v2.11.7) | Replaced GUI-driven proxy config with declarative `Caddyfile` and automatic Let's Encrypt TLS/HTTP3. |
| **`plex`** | Era 2 (`2025-06-16`) | `plexinc/pms-docker:latest` | **`jellyfin`** (`watch.vrg.rocks`) | Replaced proprietary cloud-tied media server with 100% local open-source Jellyfin. |
| **`overseerr`** / **`jellyseerr`** | Era 2 / Era 3 (`2026-09-13`) | `sctx/overseerr`, `fallenbagel/jellyseerr` | **`seerr`** (`request.vrg.rocks`) | Consolidated into upstream unified `ghcr.io/seerr-team/seerr:latest` (`43` historical requests merged). |
| **`syncthing`** | Era 2 (`2025-09`) | `lscr.io/linuxserver/syncthing:latest` | **`copyparty`** (`files.vrg.rocks`) + **`ignis`** (`ignis.vrg.rocks`) | Replaced background P2P file sync with Copyparty WebDAV and Ignis Obsidian vault sync. |
| **`filebrowser`** | Era 2 (`2025-09-07`) | `filebrowser/filebrowser:s6` | **`copyparty`** (`files.vrg.rocks`) | Replaced by Copyparty for multi-volume WebDAV, zero-click `Remote-Email` header auth, and high-speed transfers. |
| **`obsidian-remote`** / **`obsidian`** | Era 2 (`2025-07-25`) | `sytone/obsidian-remote`, `linuxserver/obsidian` | **`ignis`** (`ignis.vrg.rocks`) + **`mind.vrg.rocks`** (Quartz) | Replaced VNC browser containers with Ignis API sync and static Quartz publishing. |
| **`readarr`** | Era 2 (`2025-09`) | `lscr.io/linuxserver/readarr:develop` | *(Retired)* | Upstream project retired by Servarr team. |
| **`bitwarden`** | Era 2 (`2025-10-06`) | `ghcr.io/bitwarden/self-host:beta` | **`vaultwarden`** (standby) | Replaced heavy multi-container enterprise image with lightweight Rust `vaultwarden/server:latest` (standby). |

---

## 5. Port & Network Isolation Matrix for Standby Services

When activating any standby service, review the port and network considerations below:

| Standby Service | Port & Network Mode | Bridge / Host Isolation Notes |
| :--- | :--- | :--- |
| **`gatus`**, **`dozzle`**, **`leafwiki`** | `8080/tcp` on `sol_default` bridge | Safe to run alongside active `glance` (`8080`), `qbittorrent` (`8080`), and `ignis` (`8080`) because Docker bridge networking isolates container ports by service hostname (`http://gatus:8080`, `http://dozzle:8080`, `http://leafwiki:8080`). |
| **`beszel`** | `8090/tcp` on `sol_default` bridge | Safe alongside active `pocketbase` (`8090`) on the bridge network (`http://beszel:8090` vs `http://pocketbase:8090`). |
| **`beszel-agent`** | `45876/tcp` (`network_mode: host`) | Binds host port `45876` directly on macOS to read host hardware sensors. Ensure no host process occupies `45876`. |
| **`paperless-gotenberg`**, **`paperless-ai`** | `3000/tcp` on `sol_default` bridge | Safe alongside active `tinyauth` (`3000`) and `airtrail` (`3000`) on the bridge network (`http://paperless-gotenberg:3000`, `http://paperless-ai:3000`). |
| **`vaultwarden`** | `80/tcp` on `sol_default` bridge | Safe alongside active `caddy` (`80`) and `ntfy` (`80`) on the bridge network (`http://vaultwarden:80`). Never map host port `80:80`. |
| **`homeassistant`** | `8123/tcp` (`network_mode: host`, `privileged: true`) | Binds host port `8123` on macOS. Caddy proxies to `http://host.docker.internal:8123` when `home.vrg.rocks` is uncommented. |
| **`jellyfin-metal`** *(Native)* | `8097/tcp` (macOS host process) | Binds host port `8097`. Caddy proxies to `http://host.docker.internal:8097` when `metal.vrg.rocks` is uncommented. |
| **`rclone`** (`ops`) | `127.0.0.1:53682` (loopback only) | Ephemeral CLI/OAuth container (`docker compose --profile ops run --rm rclone ...`). |
