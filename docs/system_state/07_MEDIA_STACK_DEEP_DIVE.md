# 07. Media & Ingestion Stack: Deep Architectural Audit & State Documentation

> **Scope:** End-to-end architecture, live API/SQLite state, ExFAT zero-copy relative symlink pipeline, and QUI FUP automation across the Sol media ecosystem (`jellyfin`, `jellyfin-metal`, `seerr`, `radarr`, `sonarr`, `lidarr`, `bazarr`, `prowlarr`, `byparr`, `qbittorrent`, and `qui`).  
> **Host:** Apple Silicon M1 Pro macOS (`dash.vrg.rocks`, OrbStack / Docker Engine)  
> **Last Synced to Ground Truth:** 2026-10-20 (Post-Phase-2 31-Agent Swarm Audit & Remediation)  

---

## 1. End-to-End Media Pipeline Dataflow

```text
                             [ Household User Request ]
                                         |
                                         v
                      +-------------------------------------+
                      |           Seerr (v3.2.0)            | (https://request.vrg.rocks)
                      |  43 Merged Requests | Jellyfin LDAP |
                      +------------------+------------------+
                                         |
                    +--------------------+--------------------+
                    | (Movies -> /external/media/movies)      | (TV -> /external/media/tv)
                    v                                         v
     +------------------------------+         +------------------------------+
     |  Radarr (v6.4.4.10685-ls321) |         |   Sonarr (v4.0.17.2952-ls)   |
     |  CDH: False | Recycle: 14d   |         |   CDH: False | Recycle: 14d  |
     +--------------+---------------+         +---------------+--------------+
                    |                                         |
                    +--------------------+--------------------+
                                         | (Search & RSS Sync)
                                         v
                      +-------------------------------------+      +----------------------------------+
                      |      Prowlarr (v2.3.6.5351-ls)      |----->|         Byparr (v3.0.4)          |
                      |  8 Enabled Indexers | 90s Timeout   |      |  http://flaresolverr:8191 alias  |
                      +------------------+------------------+      |  Invisible-Playwright + /tmp RAM |
                                         |                         +----------------------------------+
                                         v
                      +-------------------------------------+      +----------------------------------+
                      |     qBittorrent (v5.1.4-ls408)      |<---->|          QUI (v1.32.0)           |
                      |  Port 42069 WAN | 150 Torrents      |      |  25 Trackers | 10 FUP Rules      |
                      +------------------+------------------+      |  30m Cross-Seed RSS Automation   |
                                         |                         +----------------------------------+
                                         | (OnTorrentFinished Hook)
                                         v
                      +-------------------------------------+
                      |    scripts/torrent_finished.py      |
                      |  + scripts/arr_symlink_dedupe.sh    |
                      |  Zero-Copy Relative Symlinks:       |
                      |  /external/media/{movies,tv}/...    |
                      |    -> ../../../torrents/{movies,tv} |
                      |  (Plus APFS Hardlinks on /data)     |
                      +------------------+------------------+
                                         |
        +--------------------------------+--------------------------------+
        | (Rescan & Import)              | (Subtitle Sync)                | (Library Refresh)
        v                                v                                v
+---------------+              +-------------------+            +-------------------+
| Radarr/Sonarr |              |  Bazarr (v1.6.2)  |            | Jellyfin (v12.2)  |
| RefreshMovie  |              |  Profile 1: EN    |            | watch.vrg.rocks   |
| RefreshSeries |              |  42 Movies / 5 TV |            | 2 GiB /tmp tmpfs  |
+-------+-------+              +---------+---------+            +---------+---------+
        |                                |                                |
        +--------------------------------+--------------------------------+
                                         | (Completion & Import Alerts)
                                         v
                      +-------------------------------------+
                      |           ntfy (v2.31.1)            | (http://ntfy:80 -> https://ntfy.vrg.rocks)
                      +-------------------------------------+
```

---

## 2. ExFAT Zero-Copy Relative Symlink Pipeline (`/Volumes/PANOPTICON`)

Because `/Volumes/PANOPTICON` (`4 TB` external HDD, `737 GiB` free) is formatted as **ExFAT**, it does not support POSIX hardlinks (`ln`), while standard Servarr `Completed Download Handling` (CDH) would perform slow, full-file 2x copies across USB during seeding. Sol solves this with a zero-copy relative symlink pipeline:

1. **CDH Disabled & Unified Mounts:**
   - Both `radarr` and `sonarr` have `enablecompleteddownloadhandling = False` in their SQLite `Config` tables and mount `/Users/vrg/Documents/Sol/data:/data` and `/Volumes/PANOPTICON:/external`.
   - `recyclebin` is configured to `/external/media/.recycle` (`recyclebincleanupdays = 14`).
2. **`scripts/torrent_finished.py` (qBittorrent Completion Hook):**
   - Triggered automatically by qBittorrent on torrent completion (`%N`, `%L`, `%F`, `%R`, `%D`, `%C`, `%Z`, `%I`).
   - Queries Radarr (`:7878`) or Sonarr (`:8989`) history by infohash (`downloadId`) to resolve the target media folder (`/external/media/movies/<Title>` or `/external/media/tv/<Series>/Season XX`).
   - Creates **relative symlinks** (`os.path.relpath(real_src, target_dir)`, e.g., `../../../torrents/movies/...`) for all video and subtitle files, triggers `RefreshMovie` / `RefreshSeries` in Radarr/Sonarr, triggers `POST /Library/Refresh` in Jellyfin, and publishes a completion push notification to `http://ntfy:80/qBittorrent`.
3. **`scripts/arr_symlink_dedupe.sh` (Radarr/Sonarr `OnImport` / `OnUpgrade` Custom Script):**
   - Guarded by `case "$DEST" in /external/media/*)` and idempotency check `[ -L "$DEST" ] && [ "$REAL_SRC" = "$REAL_DEST" ]`.
   - If Radarr or Sonarr ever imports a physical copy on `/external/media/*`, replaces it atomically with a relative symlink (`realpath -m --relative-to="$DIR" "$REAL_SRC"`).
4. **Symlink Manifest Backup (`data/backups/symlinks_manifest.tsv`):**
   - `scripts/stage_db_backups.sh` captures all relative symlinks under `data/media`, `data/torrents`, `/Volumes/PANOPTICON/media`, and `/Volumes/PANOPTICON/torrents` (`1,417` symlinks total) via an OrbStack `redis:8-alpine` scan (bypassing macOS TCC prompts on removable volumes), and `scripts/restore.sh` reconstructs every symlink on recovery.

---

## 3. Component-by-Component Configuration & Verified State (2026-10-20)

### 🍿 1. Jellyfin (`http://jellyfin:8096` / `https://watch.vrg.rocks`, `https://jellyfin.vrg.rocks`)
* **Image & Version:** `lscr.io/linuxserver/jellyfin:latest` (`12.2.0` / `12.2ubu2604-ls54`), `healthy` (`336.8 MiB` RAM).
* **Mounts & RAM Scratch (`compose/media.yml`):**
  - `/config` -> `/Users/vrg/Documents/Sol/config/jellyfin`
  - `/media/internal` -> `/Users/vrg/Documents/Sol/data/media`
  - `/media/external` -> `/Volumes/PANOPTICON`
  - `tmpfs`: `/tmp/jellyfin:size=2g,uid=501,gid=20,mode=0755` (keeps Trickplay & dynamic image extraction in RAM off the APFS SSD with write permissions for `uid=501(abc)`).
* **Database & Server Settings:**
  - `config/jellyfin/database.xml`: `<LockingBehavior>Optimistic</LockingBehavior>` (eliminates `SQLite Error 5: unable to delete/modify collation sequence due to active statements` on concurrent `GET /Items` requests). Orphaned `library.db*` files removed.
  - `config/jellyfin/system.xml`: `<ServerName>Sol</ServerName>`.
* **Libraries (`59` Movies, `5` Series / `758` Episodes, `0` Broken Symlinks):**
  - `Movies` (`CollectionType: movies`): `/media/internal/movies` + `/media/external/media/movies` (`59` movies; duplicate `TRON: Legacy (2010).mkv` symlink removed; `The Ba***ds of Business (1995).mp4` moved to `Home Videos`).
  - `Shows` (`CollectionType: tvshows`): `/media/internal/tv` + `/media/external/media/tv` (`5` series: *Impractical Jokers* `232` eps, *Kochikame* `142` eps, *Mind Your Language* `42` eps, *Oswald* `26` files / `52` eps, *Shin Chan* `316` eps).
  - `Home Videos` (`CollectionType: homevideos`): `/media/internal/home-videos` (*VRG's 1st Birthday* + *The Ba\*\*\*ds of Business (1995)*; excluded from Seerr sync).
* **SSO-Auth (`v4.0.0.4`) + LDAP-Auth (`v24.0.0.0`) Integration:**
  - `LDAP-Auth` connects to `lldap:3890` (`dc=vrg,dc=rocks`) and owns all 4 household user accounts (`VRG` and 3 household member accounts).
  - `SSO-Auth` connects to Tinyauth OIDC (`https://auth.vrg.rocks`, `SchemeOverride: https`, `DefaultProvider: LDAP-Auth`, `DefaultUsernameClaim: email`) with `<CanonicalLinks>` pre-seeded by `scripts/identity_sync.py` and a 300ms JS auto-redirect in `branding.xml`.
* **Standby Jellyfin Metal (`scripts/setup_jellyfin_metal.py`, Port `8097`):**
  - Marked `"status": "standby"` in `ports.json` and commented out in `Caddyfile` (`metal.vrg.rocks`); `DB_FILE` path (`data/data/jellyfin.db`) fixed in `scripts/setup_jellyfin_metal.py` for on-demand Apple Silicon `videotoolbox` hardware transcoding.

---

### 🎯 2. Seerr (`http://seerr:5055` / `https://request.vrg.rocks`, `https://seerr.vrg.rocks`)
* **Image & Version:** `ghcr.io/seerr-team/seerr:latest` (`v3.2.0`), `healthy` (`67.2 MiB` RAM), network alias `jellyseerr`.
* **Authentication & Users:** Authenticates against Jellyfin (`http://jellyfin:8096`) using LLDAP credentials; all 4 household users provisioned with `43` total requests (including 27 historical Overseerr requests migrated in October 2026).
* **Service Integrations (`config/seerr/settings.json`):**
  - **Radarr:** `http://radarr:7878`, Profile: `VRG HQ (UHD/FHD)`, Root Folder: `/external/media/movies` (updated from legacy `/data/media/movies` in Phase 2).
  - **Sonarr:** `http://sonarr:8989`, Profile: `Ultra-HD`, Root Folder: `/external/media/tv`.
  - **Jellyfin Sync:** Syncs `Movies` and `Shows` cleanly with zero `Unable to find TMDb ID` errors after moving `The Ba***ds of Business (1995).mp4` out of `/media/internal/movies` into `/media/internal/home-videos`.

---

### 🎬 3. Radarr (`http://radarr:7878` / `https://radarr.vrg.rocks`)
* **Image & Version:** `lscr.io/linuxserver/radarr:latest` (`6.4.4.10685-ls321`), `healthy` (`143.3 MiB` RAM, `/ping` healthcheck active).
* **Library & Symlink Integrity:**
  - `0` broken symlinks across `/external/media/movies` (`38` relative symlinks -> `../../../torrents/movies/...`) and `/data/media/movies` (*The Fifth Element (1997)* hardlinked `Links: 2` on APFS).
  - *The Sixth Sense (1999)* (Movie ID `16`, `21.5 GiB`) re-linked to `/external/media/movies/The Sixth Sense (1999)` (`hasFile: true`, `movieFileId: 472`).
  - `LogLevel` set to `info` in `config.xml` (legacy debug logs purged).

---

### 📺 4. Sonarr (`http://sonarr:8989` / `https://sonarr.vrg.rocks`)
* **Image & Version:** `lscr.io/linuxserver/sonarr:latest` (`4.0.17.2952-ls306`), `healthy` (`116.6 MiB` RAM, `/ping` healthcheck active).
* **Library & Symlink Integrity:**
  - **100% Recovered & Indexed:** All 4 series on `/external/media/tv` (*Impractical Jokers* `232/232` files, *Kochikame* `142` files, *Oswald* `26/26` files covering `52/52` episodes, *Shin Chan* `316` files) plus *Mind Your Language* (`42/42` files on `/data/media/tv`) are real directories containing **1,379 valid relative symlinks** (`0` broken symlinks, `0` directory symlinks).
  - `RenameEpisodes = 0`, `enablecompleteddownloadhandling = False`, `recyclebin = /external/media/.recycle`, `LogLevel = info`.

---

### 🎵 5. Lidarr (`http://lidarr:8686` / `https://lidarr.vrg.rocks`)
* **Image & Version:** `lscr.io/linuxserver/lidarr:latest` (`3.1.0.4875-ls285`), `healthy` (`109.7 MiB` RAM, `/ping` healthcheck active).
* **Configuration:** `External` auth behind Tinyauth admin `forward_auth`, connected to `qBittorrent` and `Prowlarr`, `LogLevel = info`.

---

### 💬 6. Bazarr (`http://bazarr:6767` / `https://bazarr.vrg.rocks`)
* **Image & Version:** `lscr.io/linuxserver/bazarr:latest` (`v1.6.2-ls368`), `healthy` (`71.7 MiB` RAM, `/ping` healthcheck active).
* **Configuration (`config.yaml` & `bazarr.db`):**
  - Default language profiles enabled (`serie_default_enabled: true`, `serie_default_profile: 1`, `movie_default_enabled: true`, `movie_default_profile: 1`, `default_und_audio_lang: en`).
  - `profileId = 1` (`English`) assigned across all `5/5` series and `42/42` movies (`use_embedded_subs: true` recognizes embedded English tracks across `373` movie tracks and `407` episode tracks).
  - Active providers pruned to `opensubtitlescom` (VIP), `embeddedsubtitles`, `yifysubtitles`, and `tvsubtitles` (broken `subdl` and Hebrew-only `wizdom` removed).

---

### 🔍 7. Prowlarr (`http://prowlarr:9696` / `https://prowlarr.vrg.rocks`) & 🛡️ 8. Byparr (`http://byparr:8191`)
* **Prowlarr (`v2.3.6.5351-ls143`, `138.9 MiB` RAM, `healthy`):**
  - Syncs indexers (`IPTorrents`, `1337x`, `Milkie`, `The Pirate Bay`, `TheRARBG`, `upload.cx`, `YTS`, `RuTracker.org`) to Radarr, Sonarr, and Lidarr (`LogLevel = info`).
  - Zero-grab `LimeTorrents` (ID `4`) disabled to eliminate recurring 6-hourly `400 BadRequest` sync errors on Movie/Audio category queries.
  - `FlareSolverr` proxy (`http://flaresolverr:8191/`, ID `1`) `requestTimeout` raised from `60s` to `90s`, and tag `1` (`flare`) applied to both `1337x` and `RuTracker.org`.
* **Byparr (`v3.0.4`, `35.4 MiB` idle RAM, `healthy`):**
  - Uses `invisible-playwright` (patched Firefox `151.0`) with `shm_size: 1gb`, `tmpfs: /tmp:size=512m,exec,mode=1777`, `BLOCK_MEDIA: "true"`, and a lightweight `/openapi.json` healthcheck.
  - `flaresolverr.vrg.rocks` redirects `301` to `https://byparr.vrg.rocks{uri}` (enforcing `TINYAUTH_APPS_BYPARR_*` admin-only ACL).

---

### ⚡ 9. qBittorrent (`http://qbittorrent:8080` / `https://qb.vrg.rocks`) & 🔁 10. QUI (`http://qui:7476` / `https://qui.vrg.rocks`)
* **qBittorrent (`v5.1.4-ls408`, `31.4 MiB` RAM, `healthy`):**
  - Mounts `/config`, `/data`, and `/external` (`/downloads` retired); WAN port `42069` TCP/UDP exposed.
  - Category save paths: `radarr` -> `/external/torrents/movies`, `sonarr` -> `/external/torrents/tv`, `lidarr` -> `/data/torrents/music`, `cross-seed-link` -> `/data/torrents/cross-seed-links`.
  - All 7 recoverable cross-seed torrents in `/data/torrents/cross-seed-links/` re-pointed to live container paths and verified.
* **QUI (`v1.32.0`, `34.3 MiB` RAM, `healthy`):**
  - Replaced standalone Node.js `cross-seed` and `qbit_manage`.
  - **25 Tracker Customizations & 10 Active Automation Rules (`38` condition blocks):** Automatically tags all `150 / 150` torrents (`MAM: 84`, `IPT: 32`, `PUB: 18`, `3DT: 12`, `ULCX: 2`, `RUT: 1`, `MLK: 1`), enforces tiered FUP upload speed caps and ratio limits (`Permaseed [INF]` at `10 MiB/s`, `Public <= 25 GB` stop at `1.0`, `Public > 25 GB` stop on completion, `Private Tier 1 <= 50 GB` at `5 MiB/s`, `Tier 2 50-100 GB` at `2 MiB/s`, `Private > 100 GB` cap/pause), and runs 30-minute RSS cross-seed scans (`useHardlinks: true`, `hardlinkBaseDir: "/data/torrents/qui-links"`).
