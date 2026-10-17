# 04. Standby, Sidelined & Legacy Service Registry

> **Scope:** Audit of every standby service declared with Docker Compose V2 `profiles: ["standby"]` (and `profiles: ["ops"]`) across `compose/*.yml`, every commented standby vhost in `Caddyfile`, and every service archived in `docs/archive/` (`docker-compose-backup.yml`, `docker-compose-archive.yml`).  
> **Purpose:** Document historical design decisions, sidelining rationale, port conflict analyses, and reactivation recipes.  
> **Last Synced to Ground Truth:** 2026-10-17  

---

## 1. Executive Summary of Stack Evolution

Over the lifecycle of **Sol**, the server architecture moved through several phases to improve performance, security, and maintainability:

1. **Edge Routing & Ingress:** Shifted from `Nginx Proxy Manager` (GUI-driven) to `Caddy v2` (declarative, automatic HTTPS, HTTP/3, and embedded file serving).
2. **Authentication & Identity:** Shifted from `Authelia` to `Authentik` (unified OIDC, LDAP, customizable outpost templates, and Caddy forward-auth).
3. **Media & Requests:** Shifted from `Plex` + `Overseerr` to `Jellyfin` + `Seerr` (formerly `Jellyseerr`) (100% open-source, local playback freedom, zero cloud account dependencies). A native macOS `jellyfin-metal` instance on port `8097` adds Apple VideoToolbox transcoding.
4. **File Logistics & Storage:** Shifted from `File Browser` to `Copyparty` (high-speed multi-user WebDAV, audio streaming, and deduplication).
5. **Dashboard & Administration:** Shifted from `Homarr` + `Dockge` to `Glance` (lightweight YAML dashboard) + `Arcane` (modern Docker stack manager with OIDC).
6. **Digital Notes & PKM:** Shifted from VNC-based `Obsidian` containers to `Quartz` (static digital garden) and `Ignis`.
7. **Cloudflare Challenge Solving:** Shifted from `FlareSolverr` to `Byparr` (`ghcr.io/thephaseless/byparr:latest`) as the active Turnstile solver. Byparr carries the network alias `flaresolverr`, so Prowlarr settings did not change.
8. **Standby Declaration Model:** Shifted from commented-out YAML blocks in `docker-compose.yml` to full service definitions with `profiles: ["standby"]` in each domain file. Standby services now pass `docker compose config` validation, keep their labels, and start with one command.

### Inventory Totals

| Tier | Count | Location |
| :--- | :---: | :--- |
| Active (default profile) | `24` | `compose/*.yml`, no `profiles:` key |
| Standby / Ops (profiled) | `26` | `compose/*.yml`, `profiles: ["standby"]` (25) or `profiles: ["ops", "standby"]` (`rclone`) |
| Native macOS | `1` | `jellyfin-metal` (`scripts/setup_jellyfin_metal.py`) |
| Commented standby vhosts | `18` | `Caddyfile` sections marked `Standby ... Routes` |
| Archived / decommissioned | `10` rows | `docs/archive/docker-compose-archive.yml` and `bitwarden.env` |

---

## 2. Standard Reactivation Procedure

Every standby service follows the same recipe:

```bash
# 1. Start the container (profile flag is required, otherwise compose ignores the service)
docker compose --profile standby up -d <service>

# 2. If the service has a commented vhost, uncomment it in Caddyfile, then reload Caddy
docker exec caddy caddy reload --config /etc/caddy/Caddyfile

# 3. Optional: update ports.json "status" from "standby" to "active"
```

> [!WARNING]
> `docker compose --profile standby up -d` with no service name starts all 26 profiled containers at once. That includes `rclone`, which has `restart: "no"` and exits without a command, and `homeassistant`, which runs `privileged: true` with `network_mode: host`. Always name the service.

To return a service to standby, run `docker compose stop <service>` (or `docker compose rm -sf <service>`) and comment its vhost again.

---

## 3. Standby Services Catalog (`profiles: ["standby"]`)

These services exist as full definitions in `compose/*.yml` and stay stopped unless started with `--profile standby`.

---

### `flaresolverr` (`compose/media.yml`)
* **Image:** `ghcr.io/flaresolverr/flaresolverr:latest`
* **Original Function:** Proxy server that bypasses Cloudflare and DDoS-GUARD protection for Prowlarr indexers.
* **Original Ports / Proxy:** Internal `8191/tcp`. `flaresolverr.vrg.rocks` now routes to `byparr:8191`.
* **Sidelining Rationale:** Replaced by `byparr` as the active Cloudflare Turnstile solver. Preserved as a fallback (Glance description: `Legacy Cloudflare Challenge Solver (Standby)`).
* **Reactivation Notes:**
  - Stop `byparr` first (`docker compose stop byparr`). Byparr holds the network alias `flaresolverr`, and two containers answering one name produce round-robin DNS.
  - Then run `docker compose --profile standby up -d flaresolverr`. Prowlarr keeps calling `http://flaresolverr:8191`.
  - To expose it at the edge, change the `byparr.vrg.rocks, flaresolverr.vrg.rocks` upstream to `http://flaresolverr:8191`.

---

### `recyclarr` (`compose/media.yml`)
* **Image:** `ghcr.io/recyclarr/recyclarr:latest`
* **Original Function:** TRaSH Guides sync engine for Radarr and Sonarr custom formats and quality profiles.
* **Configuration:** `user: "${PUID}:${PGID}"`, `CRON_SCHEDULE: "@daily"`, config at `config/recyclarr`. No port and no vhost (Glance URL points to `https://radarr.vrg.rocks`).
* **Sidelining Rationale:** Declared but not yet activated. [07_MEDIA_STACK_DEEP_DIVE.md](07_MEDIA_STACK_DEEP_DIVE.md) records `0` Custom Formats in Radarr and Sonarr and recommends running it.
* **Reactivation Notes:** Write `config/recyclarr/recyclarr.yml` with Radarr and Sonarr API keys first, then `docker compose --profile standby up -d recyclarr`.

---

### `wizarr` (`compose/media.yml`)
* **Image:** `ghcr.io/wizarrrr/wizarr:latest`
* **Original Function:** Automated invitation and user onboarding portal for Jellyfin.
* **Original Ports / Proxy:** Internal `5690/tcp`, routed at `https://wizarr.vrg.rocks` (commented).
* **Sidelining Rationale:** Sol runs as a single-family private ecosystem. User onboarding automation is unnecessary for static accounts.
* **Reactivation Notes:** Config and database persist in `config/wizarr` (mounted at `/data`). `DISABLE_BUILTIN_AUTH: "false"`.

---

### `unpackerr` (`compose/download.yml`)
* **Image:** `golift/unpackerr:latest`
* **Original Function:** Automated archive extractor for Servarr downloads.
* **Configuration:** `user: "${PUID}:${PGID}"`, watches `UN_FOLDER_0_PATH: /data/torrents`, connects to `http://sonarr:8989`, `http://radarr:7878`, `http://lidarr:8686`. Glance parent: `qbittorrent`.
* **Sidelining Rationale:** Not required while indexers deliver unpacked releases.
* **Reactivation Notes:** Set `SONARR_API_KEY`, `RADARR_API_KEY`, and `LIDARR_API_KEY` in `.env` (they default to empty strings), then start the service.

---

### `qbit_manage` (`compose/download.yml`)
* **Image:** `ghcr.io/stuffanthings/qbit_manage:latest`
* **Original Function:** CLI and API tool that manages qBittorrent tags and categories, removes unregistered torrents, and enforces seed limits.
* **Original Ports / Proxy:** Internal `8181/tcp` (`QBT_PORT: 8181`, `QBT_WEB_SERVER: "true"`), routed at `https://qbm.vrg.rocks` / `https://qbit_manage.vrg.rocks` (commented).
* **Sidelining Rationale:** Sidelined to avoid automated deletion or modification of active seeding torrents during tracker migration. `Cross-Seed` handles automated injection independently.
* **Reactivation Notes:** Configuration exists at `config/qbit_manage/config.yml`. Requires qBittorrent credentials. Every destructive toggle (`QBT_REM_UNREGISTERED`, `QBT_REM_ORPHANED`, `QBT_SHARE_LIMITS`, and others) defaults to `"false"`, and `QBT_RUN: "false"` with `QBT_SCHEDULE: 1440`. It is the only service that mounts `${EXTERNAL_DRIVE_01}` (`/ext01:rw`).

---

### `flood` (`compose/download.yml`)
* **Image:** `jesec/flood:latest`
* **Original Function:** Modern Node.js web alternative frontend for qBittorrent.
* **Original Ports / Proxy:** Internal `3000/tcp` (previously host `42024:3000`), routed at `https://flood.vrg.rocks` (commented).
* **Sidelining Rationale:** Native qBittorrent Web UI (`https://qb.vrg.rocks`) is preferred for lower overhead and direct API feature access.
* **Reactivation Notes:** Command flags `--auth=none`, `--qburl=http://qbittorrent:${QBITTORRENT_WEBUI_PORT:-8080}`, `--qbuser=${FLOOD_QBITTORRENT_USERNAME:-VRG}`, `--qbpass=${CORE_PASSWORD:-}`. Uses `restart: always` and `depends_on: qbittorrent`. Because `--auth=none`, keep `import authentik` on its vhost.

---

### `paperless-gotenberg` & `paperless-tika` (`compose/paperless.yml`)
* **Images:** `docker.io/gotenberg/gotenberg:8.20`, `docker.io/apache/tika:latest`
* **Original Function:** Document conversion engines that turn Microsoft Office files (`.docx`, `.xlsx`), emails (`.eml`), and other formats into PDF before Paperless OCR.
* **Original Ports:** Gotenberg `3000/tcp` (`--chromium-disable-javascript=true`, `--chromium-allow-list=file:///tmp/.*`), Tika `9998/tcp`.
* **Sidelining Rationale:** Paperless on Sol mostly processes scanned PDF receipts, statements, and bills through the custom `pre-consumption.py` script. Gotenberg and Tika run heavy Chromium and Java virtual machines that consume significant RAM.
* **Reactivation Notes:**
  - `docker compose --profile standby up -d paperless-gotenberg paperless-tika`.
  - In `compose/paperless.yml`, uncomment the `paperless-gotenberg` and `paperless-tika` `depends_on` entries and `PAPERLESS_TIKA_ENABLED: 1`, `PAPERLESS_TIKA_GOTENBERG_ENDPOINT`, and `PAPERLESS_TIKA_ENDPOINT` on `paperless-webserver`. If you uncomment `depends_on` without starting the profile, `paperless-webserver` fails to start.

---

### `paperless-ai` (`compose/paperless.yml`)
* **Image:** `clusterzx/paperless-ai:latest`
* **Original Function:** Automated AI document analysis, tagging, correspondent classification, and summarizing through local or remote LLMs with ChromaDB vector search.
* **Original Ports / Proxy:** Internal `3000/tcp`, routed at `https://paperless-ai.vrg.rocks` (commented, with `import authentik`).
* **Sidelining Rationale:** Disabled to avoid continuous LLM API usage and memory pressure. Paperless rule-based matching with pre-consumption scripts covers document sorting needs.
* **Reactivation Notes:** Database and vector index persist in `data/paperless-ai`.

---

### `gatus` (`compose/monitoring.yml`)
* **Image:** `twinproduction/gatus:latest`
* **Original Function:** Service health and status page.
* **Original Ports / Proxy:** `expose: 8080`, routed at `https://status.vrg.rocks` (commented, no `import authentik`, public status page).
* **Sidelining Rationale:** Preserved under the standby profile alongside the other monitoring tools. Glance covers day-to-day container health.
* **Reactivation Notes:** Endpoint definitions live in `config/gatus`. Shares internal port `8080` with `glance`, `qbittorrent`, `ignis`, `dozzle`, `leafwiki`, and `calibre`, which is safe on the bridge.

---

### `dozzle` (`compose/monitoring.yml`)
* **Image:** `amir20/dozzle:latest`
* **Original Function:** Real-time Docker container log viewer with shell access (`DOZZLE_ENABLE_ACTIONS: "true"`, `DOZZLE_ENABLE_SHELL: "true"`).
* **Original Ports / Proxy:** Internal `8080/tcp` (previously host `40020:8080`), routed at `https://dozzle.vrg.rocks` (commented).
* **Sidelining Rationale:** `Arcane` provides integrated container logging, terminal shell execution, and Docker Compose management with Authentik OIDC, so a standalone log viewer is redundant.
* **Reactivation Notes:**
  - `docker compose --profile standby up -d dozzle`, then uncomment `dozzle.vrg.rocks` in `Caddyfile`.
  - Shell actions are enabled, so keep `import authentik` on the vhost.

---

### `beszel` & `beszel-agent` (`compose/monitoring.yml`)
* **Image:** `henrygd/beszel:latest`, `henrygd/beszel-agent:latest`
* **Original Function:** Lightweight server resource and hardware monitoring hub with host agent daemon.
* **Original Ports / Proxy:** Hub `8090/tcp` (previously host `40010:8090`, now `expose: 8090`), Agent `45876/tcp` (`network_mode: host`, `LISTEN: 45876`, `HUB_URL: http://beszel:8090`), routed at `https://beszel.vrg.rocks` (commented).
* **Environment Keys:** `BESZEL_AGENT_KEY`, `BESZEL_AGENT_TOKEN` in `.env`.
* **Sidelining Rationale:** System health and Docker container states are monitored directly on the Glance dashboard (`dash.vrg.rocks`).
* **Reactivation Notes:**
  - Hub data persists in `data/beszel`. Agent fingerprint persists in `data/beszel_agent`.
  - Agent requires `network_mode: host` to read hardware metrics. With host networking, `HUB_URL: http://beszel:8090` cannot resolve the bridge hostname, so verify the agent reaches the hub after start.

---

### `homarr` (`compose/monitoring.yml`)
* **Image:** `ghcr.io/homarr-labs/homarr:latest`
* **Original Function:** Customizable homelab dashboard.
* **Original Ports / Proxy:** Internal `7575/tcp` (previously host `7575:7575`), routed at `https://homarr.vrg.rocks` (commented).
* **Sidelining Rationale:** Superseded by `Glance` (`glanceapp/glance`), a faster, lighter, code-configured YAML dashboard with Sol branding.
* **Reactivation Notes:** Config and database remain intact in `config/homarr` (mounted at `/appdata`). Requires `HOMARR_SECRET_KEY`.

---

### `dockge` (`compose/monitoring.yml`)
* **Image:** `louislam/dockge:1`
* **Original Function:** Web-based Docker Compose stack manager.
* **Original Ports / Proxy:** Internal `5001/tcp` (previously host `40030:5001`), routed at `https://dockge.vrg.rocks` (commented).
* **Sidelining Rationale:** Succeeded by `Arcane`, which offers a better UI, modern Docker Compose V2 support, and native OIDC integration with Authentik.
* **Reactivation Notes:** Stacks database persists in `data/dockge`. Mounts `/opt/stacks` (`DOCKGE_STACKS_DIR`) and the Docker socket read-write.

---

### `uptime-kuma` (`compose/monitoring.yml`)
* **Image:** `louislam/uptime-kuma:1`
* **Original Function:** Self-hosted uptime and HTTP/TCP service monitor with push notifications.
* **Original Ports / Proxy:** Internal `3001/tcp` (previously host `40040:3001`), routed at `https://kuma.vrg.rocks` (commented).
* **Sidelining Rationale:** Service availability monitoring is aggregated into Glance widgets. Background pings were minimized to conserve host resources.
* **Reactivation Notes:** SQLite database and monitoring history persist in `data/uptime-kuma/kuma.db`. Uses `restart: always`.

---

### `kavita`, `calibre` & `calibre-web` (`compose/knowledge.yml`)
* **Images:** `lscr.io/linuxserver/kavita:latest`, `lscr.io/linuxserver/calibre:latest`, `lscr.io/linuxserver/calibre-web:latest`
* **Original Function:** Digital e-book, comic, and PDF management and web reader suite.
* **Original Ports / Proxy:**
  - Kavita: `5000/tcp` (`https://kavita.vrg.rocks`, commented)
  - Calibre: `8080/tcp` (`https://calibre.vrg.rocks`, commented)
  - Calibre-Web: `8083/tcp` (`https://calibre-web.vrg.rocks`, commented, `OAUTHLIB_RELAX_TOKEN_SCOPE: 1`)
* **Sidelining Rationale:**
  - `calibre` runs a full desktop GUI inside an X11/VNC container, which consumes memory on the host Mac (historic compose comment: `# It's the desktop app in a VM. Keep disabled.`). Glance description: `E-Book Desktop VM`.
  - Book reading workflows are handled locally on reader devices or through Apple Books / Kindle.
* **Reactivation Notes:** Media folder `data/media/books` and configurations in `config/kavita`, `config/calibre`, and `config/calibre-web` remain intact.

---

### `leafwiki` (`compose/knowledge.yml`)
* **Image:** `ghcr.io/perber/leafwiki:latest`
* **Original Function:** Minimalist markdown wiki and digital garden platform.
* **Original Ports / Proxy:** Internal `8080/tcp`, routed at `https://leaf.vrg.rocks` (commented). The historic `wiki.vrg.rocks` alias is not present in the current `Caddyfile`.
* **Sidelining Rationale:** Superseded by `Quartz` (`quartz/`), which builds fast static HTML deployed through Caddy (`https://mind.vrg.rocks`).
* **Reactivation Notes:** SQLite databases and markdown root trees persist in `data/leafwiki`. `LEAFWIKI_JWT_SECRET` and `LEAFWIKI_ADMIN_PASSWORD` both read `${CORE_PASSWORD:-}`. `LEAFWIKI_ALLOW_INSECURE: "true"`.

---

### `homebox` (`compose/utilities.yml`)
* **Image:** `ghcr.io/sysadminsmedia/homebox:latest`
* **Original Function:** Asset and physical home inventory tracking database, backend for the `scan.vrg.rocks` PWA.
* **Original Ports / Proxy:** Internal `7745/tcp`, routed at `https://inv.vrg.rocks` (commented).
* **Sidelining Rationale:** Moved from active to standby pending local SQLite database repair (Glance description: `Home Inventory Management (Standby - Pending DB Repair)`).
* **Hardening Applied:** The commented vhost restricts CORS to `Origin https://scan.vrg.rocks` (fixed `Access-Control-Allow-Origin`, `Vary Origin`) instead of reflecting any `Origin`. It now also imports `security_headers`.
* **Reactivation Notes:**
  - Repair `data/homebox/homebox.db` locally first (for example, `sqlite3 homebox.db "PRAGMA integrity_check;"` on a copy).
  - `docker compose --profile standby up -d homebox`, uncomment the `inv.vrg.rocks` block, and reload Caddy.
  - `scan.vrg.rocks` stays active, but its API calls fail until this service returns.

---

### `vaultwarden` / `bitwarden` (`compose/utilities.yml`)
* **Images:** `vaultwarden/server:latest` (standby in compose). `ghcr.io/bitwarden/self-host:beta` is archived only.
* **Original Function:** Self-hosted Bitwarden-compatible password manager.
* **Original Ports / Proxy:** Internal `80/tcp` (`DOMAIN: https://vault.vrg.rocks`) or historic `3333:8080` for Bitwarden, routed at `https://vault.vrg.rocks` and `https://pass.vrg.rocks` (commented).
* **Sidelining Rationale:** Password management runs on primary ecosystem password solutions. The self-hosted instance is kept on standby.
* **Reactivation Notes:** Configuration in `config/vaultwarden`. `BW_*` keys in `.env.example` belong to the archived Bitwarden deployment (`bitwarden.env` in `docs/archive/`).

---

### `n8n` (`compose/utilities.yml`)
* **Image:** `docker.n8n.io/n8nio/n8n`
* **Original Function:** Visual node-based workflow automation and webhook platform.
* **Original Ports / Proxy:** Internal `5678/tcp`, routed at `https://n8n.vrg.rocks` (commented). `N8N_HOST` and `WEBHOOK_URL` derive from `${N8N_SUBDOMAIN:-n8n}.${N8N_DOMAIN_NAME:-vrg.rocks}`.
* **Sidelining Rationale:** Automations on Sol run through native shell scripts (`backup.sh`, `ntfy_notify.sh`), Python hooks (`pre-consumption.py`), and *arr webhooks.
* **Reactivation Notes:** Stored workflows and SQLite state persist in `config/n8n` and `data/n8n`.

---

### `homeassistant` (`compose/utilities.yml`)
* **Image:** `ghcr.io/home-assistant/home-assistant:stable`
* **Original Function:** Open-source smart home and IoT device automation hub.
* **Original Ports / Proxy:** Host `8123/tcp` (`network_mode: host`, `privileged: true`), routed through Caddy upstream `http://host.docker.internal:8123` at `https://home.vrg.rocks`.
* **Sidelining Rationale:** IoT smart home bridges run independently or are paused during hardware re-architecture.
* **Reactivation Notes:**
  - Configurations, automations, and SQLite history persist in `config/homeassistant`.
  - The `home.vrg.rocks` vhost is **not** commented. It stays active and returns an upstream error until the container starts.

---

### `rclone` (Task) & `rclone-gui` (`compose/utilities.yml`)
* **Image:** `rclone/rclone:latest`
* **Original Function:** Rclone web interface (`5572/tcp`, `rcd --rc-web-gui --rc-addr :5572 --rc-user ${RCLONE_GUI_USER:-admin} --rc-pass ${CORE_PASSWORD:-admin}`) and OAuth token callback server (`127.0.0.1:53682`).
* **Profiles:** `rclone` uses `profiles: ["ops", "standby"]` with `restart: "no"`. `rclone-gui` uses `profiles: ["standby"]`.
* **Sidelining Rationale:** Not persistent containers. `scripts/backup.sh` prefers the native host `rclone` CLI and falls back to an ephemeral container: `docker compose --profile ops run --rm rclone sync /source OneDrive:Sol --filter-from <filter> --backup-dir OneDrive:Sol-archive/<TIMESTAMP> ...`.
* **Reactivation Notes:** Configuration lives in `config/rclone/rclone.conf` and `config/rclone/filter.txt` (template `filter.txt.example`). `rclone-gui` exposes `--rc-pass` from `CORE_PASSWORD`, so keep `import authentik` on `rclone.vrg.rocks`.

---

## 4. Legacy Archived Services Registry (`docs/archive/docker-compose-archive.yml`)

These services were fully decommissioned. Their definitions are archived in `docs/archive/` and have no service block in `compose/*.yml`.

| Decommissioned Service | Base Image | Previous Host Ports | Successor / Replacement | Migration Rationale |
| :--- | :--- | :--- | :--- | :--- |
| **`authelia` & `authelia-redis`** | `authelia/authelia:latest` | `9091` (Internal), `6379` | **`Authentik`** (`ghcr.io/goauthentik/server`) | Authentik provides better OIDC support, a user management UI, LDAP integration, and flexible Caddy outpost integration. |
| **`nginx-proxy-manager`** | `jc21/nginx-proxy-manager:latest` | `80:80`, `443:443`, `81:81` | **`Caddy v2`** (`caddy:${CADDY_TAG:-2}`) | Caddy removed GUI-based proxy fragility and offers declarative text configuration, native HTTP/3, and automatic TLS lifecycle management. |
| **`plex`** | `plexinc/pms-docker:latest` | `32400:32400`, `32469:32469` | **`Jellyfin`** (`lscr.io/linuxserver/jellyfin`) + **`jellyfin-metal`** | Jellyfin is 100% open-source, needs no external account authentication, supports free hardware transcoding, and avoids telemetry. |
| **`overseerr` / `jellyseerr`** | `fallenbagel/jellyseerr:latest` | `5055` | **`Seerr`** (`ghcr.io/seerr-team/seerr`) | Upstream unification of Overseerr & Jellyseerr into Seerr. |
| **`readarr`** | `lscr.io/linuxserver/readarr:develop` | `8787:8787` | *Paused / Inactive* | Sidelined along with Calibre during e-book workflow restructuring. |
| **`filebrowser`** | `filebrowser/filebrowser:s6` | `9876:80` | **`Copyparty`** (`copyparty/ac:latest`) | Copyparty offers much higher upload throughput, native WebDAV, audio streaming, and advanced permission flags. |
| **`obsidian-remote`** | `ghcr.io/sytone/obsidian-remote:latest` | `12080`, `12443` | **`Ignis`** + **`Quartz`** | Web-based Obsidian VNC was resource-heavy. Replaced by static Quartz publishing and Ignis vault synchronization. |
| **`obsidian` (KasmVNC)** | `lscr.io/linuxserver/obsidian:latest` | `3000:3000`, `3001:3001` | **`Ignis`** + **`Quartz`** | Desktop Obsidian inside Docker was replaced with local native Obsidian syncing with server storage. |
| **`syncthing`** | `lscr.io/linuxserver/syncthing:latest` | `8384`, `22000`, `21027/udp` | **`Copyparty`** / **`Ignis`** | Replaced by direct WebDAV mounts and local vault sync to minimize background sync conflicts. |
| **`bitwarden`** | `ghcr.io/bitwarden/self-host:beta` | `3333:8080` | **`vaultwarden`** (standby) | Archived with `bitwarden.env`. Vaultwarden is the retained standby option. |

---

## 5. Port Conflict Matrix & Reactivation Guide

If any standby or legacy service is reactivated, the table below highlights potential collisions and required adjustments:

| Standby Service | Internal Port | Potential Conflict Target | Conflict Resolution Strategy |
| :--- | :--- | :--- | :--- |
| **`flaresolverr`** | `8191` | `byparr` (`8191`, alias `flaresolverr`) | **Name collision, not only port.** Stop `byparr` before starting `flaresolverr`, or remove the alias. Never run both. |
| **`gatus`** | `8080` | `glance`, `qbittorrent`, `ignis` (`8080`) | Bridge network isolates ports per container. Address it as `http://gatus:8080`. |
| **`beszel`** | `8090` | None | Direct routing via Caddy `beszel.vrg.rocks -> http://beszel:8090`. |
| **`beszel-agent`** | `45876` | Host port `45876` | Uses `network_mode: host`. Ensure no host process binds `45876`. |
| **`dozzle`** | `8080` | `glance` (`8080`), `qbittorrent` (`8080`), `calibre` (`8080`) | All services share the bridge network. Address by container hostname (`http://dozzle:8080`), not localhost. |
| **`flood`** | `3000` | `paperless-gotenberg` (`3000`), `paperless-ai` (`3000`) | Addressed safely by container name (`http://flood:3000`). |
| **`uptime-kuma`**| `3001` | None | Direct routing via Caddy `kuma.vrg.rocks -> http://uptime-kuma:3001`. |
| **`kavita`** | `5000` | None | Direct routing via Caddy `kavita.vrg.rocks -> http://kavita:5000`. |
| **`calibre-web`**| `8083` | None | Direct routing via Caddy `calibre-web.vrg.rocks -> http://calibre-web:8083`. |
| **`homebox`** | `7745` | None | Repair SQLite DB first, then uncomment `inv.vrg.rocks`. |
| **`vaultwarden`** | `80` | `ntfy` (`80`), `caddy` (`80`) | Use container hostname `http://vaultwarden:80` inside the Docker network. Never map host port `80:80`. |
| **`homeassistant`**| `8123` | Host port `8123` | Uses `network_mode: host`. Caddy routes via `http://host.docker.internal:8123`. |
| **`rclone`** | `53682` | Host loopback `53682` | Bound to `127.0.0.1:53682` only. Run one-shot with `docker compose --profile ops run --rm rclone ...`. |
| **`authelia`** | `9091` | `authentik` (`9000`) | Legacy service. Do NOT reactivate alongside Authentik, because the two Caddy forward-auth handlers would conflict. |
