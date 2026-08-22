# 04. Inactive, Sidelined & Legacy Service Registry

> **Scope:** Comprehensive audit of all commented-out, inactive, and archived container services found across `docker-compose.yml`, `docker-compose-backup.yml`, `docker-compose-archive.yml`, and `Caddyfile`.  
> **Purpose:** Document historical design decisions, rationales for deprecation or sidelining, port conflict analyses, and reactivation recipes.

---

## 1. Executive Summary of Stack Evolution

Over the lifecycle of **Sol**, the server architecture has transitioned through several major evolutionary phases to maximize performance, security, and maintainability:

1. **Edge Routing & Ingress:** Shifted from `Nginx Proxy Manager` (GUI-driven) to `Caddy v2` (declarative, automatic HTTPS, HTTP/3, and embedded file serving).
2. **Authentication & Identity:** Shifted from `Authelia` to `Authentik` (delivering unified OIDC, LDAP, customizable outpost templates, and Caddy forward-auth).
3. **Media & Requests:** Shifted from `Plex` + `Overseerr` to `Jellyfin` + `Jellyseerr` (100% open-source, local playback freedom, zero cloud account dependencies).
4. **File Logistics & Storage:** Shifted from `File Browser` to `Copyparty` (delivering ultra-high-speed multi-user WebDAV, audio streaming, and deduplication).
5. **Dashboard & Administration:** Shifted from `Homarr` + `Dockge` to `Glance` (ultra-lightweight YAML dashboard) + `Arcane` (modern Docker stack manager with OIDC).
6. **Digital Notes & PKM:** Shifted from bulky VNC-based `Obsidian` containers to `Quartz` (high-performance static digital garden) and `Ignis`.

---

## 2. Inactive & Sidelined Services Catalog (`docker-compose.yml`)

These services exist in `docker-compose.yml` but are currently commented out.

---

### `dozzle`
* **Image:** `amir20/dozzle:latest`
* **Original Function:** Real-time Docker container log viewer with shell access.
* **Original Ports / Proxy:** Internal `8080/tcp` (previously host `40020:8080`), routed at `https://dozzle.vrg.rocks`.
* **Sidelining Rationale:** `Arcane` now provides integrated container logging, terminal shell execution, and Docker compose management with Authentik OIDC authentication, making a standalone log viewer redundant.
* **Reactivation Notes:**
  - Can be safely uncommented in `docker-compose.yml` and `Caddyfile`.
  - Ensure internal port does not collide if host-exposed.

---

### `beszel` & `beszel-agent`
* **Image:** `henrygd/beszel:latest`, `henrygd/beszel-agent:latest`
* **Original Function:** Lightweight server resource and hardware monitoring hub with host agent daemon.
* **Original Ports / Proxy:** Hub `8090/tcp` (previously host `40010:8090`), Agent `45876/tcp` (host network mode), routed at `https://beszel.vrg.rocks`.
* **Environment Keys:** `BESZEL_AGENT_KEY`, `BESZEL_AGENT_TOKEN` configured in `.env`.
* **Sidelining Rationale:** System health and Docker container states are monitored natively directly on the Glance dashboard (`dash.vrg.rocks`).
* **Reactivation Notes:**
  - Hub data persists in `data/beszel`. Agent fingerprint persists in `data/beszel_agent`.
  - Agent requires `network_mode: host` to read hardware metrics accurately.

---

### `homarr`
* **Image:** `ghcr.io/homarr-labs/homarr:latest`
* **Original Function:** Customizable homelab dashboard.
* **Original Ports / Proxy:** Internal `7575/tcp` (previously host `7575:7575`), routed at `https://homarr.vrg.rocks`.
* **Sidelining Rationale:** Superseded by `Glance` (`glanceapp/glance`), which provides a faster, lighter, code-configured YAML dashboard with Sol branding.
* **Reactivation Notes:** Config and database remain intact in `config/homarr`.

---

### `dockge`
* **Image:** `louislam/dockge:1`
* **Original Function:** Web-based Docker Compose stack manager.
* **Original Ports / Proxy:** Internal `5001/tcp` (previously host `40030:5001`), routed at `https://dockge.vrg.rocks`.
* **Sidelining Rationale:** Succeeded by `Arcane`, which offers superior UI, modern Docker Compose V2 support, and native OIDC integration with Authentik.
* **Reactivation Notes:** Stacks database persists in `data/dockge`.

---

### `uptime-kuma`
* **Image:** `louislam/uptime-kuma:1`
* **Original Function:** Self-hosted uptime and HTTP/TCP service monitor with push notifications.
* **Original Ports / Proxy:** Internal `3001/tcp` (previously host `40040:3001`), routed at `https://kuma.vrg.rocks`.
* **Sidelining Rationale:** Service availability monitoring is aggregated directly into Glance widgets; background pings were minimized to conserve host resources.
* **Reactivation Notes:** SQLite database and monitoring history persist in `data/uptime-kuma/kuma.db`.

---

### `wizarr`
* **Image:** `ghcr.io/wizarrrr/wizarr:latest`
* **Original Function:** Automated invitation and user onboarding portal for Jellyfin.
* **Original Ports / Proxy:** Internal `5690/tcp`, routed at `https://wizarr.vrg.rocks`.
* **Sidelining Rationale:** Sol is primarily operated as a single-family / private ecosystem; user onboarding automation is unnecessary for static accounts.
* **Reactivation Notes:** Config and database persist in `config/wizarr`.

---

### `kavita`, `calibre` & `calibre-web`
* **Images:** `lscr.io/linuxserver/kavita:latest`, `lscr.io/linuxserver/calibre:latest`, `lscr.io/linuxserver/calibre-web:latest`
* **Original Function:** Digital e-book, comic, and PDF management and web reader suite.
* **Original Ports / Proxy:**
  - Kavita: `5000/tcp` (`https://kavita.vrg.rocks`)
  - Calibre: `8080/tcp` (`https://calibre.vrg.rocks`)
  - Calibre-Web: `8083/tcp` (`https://calibre-web.vrg.rocks`)
* **Sidelining Rationale:**
  - `calibre` runs a full desktop GUI inside an X11/VNC container, consuming unnecessary memory on the host Mac (explicit compose comment: `# It's the desktop app in a VM. Keep disabled.`).
  - Book reading workflows are currently handled locally on reader devices or via Apple Books / Kindle.
* **Reactivation Notes:** Media folder `data/media/books` and configurations in `config/kavita`, `config/calibre`, and `config/calibre-web` remain intact.

---

### `qbit_manage`
* **Image:** `ghcr.io/stuffanthings/qbit_manage:latest`
* **Original Function:** CLI and API tool to automatically manage qBittorrent tags, categories, remove unregistered torrents, and enforce seed limits.
* **Original Ports / Proxy:** Internal `8181/tcp`, routed at `https://qbm.vrg.rocks` / `https://qbit_manage.vrg.rocks`.
* **Sidelining Rationale:** Sidelined to avoid automated deletion or modification of active seeding torrents during tracker migration; `Cross-Seed` handles automated injection independently.
* **Reactivation Notes:** Configuration exists at `config/qbit_manage/config.yml`. Requires qBittorrent credentials.

---

### `flood`
* **Image:** `jesec/flood:latest`
* **Original Function:** Modern Node.js web alternative frontend for qBittorrent.
* **Original Ports / Proxy:** Internal `3000/tcp` (previously host `42024:3000`), routed at `https://flood.vrg.rocks`.
* **Sidelining Rationale:** Native qBittorrent Web UI (`https://qb.vrg.rocks`) with Vue/HTML theme is preferred for lower overhead and direct API feature access.
* **Reactivation Notes:** Can be re-enabled by uncommenting in compose and Caddyfile.

---

### `paperless-gotenberg` & `paperless-tika`
* **Images:** `docker.io/gotenberg/gotenberg:8.20`, `docker.io/apache/tika:latest`
* **Original Function:** Document conversion engines for converting Microsoft Office files (`.docx`, `.xlsx`), emails (`.eml`), and exotic file formats into PDF before Paperless OCR.
* **Original Ports:** Gotenberg `3000/tcp`, Tika `9998/tcp`.
* **Sidelining Rationale:** Paperless on Sol primarily processes scanned PDF receipts, statements, and bills via the custom `pre-consumption.py` script. Gotenberg and Tika run heavy Chromium and Java virtual machines that consume significant RAM.
* **Reactivation Notes:**
  - Uncomment both containers in `docker-compose.yml`.
  - Uncomment `PAPERLESS_TIKA_ENABLED: 1`, `PAPERLESS_TIKA_GOTENBERG_ENDPOINT`, and `PAPERLESS_TIKA_ENDPOINT` in `paperless-webserver`.

---

### `paperless-ai`
* **Image:** `clusterzx/paperless-ai`
* **Original Function:** Automated AI document analysis, tagging, correspondent classification, and document summarizing using local/remote LLMs and ChromaDB vector search.
* **Original Ports / Proxy:** Internal `3000/tcp`, routed at `https://paperless-ai.vrg.rocks`.
* **Sidelining Rationale:** Disabled to avoid continuous LLM API usage and memory pressure; Paperless rule-based matching with pre-consumption scripts satisfies document sorting needs.
* **Reactivation Notes:** Database and vector index persist in `data/paperless-ai`.

---

### `vaultwarden` / `bitwarden`
* **Images:** `vaultwarden/server:latest` (or `ghcr.io/bitwarden/self-host:beta`)
* **Original Function:** Self-hosted Bitwarden-compatible password manager.
* **Original Ports / Proxy:** Internal `80/tcp` (or `3333:8080`), routed at `https://vault.vrg.rocks` and `https://pass.vrg.rocks`.
* **Sidelining Rationale:** Password management is handled via primary ecosystem password solutions; self-hosted instance kept on standby.
* **Reactivation Notes:** Configuration in `config/vaultwarden` or `bitwarden.env`.

---

### `n8n`
* **Image:** `docker.n8n.io/n8nio/n8n`
* **Original Function:** Visual node-based workflow automation and webhook platform.
* **Original Ports / Proxy:** Internal `5678/tcp`, routed at `https://n8n.vrg.rocks`.
* **Sidelining Rationale:** Automations on Sol are handled directly via native shell scripts (`backup.sh`, `ntfy_notify.sh`), Python hooks (`pre-consumption.py`), and *arr webhooks.
* **Reactivation Notes:** Stored workflows and SQLite state persist in `config/n8n` and `data/n8n`.

---

### `homeassistant`
* **Image:** `ghcr.io/home-assistant/home-assistant:stable`
* **Original Function:** Open-source smart home and IoT device automation hub.
* **Original Ports / Proxy:** Host `8123/tcp` (`network_mode: host`), routed via Caddy upstream `http://host.docker.internal:8123` at `https://home.vrg.rocks`.
* **Sidelining Rationale:** IoT smart home bridges are currently running independently or paused during hardware re-architecture.
* **Reactivation Notes:** Configurations, automations, and SQLite history persist in `config/homeassistant`.

---

### `leafwiki`
* **Image:** `ghcr.io/perber/leafwiki:latest`
* **Original Function:** Minimalist markdown wiki and digital garden platform.
* **Original Ports / Proxy:** Internal `8080/tcp`, routed at `https://leaf.vrg.rocks` / `https://wiki.vrg.rocks`.
* **Sidelining Rationale:** Superseded by `Quartz` (`quartz/`), which builds blazing-fast static HTML deployed directly via Caddy (`https://mind.vrg.rocks`).
* **Reactivation Notes:** SQLite databases and markdown root trees persist in `data/leafwiki`.

---

### `rclone` (Task) & `rclone-gui`
* **Image:** `rclone/rclone:latest`
* **Original Function:** Rclone web interface (`5572/tcp`) and OAuth token callback server (`53682/tcp`).
* **Sidelining Rationale:** Sidelined as persistent containers because backups are executed on-demand or via cron by launching an ephemeral container using `backup.sh` (`docker-compose run --rm rclone sync ...`).
* **Reactivation Notes:** Configuration remains active in `config/rclone/rclone.conf` and `filter.txt`.

---

## 3. Legacy Archived Services Registry (`docker-compose-archive.yml`)

These services were fully decommissioned and archived into `docker-compose-archive.yml`.

| Decommissioned Service | Base Image | Previous Host Ports | Successor / Replacement | Migration Rationale |
| :--- | :--- | :--- | :--- | :--- |
| **`authelia` & `authelia-redis`** | `authelia/authelia:latest` | `9091` (Internal), `6379` | **`Authentik`** (`ghcr.io/goauthentik/server`) | Authentik provides superior OIDC support, user management UI, LDAP integration, and flexible Caddy outpost integration. |
| **`nginx-proxy-manager`** | `jc21/nginx-proxy-manager:latest` | `80:80`, `443:443`, `81:81` | **`Caddy v2`** (`caddy:latest`) | Caddy eliminated GUI-based proxy fragility, offering declarative text configuration, native HTTP/3, and automatic TLS lifecycle management. |
| **`plex`** | `plexinc/pms-docker:latest` | `32400:32400`, `32469:32469` | **`Jellyfin`** (`lscr.io/linuxserver/jellyfin`) | Jellyfin is 100% open-source, requires no external account authentication, supports free hardware transcoding, and avoids telemetry. |
| **`overseerr`** | `sctx/overseerr:latest` | `5050:5055` | **`Jellyseerr`** (`fallenbagel/jellyseerr`) | Migrated to Jellyseerr for native Jellyfin media server integration and library synchronization. |
| **`readarr`** | `lscr.io/linuxserver/readarr:develop` | `8787:8787` | *Paused / Inactive* | Sidelined along with Calibre during e-book workflow restructuring. |
| **`filebrowser`** | `filebrowser/filebrowser:s6` | `9876:80` | **`Copyparty`** (`copyparty/ac:latest`) | Copyparty offers vastly higher file upload throughput, native WebDAV, audio streaming, and advanced permission flags. |
| **`obsidian-remote`** | `ghcr.io/sytone/obsidian-remote:latest` | `12080`, `12443` | **`Ignis`** + **`Quartz`** | Web-based Obsidian VNC was resource-heavy; replaced by static Quartz publishing and Ignis vault synchronization. |
| **`obsidian` (KasmVNC)** | `lscr.io/linuxserver/obsidian:latest` | `3000:3000`, `3001:3001` | **`Ignis`** + **`Quartz`** | Desktop Obsidian inside Docker was replaced with local native Obsidian syncing with server storage. |
| **`syncthing`** | `lscr.io/linuxserver/syncthing:latest` | `8384`, `22000`, `21027/udp` | **`Copyparty`** / **`Ignis`** | Replaced by direct WebDAV mounts and local vault sync to minimize background sync conflicts. |

---

## 4. Port Conflict Matrix & Reactivation Guide

If any inactive or legacy service is reactivated, the table below highlights potential port collisions and required adjustments:

| Inactive Service | Internal Port | Potential Conflict Target | Conflict Resolution Strategy |
| :--- | :--- | :--- | :--- |
| **`beszel`** | `8090` | None | Direct routing via Caddy `beszel.vrg.rocks -> http://beszel:8090`. |
| **`dozzle`** | `8080` | `glance` (`8080`), `qbittorrent` (`8080`), `calibre` (`8080`) | All services share bridge network; they must be addressed by container hostname (`http://dozzle:8080`), not localhost. |
| **`flood`** | `3000` | `paperless-gotenberg` (`3000`), `paperless-ai` (`3000`) | Addressed safely by container name (`http://flood:3000`). |
| **`uptime-kuma`**| `3001` | None | Direct routing via Caddy `kuma.vrg.rocks -> http://uptime-kuma:3001`. |
| **`kavita`** | `5000` | None | Direct routing via Caddy `kavita.vrg.rocks -> http://kavita:5000`. |
| **`calibre-web`**| `8083` | None | Direct routing via Caddy `calibre-web.vrg.rocks -> http://calibre-web:8083`. |
| **`vaultwarden`** | `80` | `ntfy` (`80`), `caddy` (`80`) | Use container hostname `http://vaultwarden:80` inside Docker network; never map host port `80:80`. |
| **`homeassistant`**| `8123` | Host port `8123` | Uses `network_mode: host`; Caddy routes via `http://host.docker.internal:8123`. |
| **`authelia`** | `9091` | `authentik` (`9000`) | Legacy service; do NOT reactivate alongside Authentik to prevent conflicting Caddy forward-auth handlers. |
