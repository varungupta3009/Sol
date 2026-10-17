# 07. Media & Ingestion Stack: Deep Architectural Audit & State Documentation

> **Scope:** Live API and configuration audit of the Sol media ecosystem (Radarr, Sonarr, Prowlarr, Byparr, Bazarr, Jellyfin, Jellyfin Metal, Seerr, qBittorrent, and Cross-Seed).  
> **Host:** Apple Silicon M1 Pro macOS (OrbStack / Docker Engine)  
> **Audit Date:** August 2026 (Live API Rescan). Application versions, health states, and free-space figures below are from that rescan.  
> **Infrastructure Sync:** 2026-10-17 (compose, Caddyfile, scripts, and rclone filter state)  
> **Mode:** Read-Only State Inspection & Optimization Roadmap  

---

## 1. End-to-End Media Pipeline Dataflow

```
                             [ User Request ]
                                    |
                                    v
                     +-----------------------------+
                     |            Seerr            | (https://request.vrg.rocks) [Authentik]
                     |   (Discovery & Approvals)   |
                     +--------------+--------------+
                                    |
                    +---------------+---------------+
                    |                               |
                    v (Movies)                      v (TV Series)
     +-----------------------------+ +-----------------------------+
     |           Radarr            | |           Sonarr            |
     |    (Movie PVR Automation)   | |     (TV PVR Automation)     |
     +--------------+--------------+ +--------------+--------------+
                    |                               |
                    +---------------+---------------+
                                    | (Search Queries & Sync)
                                    v
                     +-----------------------------+      +---------------------------+
                     |          Prowlarr           |----->|          Byparr           |
                     | (Centralized Indexer Proxy) |      | (http://flaresolverr:8191 |
                     +--------------+--------------+      |  alias, Turnstile solver) |
                                    | (Pushes Torrents)   +---------------------------+
                                    v
                     +-----------------------------+
                     |         qBittorrent         | (Port: 42069 / WAN, qb.vrg.rocks Native Auth)
                     |     (BitTorrent Client)     |
                     +--------------+--------------+
                                    | (Downloads to /downloads == /data/torrents)
                                    v
                     +-----------------------------+
                     |       APFS Hardlinks        | (Instant Zero-Copy Move)
                     |  -> /data/media/movies      |
                     |  -> /external/Movies        | (PANOPTICON - 759 GB Free, Aug 2026)
                     |  -> /data/media/tv          |
                     |  -> /external/TV Shows      | (PANOPTICON - 759 GB Free, Aug 2026)
                     +--------------+--------------+
                                    |
                    +---------------+---------------+---------------------------+
                    |                               |                           |
                    v (Subtitle Sync)               v (Container Streaming)     v (Native Streaming)
     +-----------------------------+ +-----------------------------+ +-----------------------------+
     |           Bazarr            | |          Jellyfin           | |       Jellyfin Metal        |
     |   (Subtitles Automation)    | |  (watch.vrg.rocks, :8096)   | | (metal.vrg.rocks, :8097,    |
     +-----------------------------+ +-----------------------------+ |  Apple VideoToolbox)        |
                    |                               |                +-----------------------------+
                    +---------------+---------------+
                                    | (Webhooks & Notifications)
                                    v
                     +-----------------------------+
                     |          ntfy.sh            | (https://ntfy.vrg.rocks)
                     |   (Instant Push Alerts)     |
                     +-----------------------------+
```

---

## 2. Component-by-Component Configuration Matrix

### 🎬 1. Radarr (`http://radarr:7878` / `https://radarr.vrg.rocks`)
* **Core Version:** `6.3.0.10514` | **Database:** SQLite 3.51.2
* **System Health:** **`0` Errors, `0` Warnings (100% Healthy)**.
* **Container DNS:** `1.1.1.1`, `9.9.9.9`.
* **Storage Root Folders:**
  - `/data/media/movies` *(Internal SSD: Accessible, 21.0 GB Free)*.
  - `/external/Movies` *(External PANOPTICON: Accessible, 759.4 GB Free)*.
* **Quality Profiles:**
  - `VRG HQ (UHD/FHD)` *(Default)*: Includes Remux-2160p, Bluray-2160p, WEBDL-2160p, Remux-1080p, Bluray-1080p, WEBDL-1080p.
  - **Upgrade Allowed:** `False` *(Will not auto-upgrade releases once downloaded)*.
* **Custom Formats (TRaSH Guides):** **`0` Active Formats** *(No scoring rules for HDR10+, Dolby Vision, AV1, lossless audio, or low-quality release filters)*.
* **Media Management & Naming:**
  - `Rename Movies`: **`False`** *(Keeps raw torrent scene names, for example `Movie.Title.2024.2160p.HDR.x265-GROUP.mkv`)*.
  - `Use Hardlinks instead of Copy`: `True` *(Zero-copy APFS linking active)*.
* **Download Client Mapping:**
  - `qBittorrent`: `http://qbittorrent:8080`, category: `radarr`.
  - Remote Path Mapping: `/downloads/movies` -> `/data/torrents/movies/`.
  - Because `qbittorrent` now also mounts `/data`, this mapping becomes unnecessary once qBittorrent save paths move to `/data/torrents/...`.

---

### 📺 2. Sonarr (`http://sonarr:8989` / `https://sonarr.vrg.rocks`)
* **Core Version:** `4.0.19.2979` | **Database:** SQLite 3.53.2
* **Container DNS:** `1.1.1.1`, `9.9.9.9`.
* **Storage Root Folders:**
  - `/data/media/tv` *(Internal SSD: Accessible, 21.0 GB Free)*.
  - `/external/TV Shows` *(External PANOPTICON: Accessible, 759.4 GB Free)*.
* **Quality Profiles:**
  - `Ultra-HD` *(Default)*: WEB-2160p, Bluray-2160p, Remux-2160p (Cutoff: `Bluray-2160p`, Upgrades Allowed: `True`).
  - `HD-1080p`: Bluray-1080p, WEB-1080p, HDTV-1080p.
* **Custom Formats / Release Profiles:** **`0` Active Custom Formats**.
* **Media Management & Naming:**
  - `Rename Episodes`: **`True`** *(Active)*.
  - `Standard Episode Format`: `{Series Title} - S{season:00}E{episode:00} - {Episode Title} [{Quality Full}] [{MediaInfo VideoDynamicRangeType}] [{MediaInfo VideoBitDepth}bit] [{MediaInfo VideoCodec}] [{MediaInfo AudioFormat} {MediaInfo AudioChannels}] [{Release Group}]` *(TRaSH-aligned format)*.
  - `Season Folder Format`: `Season {season:00}`.
  - `Use Hardlinks instead of Copy`: `True` *(Active)*.
* **Health Notice:**
  - `DownloadClientCheck`: Recheck connection password/settings for qBittorrent in Sonarr.

---

### 🔍 3. Prowlarr (`http://prowlarr:9696` / `https://prowlarr.vrg.rocks`)
* **Core Version:** `1.31.2.4975`
* **Container DNS:** `1.1.1.1`, `9.9.9.9`.
* **Active Indexers:**
  - `IPTorrents` (Private Tracker / VIP Passkey)
  - `1337x`, `Milkie`, `The Pirate Bay`, `TheRARBG`, `upload.cx`, `YTS` (Public Trackers)
  - `RuTracker.org` *(Warning: Connection timeout / Cloudflare challenge)*
  - `DesiTorrents` *(Disabled)*
* **Application Synchronization:** Full Sync active to Radarr, Sonarr, and Lidarr.
* **Proxy Configuration:** Challenge-solver proxy at `http://flaresolverr:8191` with `flaresolverr` tag routing. Since October 2026 that hostname resolves to `byparr` through its network alias. No Prowlarr setting changed.

---

### 🛡️ 4. Byparr (`http://byparr:8191`, alias `http://flaresolverr:8191` / `https://byparr.vrg.rocks`)
* **Image:** `ghcr.io/thephaseless/byparr:latest`
* **Role:** Active Cloudflare Turnstile solver for Prowlarr. Drop-in replacement for FlareSolverr.
* **Environment:** `TZ: ${TZ}`, `LOG_LEVEL: info`. DNS `1.1.1.1`, `9.9.9.9`.
* **Edge Access:** `byparr.vrg.rocks` and `flaresolverr.vrg.rocks` with `import authentik`.
* **Fallback:** `flaresolverr` (`ghcr.io/flaresolverr/flaresolverr:latest`) under `profiles: ["standby"]`. Stop `byparr` before you start it, because both answer the `flaresolverr` name.

---

### 💬 5. Bazarr (`http://bazarr:6767` / `https://bazarr.vrg.rocks`)
* **Core Version:** `1.6.0` | **Python:** `3.12.13`
* **Container DNS:** `1.1.1.1`, `9.9.9.9`.
* **Active Providers:** `opensubtitlescom`, `embeddedsubtitles`, `yifysubtitles`, `tvsubtitles`, `wizdom`, `subdl`.
* **OpenSubtitles.com:** VIP Account configured (`varungupta3009`).
* **Scoring Rules:** Series Threshold: `90`, Movie Threshold: `70`.
* **Embedded Subtitles:** `ffprobe` extraction enabled, OCR uppercase fixes active.
* **Jellyfin Notification:** Automated library refresh on subtitle download.

---

### 🍿 6. Jellyfin (`http://jellyfin:8096` / `https://watch.vrg.rocks`)
* **Core Version:** `10.11.11`
* **Active Libraries:**
  - `Movies` (`/config/data/root/default/Movies`)
  - `Shows` (`/config/data/root/default/Shows`)
  - `Collections` & `Playlists`
* **Hardware Acceleration:** **`none` (Software CPU decoding/encoding)**. The Linux VM under OrbStack has no VideoToolbox access.
* **Transcoding Throttling:** **`false` (Unthrottled CPU load during transcode)**, as of the August 2026 rescan.
* **Edge Transport:** No compression. `read_buffer 32768`, `write_buffer 32768`, `keepalive 120s`.
* **Installed Plugins:**
  - `Intro Skipper` *(Automatic episode intro detection & skip button)*.
  - `TMDb`, `OMDb`, `TheTVDB`, `OpenSubtitles`, `AudioDB`, `MusicBrainz`, `Studio Images`, `Chapter Creator`, `Jellyfin Enhanced`, `SSO-Auth`.

---

### 🍏 7. Jellyfin Metal (`http://127.0.0.1:8097` / `https://metal.vrg.rocks`)
* **Runtime:** Native macOS `/Applications/Jellyfin.app` (not a container), proxied by Caddy through `http://host.docker.internal:8097`.
* **Config Root:** `config/jellyfin_metal` (`data/jellyfin.db`, `cache/`, `log/`).
* **Hardware Acceleration (set by `--reset` bootstrap):** `videotoolbox`, `EnableTonemapping`, `EnableVideoToolboxTonemapping`, `EnableThrottling: true`, `ThrottleDelaySeconds: 120`, decode `h264`, `hevc`, `vc1`, `vp9`, `av1`, 10-bit HEVC and VP9, HEVC and AV1 encoding allowed.
* **Libraries (set by `--reset` bootstrap):** `Movies` (`data/media/movies`, plus `/Volumes/PANOPTICON/Movies` if present), `Shows` (`data/media/tv`, plus `/Volumes/PANOPTICON/TV Shows` if present).
* **API Keys (set by `--reset` bootstrap):** `Jellyseerr`, `Bazarr`.
* **Lifecycle:** `python3 scripts/setup_jellyfin_metal.py` relaunches and preserves `jellyfin.db`. `--reset` wipes `config/jellyfin_metal` and re-runs the wizard.

---

### 🎯 8. Seerr (`http://seerr:5055` / `https://request.vrg.rocks` / `https://seerr.vrg.rocks`)
* **Core Version:** `3.5.0`
* **Container DNS:** `8.8.8.8`, `1.1.1.1`. Network alias `jellyseerr`.
* **Service Integrations:**
  - **Radarr:** `http://radarr:7878`, Profile: `VRG HQ (UHD/FHD)`, Path: `/data/media/movies`, `preventSearch: true`.
  - **Sonarr:** `http://sonarr:8989`, Profile: `Ultra-HD`, Path: `/data/media/tv`, `preventSearch: true`.
  - **Jellyfin:** `http://jellyfin:8096`, Libraries: `Movies`, `Shows`.

---

### ⚡ 9. qBittorrent (`http://qbittorrent:8080` / `https://qb.vrg.rocks`)
* **WAN Port:** `42069` (TCP & UDP Port Forwarded).
* **Edge Auth:** qBittorrent Native Auth only. `import authentik` is intentionally omitted so the Android mobile torrent client can connect directly.
* **Container DNS:** `1.1.1.1`, `9.9.9.9`.
* **Mounts:** `${DOCKER_DATA_DIR}/torrents:/downloads` and `${DOCKER_DATA_DIR}:/data` (same host directory reachable as `/downloads` and `/data/torrents`).
* **Save Paths:** `/downloads/` (`/data/torrents`), Temp: `/downloads/incomplete/`.
* **Queue Limits:** Max Active Downloads: `5`, Max Active Torrents: `200`, Max Active Uploads: `200`.
* **AutoRun Hook:** Sends instant push notifications through `/config/scripts/ntfy_notify.sh "%N" "%L" "%Z"`.
* **Torrent Export:** Saves all `.torrent` files to `/downloads/files/`.
* **Backup Coverage:** `data/torrents/**/*.torrent`, `data/torrents/**/*.fastresume`, `config/qbittorrent/**/*.torrent`, and `config/qbittorrent/**/*.fastresume` are priority inclusions in the rclone filter. Payloads (`data/torrents/**`) are excluded.

---

### 🔁 10. Cross-Seed (`http://cross-seed:2468` / `https://cs.vrg.rocks`)
* **Image:** `ghcr.io/cross-seed/cross-seed:6`, `command: daemon`, `user: "${PUID}:${PGID}"`.
* **Mounts:** `/config`, `/downloads` (`data/torrents`), `/data` (full data root for library-wide `dataDirs` scanning of `/data/torrents` and `/data/media`), `/external`.
* **Operational Mode:** `matchMode: "partial"`, `linkType: "symlink"`, `linkDirs: ["/downloads/cross-seed-links", "/external/cross-seed-links"]`, `action: "inject"`.
* **Backup Coverage:** `config/cross-seed/torrent_cache/**` is a priority inclusion.
* **Diagnostics:** `scripts/test_cross_seed.sh` runs as `-u "${PUID:-501}:${PGID:-20}"` and reports write and hardlink results for `/external`, `/downloads`, and `/data/torrents` <-> `/data/media`.

---

## 3. Critical Findings & Optimization Roadmap

1. **🏆 Implement Recyclarr for Automated TRaSH Formats Sync:**
   - Neither Radarr nor Sonarr has Custom Formats.
   - *Status:* `recyclarr` (`ghcr.io/recyclarr/recyclarr:latest`, `CRON_SCHEDULE: "@daily"`) is declared under `profiles: ["standby"]` in `compose/media.yml`.
   - *Recommendation:* Write `config/recyclarr/recyclarr.yml`, then run `docker compose --profile standby up -d recyclarr`. Sync TRaSH `UHD Bluray + WEB` and `WEB-1080p` scoring profiles to prioritize HDR10+, Dolby Vision (with HDR fallback), TrueHD/Atmos/DTS-HD audio, and block low-bitrate YTS/CAM releases.
2. **🏷️ Standardize Movie Renaming in Radarr:**
   - `Rename Movies` is `False` in Radarr.
   - *Recommendation:* Enable `Rename Movies: True` and set the format to:
     `{Movie CleanTitle} ({Release Year}) [imdbid-{ImdbId}] - [{Quality Full}] [{MediaInfo VideoDynamicRangeType}] [{MediaInfo VideoBitDepth}bit] [{MediaInfo VideoCodec}] [{MediaInfo AudioFormat} {MediaInfo AudioChannels}]-{Release Group}`
3. **⚡ Enable Transcoding Throttling in Jellyfin:**
   - *Container:* In `config/jellyfin/encoding.xml`, enable `<EnableThrottling>true</EnableThrottling>` with `120s` delay to prevent CPU exhaustion on software transcodes. Not yet verified after the August rescan.
   - *Metal:* The `--reset` bootstrap of `scripts/setup_jellyfin_metal.py` sets `EnableThrottling: true` and `ThrottleDelaySeconds: 120` together with VideoToolbox. Route heavy 4K transcodes to `metal.vrg.rocks`.
4. **🛡️ Fix RuTracker.org Routing in Prowlarr:**
   - Tag RuTracker with `flaresolverr` so queries route through `http://flaresolverr:8191`, which Byparr now answers.
   - Byparr targets Cloudflare Turnstile, which FlareSolverr no longer solved reliably.
5. **🔌 Sonarr Download Client Authentication:**
   - Re-save the qBittorrent password in Sonarr (`Settings -> Download Clients -> qBittorrent`) to clear the communication check alert.
6. **📂 Complete the Unified `/data/torrents` Migration:**
   - `qbittorrent` and `cross-seed` now mount both `/downloads` and `/data`.
   - *Recommendation:* Move qBittorrent default and category save paths from `/downloads/...` to `/data/torrents/...`, update cross-seed `linkDirs` to `/data/torrents/cross-seed-links`, remove the Radarr `/downloads/movies` remote path mapping, run `scripts/test_cross_seed.sh`, then drop the `/downloads` mounts.
