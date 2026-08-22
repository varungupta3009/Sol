# 03. Ingress, Routing & Network Architecture

> **Scope:** Reverse proxy configurations, SSL/TLS termination, HTTP/3 transport, identity middleware integration, network topology, and DNS routing on `Sol`.  
> **Proxy Engine:** Caddy v2 (`caddy:latest`) with automatic Let's Encrypt / ZeroSSL certificate provisioning.  
> **Primary Domain:** `*.vrg.rocks`  
> **Upstream Host Gateway:** `host.docker.internal` (OrbStack / macOS Bridge)  

---

## 1. Edge Proxy Architecture & Middleware

Caddy serves as the single unified ingress gateway for the entire Sol home server. All traffic arriving on ports `80` (HTTP) and `443` (HTTPS & HTTP/3 / QUIC) is inspected, authenticated, compressed, and proxied to internal container bridge endpoints or local network devices.

```
                                      [ Inbound Traffic ]
                                     https://<subdomain>.vrg.rocks
                                               |
                                               v
                                +------------------------------+
                                |        Caddy v2 Proxy        |
                                |  (:80, :443 TCP, :443 UDP)   |
                                +--------------+---------------+
                                               |
                     +-------------------------+-------------------------+
                     |                                                   |
                     v                                                   v
        [ Static Web Handlers ]                             [ Reverse Proxy Handlers ]
        -----------------------                             --------------------------
        - mind.vrg.rocks   (/mind)                          - Authenticated via Authentik Outpost
        - fam.vrg.rocks    (/fam)                           - Direct / Application-Native Auth
        - scan.vrg.rocks   (/scan)                          - External LAN Gateway (Router / HA)
        - aysynbm.vrg.rocks(/aysynbm)                       - High-Performance Compression (zstd/gzip)
```

### Global Options & Performance Snippets

```caddyfile
# Global Options
{
    log # Enables Caddy structured access logging
}

# (optimize) Snippet: Enables ultra-fast compression across all proxied interfaces
(optimize) {
    encode zstd gzip
}

# (authentik) Snippet: Enforces forward authentication against the Authentik outpost
(authentik) {
    forward_auth authentik-server:9000 {
        uri /outpost.goauthentik.io/auth/caddy
        copy_headers X-Authentik-Username X-Authentik-Groups X-Authentik-Entitlements X-Authentik-Email X-Authentik-Name X-Authentik-Uid X-Authentik-Jwt X-Authentik-Meta-Jwks X-Authentik-Meta-Outpost X-Authentik-Meta-Provider X-Authentik-Meta-App X-Authentik-Meta-Version
        trusted_proxies private_ranges
    }
}
```

---

## 2. Master Reverse Proxy Routing Table

| Subdomain / Hostname | Local Upstream Target | Compression | Auth Model / Policy | Special Headers / Notes |
| :--- | :--- | :--- | :--- | :--- |
| **`router.vrg.rocks`** | `http://192.168.50.1:80` | `zstd/gzip` | Router Native Auth | Proxies to physical LAN Router Gateway |
| **`auth.vrg.rocks`** | `http://authentik-server:9000` | `zstd/gzip` | Authentik Native | Central Identity & SSO Web Portal |
| **`dash.vrg.rocks`** | `http://glance:8080` | `zstd/gzip` | Direct / Dashboard | Glance Home Server Dashboard |
| **`sol.vrg.rocks`** | *(Redirect)* | N/A | Direct | HTTP 302 redirect to `https://dash.vrg.rocks/sol` |
| **`arcane.vrg.rocks`** | `http://arcane:3552` | `zstd/gzip` | Authentik (Forward & OIDC)| Docker stack and container management |
| **`jellyfin.vrg.rocks`** | `http://jellyfin:8096` | *(Bypassed)* | Jellyfin Native Auth | Primary media streaming UI & API |
| **`watch.vrg.rocks`** | `http://jellyfin:8096` | *(Bypassed)* | Jellyfin Native Auth | Friendly alias for Jellyfin media streaming |
| **`metal.vrg.rocks`** | `http://host.docker.internal:8097`| *(Bypassed)* | Jellyfin Native Auth | Native Apple Silicon VideoToolbox Jellyfin Metal |
| **`jellyseerr.vrg.rocks`**| `http://jellyseerr:5055` | `zstd/gzip` | Authentik (Forward Auth) | Media discovery & request manager |
| **`request.vrg.rocks`** | `http://jellyseerr:5055` | `zstd/gzip` | Authentik (Forward Auth) | Friendly alias for Jellyseerr requests |
| **`radarr.vrg.rocks`** | `http://radarr:7878` | `zstd/gzip` | Authentik (Forward Auth) | Movie automation & collection manager |
| **`sonarr.vrg.rocks`** | `http://sonarr:8989` | `zstd/gzip` | Authentik (Forward Auth) | TV series automation & tracker |
| **`prowlarr.vrg.rocks`** | `http://prowlarr:9696` | `zstd/gzip` | Authentik (Forward Auth) | Torrent & Usenet indexer manager |
| **`bazarr.vrg.rocks`** | `http://bazarr:6767` | `zstd/gzip` | Authentik (Forward Auth) | Subtitle download & synchronization |
| **`lidarr.vrg.rocks`** | `http://lidarr:8686` | `zstd/gzip` | Authentik (Forward Auth) | Music automation & discography manager |
| **`qbittorrent.vrg.rocks`**| `http://qbittorrent:8080` | `zstd/gzip` | qBittorrent Native | Torrent client Web UI |
| **`qb.vrg.rocks`** | `http://qbittorrent:8080` | `zstd/gzip` | qBittorrent Native | Short URL alias for qBittorrent |
| **`cs.vrg.rocks`** | `http://cross-seed:2468` | `zstd/gzip` | Authentik (Forward Auth) | Cross-Seed daemon management API |
| **`paperless.vrg.rocks`** | `http://paperless-webserver:8000` | `zstd/gzip` | Paperless OIDC (Authentik)| Document management & OCR server |
| **`docs.vrg.rocks`** | `http://paperless-webserver:8000` | `zstd/gzip` | Paperless OIDC (Authentik)| Friendly alias for Paperless-ngx |
| **`ntfy.vrg.rocks`** | `http://ntfy:80` | `zstd/gzip` | Direct / Token Auth | HTTP push notification publish/subscribe |
| **`code.vrg.rocks`** | `http://code-server:8443` | `zstd/gzip` | code-server Argon2 Hash | Browser-based VSCode IDE |
| **`coder.vrg.rocks`** | `http://coder:7080` | `zstd/gzip` | Authentik (Forward Auth) | Coder cloud development environments |
| **`copyparty.vrg.rocks`** | `http://copyparty:3923` | `zstd/gzip` | Authentik + Copyparty ACL| High-speed file server & WebDAV |
| **`files.vrg.rocks`** | `http://copyparty:3923` | `zstd/gzip` | Authentik + Copyparty ACL| Friendly alias for Copyparty file browser |
| **`inv.vrg.rocks`** | `http://homebox:7745` | `zstd/gzip` | Authentik (Forward Auth) | Homebox inventory (Full CORS & OPTIONS support) |
| **`ignis.vrg.rocks`** | `http://ignis:8080` | `zstd/gzip` | Authentik (Forward Auth) | Ignis Obsidian vault synchronizer |
| **`mind.vrg.rocks`** | `file_server /mind` | `zstd/gzip` | Authentik (Forward Auth) | Static Quartz PKM Digital Garden |
| **`fam.vrg.rocks`** | `file_server /fam` | `zstd/gzip` | Authentik (Forward Auth) | Static Family Data Vault web application |
| **`scan.vrg.rocks`** | `file_server /scan` | `zstd/gzip` | Authentik (Forward Auth) | Static Homebox Barcode Scanner PWA |
| **`aysynbm.vrg.rocks`** | `file_server /aysynbm` | `zstd/gzip` | Direct Static | Static Async Bookmark Manager frontend |
| **`homarr.vrg.rocks`** *(Inact)* | `http://homarr:7575` | `zstd/gzip` | Authentik (Forward Auth) | Homarr dashboard (Inactive) |
| **`kuma.vrg.rocks`** *(Inact)* | `http://uptime-kuma:3001` | `zstd/gzip` | Authentik (Forward Auth) | Uptime Kuma monitoring (Inactive) |
| **`dozzle.vrg.rocks`** *(Inact)*| `http://dozzle:8080` | `zstd/gzip` | Authentik (Forward Auth) | Dozzle log viewer (Inactive) |
| **`dockge.vrg.rocks`** *(Inact)*| `http://dockge:5001` | `zstd/gzip` | Authentik (Forward Auth) | Dockge stack manager (Inactive) |
| **`beszel.vrg.rocks`** *(Inact)*| `http://beszel:8090` | `zstd/gzip` | Authentik (Forward Auth) | Beszel metrics hub (Inactive) |
| **`wizarr.vrg.rocks`** *(Inact)*| `http://wizarr:5690` | `zstd/gzip` | Authentik (Forward Auth) | Wizarr user invitation portal (Inactive) |
| **`kavita.vrg.rocks`** *(Inact)*| `http://kavita:5000` | `zstd/gzip` | Authentik (Forward Auth) | Kavita digital book reader (Inactive) |
| **`calibre.vrg.rocks`** *(Inact)*| `http://calibre:8080` | `zstd/gzip` | Authentik (Forward Auth) | Calibre desktop VM interface (Inactive) |
| **`calibre-web.vrg.rocks`** *(Inact)*| `http://calibre-web:8083` | `zstd/gzip` | Authentik (Forward Auth) | Calibre-Web reader & manager (Inactive) |
| **`qbit_manage.vrg.rocks`** *(Inact)*| `http://qbit_manage:8181` | `zstd/gzip` | Authentik (Forward Auth) | qBit Manage Web API (Inactive) |
| **`qbm.vrg.rocks`** *(Inact)* | `http://qbit_manage:8181` | `zstd/gzip` | Authentik (Forward Auth) | Short alias for qbit_manage (Inactive) |
| **`flood.vrg.rocks`** *(Inact)*| `http://flood:3000` | `zstd/gzip` | Authentik (Forward Auth) | Flood torrent interface (Inactive) |
| **`vault.vrg.rocks`** *(Inact)*| `http://vaultwarden:80` | `zstd/gzip` | Authentik (Forward Auth) | Vaultwarden password vault (Inactive) |
| **`pass.vrg.rocks`** *(Inact)* | `http://vaultwarden:80` | `zstd/gzip` | Authentik (Forward Auth) | Short alias for Vaultwarden (Inactive) |
| **`n8n.vrg.rocks`** *(Inact)* | `http://n8n:5678` | `zstd/gzip` | Authentik (Forward Auth) | n8n workflow automation (Inactive) |
| **`home.vrg.rocks`** *(Inact)*| `http://host.docker.internal:8123` | `zstd/gzip` | Authentik (Forward Auth) | Home Assistant (Host networking via OrbStack) |
| **`leaf.vrg.rocks`** *(Inact)* | `http://leafwiki:8080` | `zstd/gzip` | Authentik (Forward Auth) | LeafWiki digital garden (Inactive) |
| **`rclone.vrg.rocks`** *(Inact)*| `http://rclone-gui:5572` | `zstd/gzip` | Authentik (Forward Auth) | Rclone Web GUI remote manager (Inactive) |

---

## 3. Network Topology & Cross-Container Communication

```
  +-------------------------------------------------------------------------------+
  | HOST SYSTEM (macOS / OrbStack Bridge Gateway: host.docker.internal)          |
  |                                                                               |
  |   Physical Ports Exposed to LAN/WAN:                                          |
  |   - :80, :443 (Caddy Reverse Proxy)                                           |
  |   - :9000, :9443 (Authentik SSO HTTP/HTTPS)                                   |
  |   - :42069 (qBittorrent WAN Wire Protocol)                                    |
  |                                                                               |
  |   +-----------------------------------------------------------------------+   |
  |   | DOCKER COMPOSE BRIDGE NETWORK ('default')                             |   |
  |   |                                                                       |   |
  |   |  - Caddy [172.x.x.x] <-------------> Authentik Server (:9000)        |   |
  |   |                                          | (DB Connection)            |   |
  |   |                                          v                            |   |
  |   |                                      PostgreSQL 16 (:5432)            |   |
  |   |                                                                       |   |
  |   |  - Prowlarr (:9696) <---------------> FlareSolverr (:8191)            |   |
  |   |        | (Torznab APIs)                                               |   |
  |   |        v                                                              |   |
  |   |    Cross-Seed (:2468) <-------------> qBittorrent (:8080)             |   |
  |   |        ^                                      ^                       |   |
  |   |        | (Media Requests)                     | (Atomic Hardlinks)    |   |
  |   |    Radarr (:7878) / Sonarr (:8989) / Lidarr (:8686)                   |   |
  |   |        ^                                                              |   |
  |   |        | (User Media Requests)                                        |   |
  |   |    Jellyseerr (:5055) [DNS: 8.8.8.8, 1.1.1.1]                         |   |
  |   |        |                                                              |   |
  |   |        v (Library Sync)                                               |   |
  |   |    Jellyfin (:8096)                                                   |   |
  |   |                                                                       |   |
  |   |  - Paperless-Webserver (:8000)                                        |   |
  |   |        |----------> Paperless-Broker (Redis :6379)                    |   |
  |   |        |----------> Paperless-DB (PostgreSQL 17 :5432)                |   |
  |   |        |----------> ntfy (:80) [Webhook Notifications]                |   |
  |   |                                                                       |   |
  |   +-----------------------------------------------------------------------+   |
  +-------------------------------------------------------------------------------+
```

### DNS & Upstream Resolution
1. **OrbStack Host Access (`host.docker.internal`):**
   - Enables Caddy and containerized services to access host-bound services (e.g. Home Assistant on `8123`) without fragile IP hardcoding.
2. **ISP DNS Filtering Bypass (`8.8.8.8`, `1.1.1.1`):**
   - Local Indian ISPs frequently throttle or block TMDb (The Movie Database) API endpoints required by Jellyseerr and *arr apps.
   - Jellyseerr explicitly overrides Docker default DNS with Google (`8.8.8.8`) and Cloudflare (`1.1.1.1`) resolvers in compose.

### CORS & Preflight Rule Architecture (`inv.vrg.rocks`)
For Homebox inventory access via the PWA mobile scanner (`https://scan.vrg.rocks`), Caddy injects dynamic CORS headers:
```caddyfile
inv.vrg.rocks {
    import optimize
    import authentik

    @allowed_origins header Origin *
    header @allowed_origins {
        Access-Control-Allow-Origin "{http.request.header.Origin}"
        Access-Control-Allow-Methods "GET, POST, OPTIONS, PUT, DELETE"
        Access-Control-Allow-Headers "Origin, Content-Type, Authorization, Accept"
        Access-Control-Allow-Credentials true
    }

    @options {
        method OPTIONS
        header Origin *
    }
    respond @options 204

    reverse_proxy http://homebox:7745
}
```
This enables the mobile scanner PWA running on `https://scan.vrg.rocks` to execute authenticated API queries and item lookups against `https://inv.vrg.rocks` without cross-origin browser rejections.
