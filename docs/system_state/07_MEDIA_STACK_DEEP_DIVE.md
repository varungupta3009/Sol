# 07. Media & Ingestion Stack: Deep Architectural Audit & State Documentation

> **Scope:** Full live API and configuration audit of the entire Sol media ecosystem (Radarr, Sonarr, Prowlarr, Bazarr, Jellyfin, Jellyseerr, and qBittorrent).  
> **Host:** Apple Silicon M1 Pro macOS (OrbStack / Docker Engine)  
> **Audit Date:** August 2026 (Live API Rescan)  
> **Mode:** Read-Only State Inspection & Optimization Roadmap  

---

## 1. End-to-End Media Pipeline Dataflow

```
                             [ User Request ]
                                    |
                                    v
                     +-----------------------------+
                     |         Jellyseerr          | (https://request.vrg.rocks)
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
                     +-----------------------------+
                     |          Prowlarr           | (https://prowlarr.vrg.rocks)
                     | (Centralized Indexer Proxy) |
                     +--------------+--------------+
                                    | (Pushes Torrents)
                                    v
                     +-----------------------------+
                     |         qBittorrent         | (Port: 42069 / WAN)
                     |     (BitTorrent Client)     |
                     +--------------+--------------+
                                    | (Downloads to /data/torrents)
                                    v
                     +-----------------------------+
                     |       APFS Hardlinks        | (Instant Zero-Copy Move)
                     |  -> /data/media/movies      |
                     |  -> /external/Movies        | (PANOPTICON - 759 GB Free)
                     |  -> /data/media/tv          |
                     |  -> /external/TV Shows      | (PANOPTICON - 759 GB Free)
                     +--------------+--------------+
                                    |
                    +---------------+---------------+
                    |                               |
                    v (Subtitle Sync)               v (Media Streaming)
     +-----------------------------+ +-----------------------------+
     |           Bazarr            | |          Jellyfin           |
     |   (Subtitles Automation)    | | (Hardware-Accelerated Stream|
     +-----------------------------+ +-----------------------------+
                    |                               |
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
* **Storage Root Folders:**
  - `/data/media/movies` *(Internal SSD: Accessible, 21.0 GB Free)*.
  - `/external/Movies` *(External PANOPTICON: Accessible, 759.4 GB Free)*.
* **Quality Profiles:**
  - `VRG HQ (UHD/FHD)` *(Default)*: Includes Remux-2160p, Bluray-2160p, WEBDL-2160p, Remux-1080p, Bluray-1080p, WEBDL-1080p.
  - **Upgrade Allowed:** `False` *(Will not auto-upgrade releases once downloaded)*.
* **Custom Formats (TRaSH Guides):** **`0` Active Formats** *(No scoring rules for HDR10+, Dolby Vision, AV1, lossless audio, or low-quality release filters)*.
* **Media Management & Naming:**
  - `Rename Movies`: **`False`** *(Keeps raw torrent scene names e.g. `Movie.Title.2024.2160p.HDR.x265-GROUP.mkv`)*.
  - `Use Hardlinks instead of Copy`: `True` *(Zero-copy APFS linking active)*.
* **Download Client Mapping:**
  - `qBittorrent`: `http://qbittorrent:8080`, category: `radarr`.
  - Remote Path Mapping: `/downloads/movies` -> `/data/torrents/movies/`.

---

### 📺 2. Sonarr (`http://sonarr:8989` / `https://sonarr.vrg.rocks`)
* **Core Version:** `4.0.19.2979` | **Database:** SQLite 3.53.2
* **Storage Root Folders:**
  - `/data/media/tv` *(Internal SSD: Accessible, 21.0 GB Free)*.
  - `/external/TV Shows` *(External PANOPTICON: Accessible, 759.4 GB Free)*.
* **Quality Profiles:**
  - `Ultra-HD` *(Default)*: WEB-2160p, Bluray-2160p, Remux-2160p (Cutoff: `Bluray-2160p`, Upgrades Allowed: `True`).
  - `HD-1080p`: Bluray-1080p, WEB-1080p, HDTV-1080p.
* **Custom Formats / Release Profiles:** **`0` Active Custom Formats**.
* **Media Management & Naming:**
  - `Rename Episodes`: **`True`** *(Active)*.
  - `Standard Episode Format`: `{Series Title} - S{season:00}E{episode:00} - {Episode Title} [{Quality Full}] [{MediaInfo VideoDynamicRangeType}] [{MediaInfo VideoBitDepth}bit] [{MediaInfo VideoCodec}] [{MediaInfo AudioFormat} {MediaInfo AudioChannels}] [{Release Group}]` *(Excellent TRaSH format)*.
  - `Season Folder Format`: `Season {season:00}`.
  - `Use Hardlinks instead of Copy`: `True` *(Active)*.
* **Health Notice:**
  - `DownloadClientCheck`: Recheck connection password/settings for qBittorrent in Sonarr.

---

### 🔍 3. Prowlarr (`http://prowlarr:9696` / `https://prowlarr.vrg.rocks`)
* **Core Version:** `1.31.2.4975`
* **Active Indexers:**
  - `IPTorrents` (Private Tracker / VIP Passkey)
  - `1337x`, `Milkie`, `The Pirate Bay`, `TheRARBG`, `upload.cx`, `YTS` (Public Trackers)
  - `RuTracker.org` *(Warning: Connection timeout / Cloudflare challenge)*
  - `DesiTorrents` *(Disabled)*
* **Application Synchronization:** Full Sync active to Radarr, Sonarr, and Lidarr.
* **Proxy Configuration:** FlareSolverr proxy active at `http://flaresolverr:8191` with `flaresolverr` tag routing.

---

### 💬 4. Bazarr (`http://bazarr:6767` / `https://bazarr.vrg.rocks`)
* **Core Version:** `1.6.0` | **Python:** `3.12.13`
* **Active Providers:** `opensubtitlescom`, `embeddedsubtitles`, `yifysubtitles`, `tvsubtitles`, `wizdom`, `subdl`.
* **OpenSubtitles.com:** VIP Account configured (`varungupta3009`).
* **Scoring Rules:** Series Threshold: `90`, Movie Threshold: `70`.
* **Embedded Subtitles:** `ffprobe` extraction enabled, OCR uppercase fixes active.
* **Jellyfin Notification:** Automated library refresh on subtitle download.

---

### 🍿 5. Jellyfin (`http://jellyfin:8096` / `https://watch.vrg.rocks`)
* **Core Version:** `10.11.11`
* **Active Libraries:**
  - `Movies` (`/config/data/root/default/Movies`)
  - `Shows` (`/config/data/root/default/Shows`)
  - `Collections` & `Playlists`
* **Hardware Acceleration:** **`none` (Software CPU decoding/encoding)**.
* **Transcoding Throttling:** **`false` (Unthrottled CPU load during transcode)**.
* **Installed Plugins:**
  - `Intro Skipper` *(Automatic episode intro detection & skip button)*.
  - `TMDb`, `OMDb`, `TheTVDB`, `OpenSubtitles`, `AudioDB`, `MusicBrainz`, `Studio Images`, `Chapter Creator`, `Jellyfin Enhanced`, `SSO-Auth`.

---

### 🎯 6. Jellyseerr (`http://jellyseerr:5055` / `https://request.vrg.rocks`)
* **Core Version:** `2.7.3`
* **Service Integrations:**
  - **Radarr:** `http://radarr:7878`, Profile: `VRG HQ (UHD/FHD)`, Path: `/data/media/movies`, `preventSearch: true`.
  - **Sonarr:** `http://sonarr:8989`, Profile: `Ultra-HD`, Path: `/data/media/tv`, `preventSearch: true`.
  - **Jellyfin:** `http://jellyfin:8096`, Libraries: `Movies`, `Shows`.

---

### ⚡ 7. qBittorrent (`http://qbittorrent:8080` / `https://qb.vrg.rocks`)
* **WAN Port:** `42069` (TCP & UDP Port Forwarded).
* **Save Paths:** `/downloads/` (`/data/torrents`), Temp: `/downloads/incomplete/`.
* **Queue Limits:** Max Active Downloads: `5`, Max Active Torrents: `200`, Max Active Uploads: `200`.
* **AutoRun Hook:** Dispatches instant push notifications via `/config/scripts/ntfy_notify.sh "%N" "%L" "%Z"`.
* **Torrent Export:** Automatically saves all `.torrent` files to `/downloads/files/`.

---

## 3. Critical Findings & Optimization Roadmap

1. **🏆 Implement Recyclarr for Automated TRaSH Formats Sync:**
   - Neither Radarr nor Sonarr currently have Custom Formats.
   - *Recommendation:* Run `recyclarr` to sync TRaSH `UHD Bluray + WEB` and `WEB-1080p` scoring profiles to prioritize HDR10+, Dolby Vision (with HDR fallback), TrueHD/Atmos/DTS-HD audio, and automatically blacklist low-bitrate YTS/CAM releases.
2. **🏷️ Standardize Movie Renaming in Radarr:**
   - `Rename Movies` is currently `False` in Radarr.
   - *Recommendation:* Enable `Rename Movies: True` and set format to:
     `{Movie CleanTitle} ({Release Year}) [imdbid-{ImdbId}] - [{Quality Full}] [{MediaInfo VideoDynamicRangeType}] [{MediaInfo VideoBitDepth}bit] [{MediaInfo VideoCodec}] [{MediaInfo AudioFormat} {MediaInfo AudioChannels}]-{Release Group}`
3. **⚡ Enable Transcoding Throttling in Jellyfin:**
   - In `config/jellyfin/encoding.xml`, enable `<EnableThrottling>true</EnableThrottling>` with `120s` delay to prevent CPU exhaustion on software transcodes.
4. **🛡️ Fix RuTracker.org Routing in Prowlarr:**
   - Tag RuTracker with `flaresolverr` so queries automatically route through `http://flaresolverr:8191`.
5. **🔌 Sonarr Download Client Authentication:**
   - Re-save qBittorrent password in Sonarr (`Settings -> Download Clients -> qBittorrent`) to clear the communication check alert.
