# 05. System Refactoring & Modular Architecture Migration Plan

> **Host Context:** Apple Silicon M1 Pro macOS (Single-Node Host running OrbStack / Docker)  
> **Workspace Root:** `/Users/vrg/Documents/Sol`  
> **Refactoring Date:** August 2026  
> **Safety Guarantee:** Non-destructive migration with dedicated pre-refactor backup at `_backup_pre_refactor/`.

---

## 1. Executive Summary & Goals

This document formalizes the architectural refactoring of the **Sol** home server ecosystem. The objective of this migration was to eliminate technical debt, modularize a monolithic 922-line compose file into clean, single-responsibility domain stacks, centralize secrets, clean up root directory clutter, and establish a robust, maintainable foundation tailored specifically to an Apple Silicon M1 Pro macOS host.

### Key Refactoring Milestones
1. **Docker Compose V2 `include:` Architecture:** Replaced the monolithic `docker-compose.yml` with 8 modular domain files under `compose/`.
2. **Zero-Friction Container DNS:** Retained 100% container-to-container name resolution (`http://radarr:7878`, `http://authentik-server:9000`, `http://glance:8080`, `http://caddy`) across the unified `sol_default` project bridge network without brittle external network hacks.
3. **Dedicated Paperless Stack:** Extracted `paperless-webserver`, `paperless-broker`, `paperless-db`, and AI/OCR helpers into an isolated, dedicated compose file (`compose/paperless.yml`).
4. **Environment & Secrets Hygiene:** Segregated `.env` and `.env.example` into logically prefixed, app-specific sections, extracting inline hardcoded secrets (`arcane` encryption keys) out of YAML.
5. **Zero-Leak Environment Mapping:** Replaced blanket `env_file:` dumps with explicit container-level `environment:` blocks so no service is exposed to unrelated secrets.
6. **Retired Redundant Files:** Safely archived `paperless.env`, `bitwarden.env`, and legacy compose files into `docs/archive/`.
7. **Static Web & Script Separation:** Grouped static frontends into `web/` (`web/fam`, `web/scan`, `web/aysynbm`) and automation tasks into `scripts/` (`scripts/backup.sh`, `scripts/test_cross_seed.sh`).
8. **Master Port Registry Update:** Completely refreshed `ports.json` with active, standby, and legacy service allocations, internal ports, host ports, protocols, and FQDNs.

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

### After (Modular, Clean & Declarative)
```
/Users/vrg/Documents/Sol/
├── .env                                  # Unified, app-segregated secrets & parameters
├── .env.example                          # Sanitized template for version control
├── docker-compose.yml                    # Root Compose orchestrator utilizing native 'include:'
├── Caddyfile                             # Live Reverse Proxy ingress rules & Authentik forward-auth
├── ports.json                            # Authoritative master port & routing registry
├── Sol.code-workspace
│
├── compose/                              # MODULAR DOMAIN STACKS
│   ├── core.yml                          # Ingress & Identity (Caddy, Authentik, Arcane)
│   ├── monitoring.yml                    # Dashboards & Metrics (Glance, [Beszel, Kuma, Homarr])
│   ├── media.yml                         # Media & *arr Suite (Jellyfin, Jellyseerr, Radarr, Sonarr, etc.)
│   ├── download.yml                      # Ingestion (qBittorrent, Cross-Seed, [qbit_manage, flood])
│   ├── paperless.yml                     # Dedicated Document Stack (Web, Broker, DB, [Gotenberg, Tika, AI])
│   ├── knowledge.yml                     # Digital Notes & Reading (Ignis, [LeafWiki, Kavita, Calibre])
│   ├── coding.yml                        # Developer Environments (code-server, Coder)
│   └── utilities.yml                     # Logistics & Storage (Copyparty, Homebox, ntfy, [Vaultwarden, n8n])
│
├── web/                                  # STATIC FRONTENDS & APPS
│   ├── mind/                             # Quartz Digital Garden build (/mind) -> quartz/public
│   ├── fam/                              # Family Data Vault static app (/fam)
│   ├── scan/                             # Homebox Mobile Barcode Scanner PWA (/scan)
│   └── aysynbm/                          # Async Bookmark Manager (/aysynbm)
│
├── scripts/                              # MAINTENANCE & AUTOMATION
│   ├── backup.sh                         # Automated OneDrive Rclone sync script
│   └── test_cross_seed.sh                # Filesystem & cross-seed permission diagnostic script
│
├── config/                               # PERSISTENT CONFIGURATIONS (Paths 100% Intact)
├── data/                                 # PERSISTENT DATA & DATABASES (Paths 100% Intact)
├── logs/                                 # AUDIT & BACKUP LOG ARCHIVES
│
├── docs/
│   ├── system_state/                     # Complete 00-05 Architectural Documentation
│   └── archive/                          # Archived historic compose files, paperless.env & logs
│
└── _backup_pre_refactor/                 # Pre-refactoring safety rollback snapshot
```

---

## 3. Detailed Component Breakdown

### 3.1 Domain Compose Stacks (`compose/`)

| Stack File | Active Services | Standby / Preserved Services | Purpose |
| :--- | :--- | :--- | :--- |
| **`core.yml`** | `caddy`, `authentik-postgresql`, `authentik-server`, `authentik-worker`, `arcane` | None | Core edge routing, authentication, and Docker management. |
| **`monitoring.yml`** | `glance` | `dozzle`, `beszel`, `beszel-agent`, `dockge`, `uptime-kuma`, `homarr` | System health overview, metrics, and homelab dashboards. |
| **`media.yml`** | `jellyfin`, `jellyseerr`, `radarr`, `sonarr`, `bazarr`, `lidarr`, `prowlarr`, `flaresolverr` | `wizarr` | Video/music streaming, automated metadata ingestion, and requests. |
| **`download.yml`** | `qbittorrent`, `cross-seed` | `qbit_manage`, `flood` | High-throughput BitTorrent client and cross-seed daemon. |
| **`paperless.yml`** | `paperless-webserver`, `paperless-broker`, `paperless-db` | `paperless-gotenberg`, `paperless-tika`, `paperless-ai` | Complete document OCR, indexing, and archival engine. |
| **`knowledge.yml`** | `ignis` | `leafwiki`, `kavita`, `calibre`, `calibre-web` | Obsidian note synchronization, digital gardens, and e-books. |
| **`coding.yml`** | `code-server`, `coder` | None | Web IDEs and on-demand Terraform container workspaces. |
| **`utilities.yml`** | `copyparty`, `homebox`, `ntfy` | `vaultwarden`, `n8n`, `homeassistant`, `rclone`, `rclone-gui` | Multi-user file sharing, inventory tracking, and push notifications. |

---

## 4. Technical Answers & Investigation Findings

### Paperless-AI Environment Variable Resolution
* **Question:** Can Paperless-AI environment variables lie outside its directory (`data/paperless-ai/.env`)?
* **Findings:** **Yes, absolutely.**
  1. `clusterzx/paperless-ai` reads standard container environment variables (`process.env`).
  2. Defining variables centrally in `.env` (or via `compose/paperless.yml`) passes them directly into the container process on startup.
  3. While Paperless-AI generates `/app/data/.env` as a local cache if variables are omitted, passing environment variables through compose overrides and centralizes the configuration cleanly.

### Environment Variable Security & Isolation
* By eliminating blanket `env_file:` imports across `authentik` and `paperless`, each service receives only the exact parameters mapped under its `environment:` block in compose.
* Unrelated system tokens (e.g. `BESZEL_AGENT_TOKEN`, `ARCANE_JWT_SECRET`) are never leaked into other containers' execution environments.

### Cross-Stack Container Networking
* Because all compose stacks are included into the root `docker-compose.yml`, Docker assigns every service to the common network `sol_default`.
* Internal DNS hostnames (`authentik-server:9000`, `radarr:7878`, `sonarr:8989`, `glance:8080`, `ntfy:80`) resolve with zero latency across stack boundaries.

---

## 5. Rollback & Disaster Recovery Procedures

In the unlikely event that a rollback is required, a full pristine snapshot of the pre-refactor configuration is saved in `_backup_pre_refactor/`.

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
*(Note: Because no files in `./data` or `./config` were modified or moved, application databases and state remain 100% intact).*
