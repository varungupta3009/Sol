# 05. System Refactoring & Modular Architecture Migration Plan

> **Host Context:** Apple Silicon M1 Pro macOS (`dash.vrg.rocks`, 16 GB Unified Memory, OrbStack / Docker Engine)  
> **Workspace Root:** `/Users/vrg/Documents/Sol`  
> **Refactoring Timeline:** August 2026 (Phase 1 Modularization) → October 17–19, 2026 (Phase 2 Profiles, Tinyauth v5 + LLDAP Cutover, Backrest + Restic DR, Wave 1 & 2 Fleet Expansion, PANOPTICON Zero-Copy Symlink Pipeline) → October 20, 2026 (Phase 3 31-Agent Swarm Audit & Full-Stack Hardening)  
> **Last Synced to Ground Truth:** 2026-10-20  

---

## 1. Executive Summary & Evolution Milestones

This document records the multi-phase architectural refactoring of the **Sol** home server (`vrg.rocks`), transforming it from a monolithic 922-line Compose file with fragmented secrets and heavyweight Python/Java daemons into a modular, zero-trust, crash-consistent 29-container active stack (`1.63 GiB` total RAM, `29/29` `(healthy)`).

### Phase 1 Milestones (August 2026 — Modularization & Secret Hygiene)
1. **Docker Compose V2 `include:` Architecture:** Split the monolithic `docker-compose.yml` into 8 single-responsibility domain files under `compose/`.
2. **Zero-Friction Container DNS:** Retained 100% container-to-container name resolution (`http://radarr:7878`, `http://tinyauth:3000`, `http://lldap:3890`, `http://glance:8080`, `http://caddy`) across the unified `sol_default` project bridge network.
3. **Dedicated Paperless Stack:** Extracted `paperless-webserver`, `paperless-broker`, `paperless-db`, and standby converters (`paperless-gotenberg`, `paperless-tika`, `paperless-ai`) into `compose/paperless.yml`.
4. **Zero-Leak Environment Mapping:** Replaced blanket `env_file:` imports with explicit container-level `environment:` blocks so no container receives unrelated tokens.
5. **Retired Redundant Root Files:** Archived `paperless.env`, `bitwarden.env`, and legacy compose files into `docs/archive/`.
6. **Static Web & Script Separation:** Organized static frontends into `web/` and operational tooling into `scripts/`.

### Phase 2 Milestones (October 17–19, 2026 — Identity Cutover, Wave 1 & 2 Expansion, Zero-Copy ExFAT & Restic Backups)
1. **Tinyauth v5 + LLDAP Identity Cutover (`~10 MiB` RAM vs `~900 MiB` Authentik):** Replaced the 3-container Authentik stack (`authentik-server`, `authentik-worker`, `authentik-postgresql`) with **Tinyauth v5** (`ghcr.io/tinyauthapp/tinyauth:v5`, `v5.2.0`, forward-auth + 7 built-in RS256 OIDC clients) and **LLDAP** (`ghcr.io/lldap/lldap:stable`, `v0.6.2`, Rust LDAP directory at `600 KiB` RAM), synchronized automatically across all downstream apps via `scripts/identity_sync.py`.
2. **Wave 1 Static Browser Apps (`0 MiB` Container RAM):** Deployed 6 self-hosted static SPAs served directly from `caddy` via `scripts/sync_static_tools.sh`: `tools.vrg.rocks` (IT-Tools), `chef.vrg.rocks` (CyberChef), `pdf.vrg.rocks` (BentoPDF), `speed.vrg.rocks` (OpenSpeedTest), `draw.vrg.rocks` (Excalidraw), and `mi.vrg.rocks` (Mission Impossible dossier), alongside `mind.vrg.rocks` (Quartz), `fam.vrg.rocks` (Family Data Vault), `scan.vrg.rocks` (Homebox Scanner PWA), and `aysynbm.vrg.rocks`.
3. **Wave 2 Lightweight Container Expansion:** Added `qui` (`v1.32.0`, replacing Node.js `cross-seed` and implementing 26 tracker rules + 10 native FUP seeding automation rules), `backrest` (`v1.14.1` Restic UI/scheduler), `readeck` (`v0.22.3` bookmark/article archiver), `enclosed` (`v1.16.0` zero-knowledge encrypted notes), `airtrail` (`v3.13.0` flight log sharing `paperless-db`), `pocketbase` (`v0.40.5` realtime Go + SQLite backend), and promoted repaired `homebox` (`v0.26.2` unified entities schema) to active production.
4. **PostgreSQL 17 Alpine Migration (`paperless-db`):** Migrated `paperless-db` from Debian `postgres:17` (`glibc`) to `postgres:17-alpine` (`musl`) via `pg_dump`/`pg_restore`, hosting both `paperless` and `airtrail` databases in `24.2 MiB` RAM.
5. **PANOPTICON ExFAT Zero-Copy Relative Symlink Pipeline:** Built `scripts/torrent_finished.py` (qBittorrent completion hook) and `scripts/arr_symlink_dedupe.sh` (Radarr/Sonarr custom script) to create relative symlinks (`../../../torrents/...`) on `/Volumes/PANOPTICON` (`ExFAT`), achieving zero-copy media imports without ExFAT hardlink support and eliminating `/downloads` in favor of unified `/data` and `/external`.
6. **Two-Tier Encrypted Restic Backup Architecture (`Backrest`):** Replaced raw `rclone sync` with encrypted Restic repositories on both `/Volumes/PANOPTICON/backups/sol-restic` (`03:00` & `15:00` IST) and `rclone:OneDrive:Sol-Restic` (`03:30` IST), preceded by `scripts/stage_db_backups.sh` (`02:45` & `14:45` IST).

### Phase 3 Milestones (October 20, 2026 — 31-Agent Swarm Audit & Full-Stack Hardening)
1. **100% Container Healthcheck Coverage (`29/29` Healthy):** Added verified native Docker `healthcheck` definitions to all previously unmonitored active services (`caddy`, `arcane`, `glance`, `jellyfin`, `radarr`, `sonarr`, `lidarr`, `prowlarr`, `bazarr`, `qbittorrent`, `ignis`, `code-server`, `coder`, `backrest`, `enclosed`) and replaced `byparr`'s heavy upstream `/health` check (which spawned Firefox against `google.com` every 15m, causing `36.1 GB` Block I/O reads in 13h) with a lightweight `/openapi.json` check + `shm_size: 1gb` + `/tmp` `tmpfs` + `BLOCK_MEDIA: "true"`.
2. **Retired Service & Directory Purge:** Removed decommissioned `authentik-postgresql`, `authentik-server`, `authentik-worker`, `flaresolverr`, and `cross-seed` blocks from `compose/*.yml` and `ports.json`, and deleted 18 retired leftover `config/` and `data/` directories on `dash.vrg.rocks`.
3. **Edge ACL & OIDC Lockdown:** Added `TINYAUTH_APPS_{IGNIS,MIND,SCAN,AYSYNBM}` admin whitelists in `compose/core.yml`, set `CODER_OIDC_ALLOW_SIGNUPS: "false"`, restricted `arcane` and `coder` OIDC consent pre-seeding in `scripts/identity_sync.py` strictly to `admin` users, fixed `(static_site)` directive ordering in `Caddyfile` (`route { try_files ...; file_server }` after `forward_auth`), and gated external `POST`/`PUT` publishes on `ntfy.vrg.rocks` and note creation on `send.vrg.rocks`.
4. **TCC-Free Pre-Backup Staging & Bare-Metal DR Fixes:** Fixed macOS TCC (`Exit 126` on `~/Documents` and removable volume hangs on `/Volumes/PANOPTICON`) in `com.vrg.sol.db-stage.plist` and `scripts/stage_db_backups.sh` (producing 29 clean WAL-free SQLite `.db` snapshots with zero `-wal`/`-shm` sidecars), materialized `web/fam` (`vault.enc`) into a real directory, and fixed `scripts/restore.sh` to run Restic via `docker run` before `.env` exists and restore `coder_db.sql.gz` + `coder_home.tar.gz`.
5. **Immutable `<50ms` Identity Sync Fast-Path:** Rewrote `scripts/identity_sync.py` to read `data/lldap/users.db?immutable=1` directly (eliminating the `WatchPaths` self-triggering JWT login write loop) with a SHA-256 fast-path exit (`45.5 ms`), Readeck OIDC user pre-seeding + `preserve_lldap_user_identity` trigger, and AirTrail single-owner safety.
6. **Coder `sol-workspace` Activation & Jellyfin `tmpfs` Fix:** Set `group_add: ["0"]` and `CODER_CLUSTER_HOST: "127.0.0.1"` on `coder` and pushed `/Sol/coder/main.tf` (`sol-workspace` active); fixed `jellyfin` `/tmp/jellyfin` `tmpfs` permissions (`uid=501,gid=20,mode=0755`), `Optimistic` SQLite locking, and moved `The Ba***ds of Business (1995).mp4` to `Home Videos`.

---

## 2. Current Directory & Stack Topology (`/Users/vrg/Documents/Sol`)

```text
/Users/vrg/Documents/Sol/
├── .env                                  # Unified, app-segregated secrets & parameters (chmod 600)
├── .env.example                          # Sanitized template tracked in Git
├── docker-compose.yml                    # Root Compose orchestrator (name: sol) with native 'include:'
├── Caddyfile                             # 33 active site blocks, 12 commented standby vhosts, hardened snippets
├── ports.json                            # Authoritative registry (46 entries: 29 active containers, 16 standby/ops, 1 native standby)
├── Sol.code-workspace
│
├── compose/                              # 8 MODULAR DOMAIN STACKS (29 Active + 15 Standby + 1 Ops = 45 Services)
│   ├── core.yml                          # Caddy, Tinyauth v5, LLDAP, Arcane (4 active)
│   ├── monitoring.yml                    # Glance, [Gatus, Dozzle, Beszel, Beszel-Agent] (1 active, 4 standby)
│   ├── media.yml                         # Jellyfin, Seerr, Radarr, Sonarr, Bazarr, Lidarr, Prowlarr, Byparr, [Recyclarr, Wizarr] (8 active, 2 standby)
│   ├── download.yml                      # qBittorrent, QUI, [Unpackerr] (2 active, 1 standby)
│   ├── paperless.yml                     # Paperless Webserver, Broker (Redis 8), DB (PG 17 Alpine), [Gotenberg, Tika, AI] (3 active, 3 standby)
│   ├── knowledge.yml                     # Ignis, Readeck, [LeafWiki, Kavita] (2 active, 2 standby)
│   ├── coding.yml                        # code-server, Coder, PocketBase (3 active)
│   └── utilities.yml                     # Copyparty, ntfy, Homebox, Backrest, Enclosed, AirTrail, [Vaultwarden, n8n, Home Assistant], [Rclone (ops)] (6 active, 3 standby, 1 ops)
│
├── web/                                  # 9 STATIC WEB APPS (+ quartz/public -> /mind = 10 Zero-RAM Sites)
│   ├── fam/                              # Family Data Vault static build + encrypted vault.enc (/fam)
│   ├── scan/                             # Homebox Mobile Barcode Scanner PWA (/scan)
│   ├── aysynbm/                          # Async Bookmark Manager (/aysynbm)
│   ├── tools/                            # IT-Tools developer suite (/tools)
│   ├── chef/                             # CyberChef GCHQ data swiss-army knife (/chef)
│   ├── pdf/                              # BentoPDF client-side WebAssembly PDF toolkit (/pdf)
│   ├── speed/                            # OpenSpeedTest LAN/WAN HTML5 speed test (/speed)
│   ├── draw/                             # Excalidraw virtual whiteboard (/draw)
│   └── mi/                               # Mission Impossible briefing experience (/mi)
│
├── scripts/                              # OPERATIONAL AUTOMATION & LAUNCHAGENTS
│   ├── stage_db_backups.sh               # Pre-backup PG dumps (Paperless, AirTrail, Coder), 29 clean SQLite snapshots, symlink manifest
│   ├── backup.sh                         # Manual Restic wrapper (local PANOPTICON + OneDrive cloud)
│   ├── restore.sh                        # Bare-metal & selective Restic restore, SQLite + PG + Coder volume recovery, LaunchAgent bootstrap
│   ├── identity_sync.py                  # LLDAP -> Tinyauth, Jellyfin, Seerr, Paperless, AirTrail, Homebox, Readeck, Copyparty (<50ms fast-path)
│   ├── allowlist_user.sh                 # Operator CLI wrapper for users.json & identity_sync.py
│   ├── torrent_finished.py               # qBittorrent completion hook (zero-copy relative symlinks on ExFAT + Radarr/Sonarr/Jellyfin/ntfy notify)
│   ├── arr_symlink_dedupe.sh             # Radarr/Sonarr OnImport/OnUpgrade custom script (idempotent relative symlink replacement)
│   ├── sync_static_tools.sh              # Idempotent release downloader for Wave 1 static web bundles
│   ├── setup_jellyfin_metal.py           # Standby native macOS Jellyfin Metal launcher (VideoToolbox port 8097)
│   ├── launchd/                          # Tracked macOS LaunchAgents (com.vrg.sol.db-stage.plist, com.vrg.sol.identity-sync.plist)
│   └── archive/                          # Historical one-off migration scripts (migrate_panopticon_live.py, merge_overseerr_history.py, test_cross_seed.sh)
│
├── coder/                                # Coder v2 Terraform template (main.tf -> active 'sol-workspace' template)
├── config/                               # Persistent service configurations (23 active/standby directories)
│   └── backrest/excludes.txt.example     # Tracked Restic backup exclusion template
├── data/                                 # Persistent service data, media, torrents & staged backups
│   └── backups/                          # paperless_db.sql.gz, airtrail_db.sql.gz, coder_db.sql.gz, coder_home.tar.gz, sqlite/ (29 DBs), symlinks_manifest.tsv
└── logs/                                 # Operational logs (db_stage.log, identity_sync.log)
```

---

## 3. Domain Compose Stacks Breakdown (`compose/`)

| Stack File | Active Containers (`29` Total, All `(healthy)`) | Standby / Ops Containers (`16` Total) | Purpose |
| :--- | :--- | :--- | :--- |
| **`core.yml`** | `caddy`, `tinyauth`, `lldap`, `arcane` (`4`) | None (`0`) | Edge TLS/HTTP3 proxy, 10 static sites, Google OAuth forward-auth + OIDC provider, Rust LDAP directory, and Docker manager. |
| **`monitoring.yml`** | `glance` (`1`) | `gatus`, `dozzle`, `beszel`, `beszel-agent` (`4` `standby`) | Unified 3-page dashboard (`dash.vrg.rocks`) and on-demand telemetry/log viewers. |
| **`media.yml`** | `jellyfin`, `seerr`, `radarr`, `sonarr`, `bazarr`, `lidarr`, `prowlarr`, `byparr` (`8`) | `recyclarr`, `wizarr` (`2` `standby`) | Media streaming, request management, PVR automation, subtitles, indexer proxy, and Cloudflare Turnstile solver. |
| **`download.yml`** | `qbittorrent`, `qui` (`2`) | `unpackerr` (`1` `standby`) | BitTorrent engine (`:42069`), Go web UI, cross-seeding, and 10 native FUP seeding automation rules. |
| **`paperless.yml`** | `paperless-webserver`, `paperless-broker`, `paperless-db` (`3`) | `paperless-gotenberg`, `paperless-tika`, `paperless-ai` (`3` `standby`) | Document OCR (`eng+hin+kan+pan`), Redis 8 task queue (`256mb` cap), and shared PostgreSQL 17 Alpine database. |
| **`knowledge.yml`** | `ignis`, `readeck` (`2`) | `leafwiki`, `kavita` (`2` `standby`) | Obsidian vault synchronization (`ignis.vrg.rocks`) and read-later article archiver (`links.vrg.rocks`). |
| **`coding.yml`** | `code-server`, `coder`, `pocketbase` (`3`) | None (`0`) | Browser VS Code IDE, Terraform CDE platform (`sol-workspace`), and Go + SQLite backend (`pb.vrg.rocks`). |
| **`utilities.yml`** | `copyparty`, `ntfy`, `homebox`, `backrest`, `enclosed`, `airtrail` (`6`) | `vaultwarden`, `n8n`, `homeassistant` (`3` `standby`), `rclone` (`1` `ops`) | File server/WebDAV, push notifications, asset inventory, Restic backup scheduler, encrypted notes, and flight log. |
| **Total** | **29 Active (`1.63 GiB` RAM)** | **15 `standby` + 1 `ops` (`16`)** | Plus 1 standby native macOS app (`jellyfin-metal` on port `8097`). |

---

## 4. Profile & Recovery Mechanics

| Command | Effect |
| :--- | :--- |
| `docker compose up -d` | Starts and reconciles all **29** active containers. Profiled `standby` and `ops` services remain stopped (`0 B` RAM). |
| `docker compose --profile standby up -d <service>` | Starts a specific standby container on demand (e.g., `dozzle`, `gatus`, `vaultwarden`). |
| `docker compose --profile ops run --rm rclone <args>` | Runs a one-shot containerized `rclone` operation under the `ops` profile. |
| `python3 scripts/identity_sync.py` | Verifies LLDAP state via SHA-256 digest in `<50ms` (`--force` reconciles all 8 downstream apps). |
| `/bin/bash scripts/stage_db_backups.sh` | Stages `paperless_db.sql.gz`, `airtrail_db.sql.gz`, `coder_db.sql.gz`, `coder_home.tar.gz`, 29 clean SQLite `.db` files, and `symlinks_manifest.tsv`. |
| `./scripts/restore.sh --restore-dbs --start-stack` | End-to-end disaster recovery from PANOPTICON or OneDrive Restic snapshots, restoring SQLite DBs, PostgreSQL dumps, Coder workspace volume, ExFAT symlinks, static web apps, and LaunchAgents. |
