# Sol Server Roadmap & Next Steps

> **Project:** Sol Home Server (`*.vrg.rocks`)  
> **Host:** Apple Silicon M1 Pro macOS (OrbStack / Docker Engine)  
> **Status:** Active Evolution & Polish Phase  

---

## 📋 Action Items

### 1. ⚡ Performance & Resource Optimization
- [x] **macOS / Apple Silicon Efficiency:**
  - Audited CPU/RAM allocations across all 24 active containers (~2.8 GB / 16 GB unified RAM footprint).
  - Implemented M1 Pro (6P+2E) concurrency tuning for Paperless-ngx (`PAPERLESS_WORKER_CONCURRENCY: 2`, `PAPERLESS_OCR_THREADS: 2`, `PAPERLESS_TASK_WORKERS: 2`) and Authentik (`AUTHENTIK_WORKERS: 2`).
- [x] **Storage & Database Engine Optimization:**
  - Documented APFS zero-copy atomic hardlinks (`torrents/` -> `media/`) vs ExFAT external drive copy dynamics.
  - Tuned PostgreSQL 16 & 17 shared buffers (`shared_buffers=256MB`, `work_mem=16MB`, `effective_cache_size=1GB`) across `authentik-postgresql` and `paperless-db`.
  - Standardized SQLite WAL pragmas for Servarr and Arcane.
- [x] **Network & Ingress Fine-Tuning:**
  - Injected dedicated upstream DNS resolvers (`1.1.1.1`, `9.9.9.9`) across `radarr`, `sonarr`, `bazarr`, `prowlarr`, `flaresolverr`, `qbittorrent`, and `cross-seed` to bypass ISP rate limits/censorship.
  - Configured Caddy streaming transport buffers (`read_buffer 32768`, `write_buffer 32768`, `keepalive 120s`) on Jellyfin routes.
  - Enabled Jellyfin transcode throttling (`EnableThrottling: true`, `ThrottleDelaySeconds: 120`, `EncodingThreadCount: 4`) in `encoding.xml` to protect CPU during software transcodes.

---

### 2. 🛡️ Disaster Recovery, Backup & Complete Restore Strategy
- [x] **OneDrive Rclone Sync Enhancement:**
  - Audit `config/rclone/filter.txt` to ensure 100% coverage of persistent SQLite/PostgreSQL databases, custom templates, and credentials while ignoring multi-terabyte media, transcode caches, and logs.
  - Preserved `data/media/preshows/**` explicitly while excluding bulk movies, tv, and torrents.
  - Added automated live PostgreSQL dump hooks (`pg_dump`) for `authentik-postgresql` and `paperless-db` prior to cloud sync.
  - Prioritized all 444+ `.torrent` and `.fastresume` files across qBittorrent, Cross-Seed, and saved torrent directories.
- [x] **One-Click Restore & Cold-Start Playbook:**
  - Designed a disaster recovery playbook for total hardware failure (e.g. restoring to a brand-new Mac).
  - Created `scripts/restore.sh` disaster recovery utility supporting dry-run, cloud pulling, directory instantiation, and stack startup.
  - Documented disaster recovery commands in `docs/system_state/02_STORAGE_AND_VOLUMES.md`.

---

### 3. 📖 Master GitHub-Grade Documentation (`README.md`)
- [x] **Comprehensive Server Showcase:**
  - Detailed the 3-year evolution, philosophy, and architecture of the Sol home server.
  - Documented **all** features across media automation, document archival, developer workspaces, storage logistics, monitoring, and identity management.
- [x] **Operational Command Reference:**
  - Itemized common operations: Stack startup, individual domain lifecycle management (`docker compose -f compose/media.yml restart`), updates, live log viewing, backup triggers, and health diagnostics.
- [x] **Master Configuration & File Index:**
  - Provided a full catalog of all configuration paths, volume mounts, ports, and environment variables.
  - Included interactive architecture ASCII diagrams and Glance dashboard configurations.

---

### 4. 🚀 Git & Jujutsu (JJ) Version Control Integration
- [x] **Repository Sanitization & `.gitignore` Hardening:**
  - Created root [`.gitignore`](file:///Users/vrg/Documents/Sol/.gitignore) strictly excluding `.env`, `/data/`, `/config/`, `/web/`, `/quartz/`, `/logs/`, `_backup_pre_refactor/`, `.DS_Store`, and temporary files.
  - Ensured only declarative infrastructure code (`docker-compose.yml`, `compose/*.yml`, `Caddyfile`, `ports.json`, `.env.example`, `scripts/*.sh`, `coder/*.tf`, `docs/system_state/*.md`, `README.md`) is tracked.
- [ ] **Manual Step: Initialize Jujutsu (`jj`) & Publish to GitHub:**
  
  Run the following commands in terminal when ready to publish:

  ```bash
  # 1. Initialize a colocated Jujutsu / Git repository
  jj git init --colocated

  # 2. Inspect status to verify only declarative files are staged (no data/, config/, or .env)
  jj status

  # 3. Create the initial commit with a descriptive message
  jj describe -m "feat(infra): initialize Sol declarative home server infrastructure"

  # 4. Add your GitHub remote repository
  jj git remote add origin git@github.com:<YOUR_GITHUB_USERNAME>/sol.git

  # 5. Create and track the 'main' bookmark on your working commit
  jj bookmark create main -r @

  # 6. Push to GitHub
  jj git push --bookmark main --remote origin
  ```

  **Everyday Jujutsu Workflow Commands:**
  ```bash
  # Check working copy changes
  jj status

  # View commit graph
  jj log

  # Start a new working copy commit
  jj new

  # Push latest bookmark changes to GitHub
  jj git push
  ```

---

### 5. 🧩 Standby Services Activation & Setup
- [ ] **Gatus Health Status Page (`compose/monitoring.yml`):**
  - Create `config/gatus/config.yaml` with automated ping/HTTP endpoints for all internal services.
  - Enable Caddy reverse proxy route `status.vrg.rocks` -> `http://gatus:8080`.
- [ ] **Recyclarr TRaSH Sync Engine (`compose/media.yml`):**
  - Create `config/recyclarr/recyclarr.yml` configured with Sonarr and Radarr API keys.
  - Run initial dry-run sync for recommended 4K/1080p custom formats and scoring rules.
- [ ] **Unpackerr Archive Extractor (`compose/download.yml`):**
  - Verify archive extraction path bindings for `/data/torrents` and automated Servarr webhook hooks.

---

### 6. 🔮 Optional Architecture: Dynamic Label Ingress via `caddy-docker-proxy`
- [ ] **Overview & Motivation:**
  - Automatically route container subdomains (`*.vrg.rocks`) via Docker Compose labels instead of maintaining a static `Caddyfile` and `ports.json`.
  - Compose files become the single source of truth for routing, internal ports, TLS, and forward-auth policies.
- [ ] **Implementation Architecture & Quirks Handling:**
  - **Image Replacement:** Swap `caddy:latest` in `compose/core.yml` with `lucaslorentz/caddy-docker-proxy:latest` (native multi-arch ARM64).
  - **Docker Socket:** Mount `/var/run/docker.sock:/var/run/docker.sock:ro` into Caddy.
  - **Hybrid Caddyfile Configuration:**
    Keep a minimal base `Caddyfile` for global options, the `(authentik)` forward-auth snippet, and static file web applications (`/mind`, `/fam`, `/scan`, `/aysynbm`).
  - **Container Label Format:**
    ```yaml
    labels:
      caddy: radarr.vrg.rocks
      caddy.reverse_proxy: "{{upstreams 7878}}"
      caddy.import: authentik
    ```
  - **Redundancy Retirement:** Once active, `ports.json` can be officially retired.

---

### 7. 🍿 Optional Feature: Native macOS Jellyfin on Bare Metal (Apple VideoToolbox HW Transcoding)
- [ ] **Overview & Motivation:**
  - Leverage Apple Silicon M1 Pro native VideoToolbox hardware acceleration and Metal framework for near-zero CPU overhead during 4K HEVC/AV1 tone-mapping and transcoding.
  - Runs in parallel alongside containerized Jellyfin for benchmark testing.
- [ ] **Dedicated Ingress Endpoint:**
  - Subdomain: `https://metal.vrg.rocks`
  - Ingress Target: `http://host.docker.internal:8097` (Configured in [Caddyfile](file:///Users/vrg/Documents/Sol/Caddyfile)).
- [ ] **Isolated Data & Config Paths:**
  - Config Root: `/Users/vrg/Documents/Sol/config/jellyfin_metal`
  - Data Root: `/Users/vrg/Documents/Sol/config/jellyfin_metal/data`
  - Cache Root: `/Users/vrg/Documents/Sol/config/jellyfin_metal/cache`
- [ ] **Execution Instructions:**
  - Launch or bootstrap automatically via API in <45s:
    ```bash
    python3 scripts/setup_jellyfin_metal.py
    ```
  - Or run manually:
    ```bash
    nohup /Applications/Jellyfin.app/Contents/MacOS/jellyfin \
      --configdir /Users/vrg/Documents/Sol/config/jellyfin_metal \
      --datadir /Users/vrg/Documents/Sol/config/jellyfin_metal/data \
      --cachedir /Users/vrg/Documents/Sol/config/jellyfin_metal/cache \
      --logdir /Users/vrg/Documents/Sol/config/jellyfin_metal/log \
      --webdir /Applications/Jellyfin.app/Contents/Resources/jellyfin-web \
      --ffmpeg /Applications/Jellyfin.app/Contents/MacOS/ffmpeg > /dev/null 2>&1 &
    ```

---

