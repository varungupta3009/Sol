# 03. Ingress, Routing & Network Architecture

> **Scope:** Reverse proxy configuration, SSL/TLS termination, HTTP/3 transport, identity middleware integration, network topology, and DNS routing on `Sol`.  
> **Proxy Engine:** Caddy v2 (`caddy:${CADDY_TAG:-2}`) with automatic Let's Encrypt / ZeroSSL certificate provisioning.  
> **Primary Domain:** `*.vrg.rocks`  
> **Upstream Host Gateway:** `host.docker.internal` (OrbStack / macOS Bridge)  
> **Caddyfile State:** 27 active site blocks, 18 commented standby vhosts  
> **Last Synced to Ground Truth:** 2026-10-17  

---

## 1. Edge Proxy Architecture & Middleware

Caddy is the single ingress gateway for the Sol home server. It inspects, authenticates, compresses, and proxies all traffic on ports `80` (HTTP) and `443` (HTTPS and HTTP/3 / QUIC) to internal bridge endpoints, the native macOS host, or LAN devices.

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
        - mind.vrg.rocks   (/mind)   [SSO]                  - Authenticated via Authentik Outpost
        - fam.vrg.rocks    (/fam)    [SSO]                  - Direct / Application-Native Auth
        - scan.vrg.rocks   (/scan)   [SSO]                  - Native macOS Host (Jellyfin Metal :8097, HA :8123)
        - aysynbm.vrg.rocks(/aysynbm)                       - External LAN Gateway (Router 192.168.50.1)
                                                            - Compression (zstd/gzip) except Jellyfin streams
```

### Global Options & Reusable Snippets

```caddyfile
# Global Options
{
	log {
		output stdout
		format console
		level INFO
	}
}

# (optimize) Snippet: Text & asset compression
(optimize) {
	encode zstd gzip
}

# (security_headers) Snippet: Baseline security headers
(security_headers) {
	header {
		X-Content-Type-Options nosniff
		X-Frame-Options SAMEORIGIN
		Referrer-Policy strict-origin-when-cross-origin
		Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
		-Server
	}
}

# (forward_auth) Snippet: Forward authentication against the Authentik embedded outpost
(forward_auth) {
	forward_auth authentik-server:9000 {
		uri /outpost.goauthentik.io/auth/caddy
		copy_headers X-Authentik-Username X-Authentik-Groups X-Authentik-Entitlements X-Authentik-Email X-Authentik-Name X-Authentik-Uid X-Authentik-Jwt X-Authentik-Meta-Jwks X-Authentik-Meta-Outpost X-Authentik-Meta-Provider X-Authentik-Meta-App X-Authentik-Meta-Version
		trusted_proxies private_ranges
	}
}

# (static_site) Snippet: Routing, clean URLs, compression & error fallbacks
(static_site) {
	import optimize
	import security_headers
	try_files {path} {path}.html {path}/ =404
	file_server
	handle_errors {
		rewrite * /{err.status_code}.html
		file_server
	}
}
```

### Streaming Transport (Jellyfin & Jellyfin Metal)
`watch.vrg.rocks` / `jellyfin.vrg.rocks` and `metal.vrg.rocks` skip `import optimize` (no compression on video streams). They use an inline transport block:

```caddyfile
reverse_proxy <upstream> {
	transport http {
		read_buffer 32768
		write_buffer 32768
		keepalive 120s
	}
}
```

---

## 2. Master Reverse Proxy Routing Table

### 2.1 Active Routes (27 Site Blocks)

| Subdomain / Hostname | Local Upstream Target | Compression | Auth Model / Policy | Special Headers / Notes |
| :--- | :--- | :--- | :--- | :--- |
| **`auth.vrg.rocks`** | `http://authentik-server:9000` | `zstd/gzip` | Authentik Native | Central Identity & SSO Web Portal |
| **`arcane.vrg.rocks`** | `http://arcane:3552` | `zstd/gzip` | Authentik (Forward & OIDC) | Docker stack and container management |
| **`router.vrg.rocks`** | `http://192.168.50.1` | `zstd/gzip` | Authentik (Forward Auth) + Router Native | Proxies to physical LAN Router Gateway |
| **`dash.vrg.rocks`** | `http://glance:8080` | `zstd/gzip` | Authentik (Forward Auth) | Glance Home Server Dashboard |
| **`sol.vrg.rocks`** | *(Redirect)* | N/A | Direct | HTTP 302 redirect to `https://dash.vrg.rocks/sol` |
| **`watch.vrg.rocks`** | `http://jellyfin:8096` | *(Bypassed)* | Jellyfin Native Auth | Friendly alias for Jellyfin, streaming transport tuning |
| **`jellyfin.vrg.rocks`** | `http://jellyfin:8096` | *(Bypassed)* | Jellyfin Native Auth | Primary media streaming UI & API |
| **`metal.vrg.rocks`** | `http://host.docker.internal:8097` | *(Bypassed)* | Jellyfin Native Auth | Native macOS Jellyfin Metal (VideoToolbox), streaming transport tuning |
| **`request.vrg.rocks`** | `http://seerr:5055` | `zstd/gzip` | Authentik (Forward Auth) | Friendly alias for Seerr requests |
| **`jellyseerr.vrg.rocks`**| `http://seerr:5055` | `zstd/gzip` | Authentik (Forward Auth) | Legacy alias for Seerr requests |
| **`seerr.vrg.rocks`** | `http://seerr:5055` | `zstd/gzip` | Authentik (Forward Auth) | Seerr media discovery & requests |
| **`radarr.vrg.rocks`** | `http://radarr:7878` | `zstd/gzip` | Authentik (Forward Auth) | Movie automation & collection manager |
| **`sonarr.vrg.rocks`** | `http://sonarr:8989` | `zstd/gzip` | Authentik (Forward Auth) | TV series automation & tracker |
| **`bazarr.vrg.rocks`** | `http://bazarr:6767` | `zstd/gzip` | Authentik (Forward Auth) | Subtitle download & synchronization |
| **`lidarr.vrg.rocks`** | `http://lidarr:8686` | `zstd/gzip` | Authentik (Forward Auth) | Music automation & discography manager |
| **`prowlarr.vrg.rocks`** | `http://prowlarr:9696` | `zstd/gzip` | Authentik (Forward Auth) | Torrent & Usenet indexer manager |
| **`byparr.vrg.rocks`** | `http://byparr:8191` | `zstd/gzip` | Authentik (Forward Auth) | Byparr Cloudflare Turnstile solver |
| **`flaresolverr.vrg.rocks`** | `http://byparr:8191` | `zstd/gzip` | Authentik (Forward Auth) | Legacy hostname served by Byparr |
| **`qb.vrg.rocks`** | `http://qbittorrent:8080` | `zstd/gzip` | qBittorrent Native (no Authentik) | Short URL alias. Android mobile torrent client connects directly and cannot follow SSO redirects. |
| **`qbittorrent.vrg.rocks`**| `http://qbittorrent:8080` | `zstd/gzip` | qBittorrent Native (no Authentik) | Torrent client Web UI |
| **`cs.vrg.rocks`** | `http://cross-seed:2468` | `zstd/gzip` | Authentik (Forward Auth) | Cross-Seed daemon management API |
| **`docs.vrg.rocks`** | `http://paperless-webserver:8000` | `zstd/gzip` | Paperless OIDC (Authentik) | Friendly alias for Paperless-ngx |
| **`paperless.vrg.rocks`** | `http://paperless-webserver:8000` | `zstd/gzip` | Paperless OIDC (Authentik) | Document management & OCR server |
| **`ignis.vrg.rocks`** | `http://ignis:8080` | `zstd/gzip` | Authentik (Forward Auth) | Ignis Obsidian vault synchronizer |
| **`code.vrg.rocks`** | `http://code-server:8443` | `zstd/gzip` | Authentik (Forward Auth) + code-server Argon2 Hash | Browser-based VSCode IDE |
| **`coder.vrg.rocks`** | `http://coder:7080` | `zstd/gzip` | Authentik (Forward Auth) | Coder cloud development environments |
| **`files.vrg.rocks`** | `http://copyparty:3923` | `zstd/gzip` | Authentik + Copyparty ACL | Friendly alias for Copyparty file browser |
| **`copyparty.vrg.rocks`** | `http://copyparty:3923` | `zstd/gzip` | Authentik + Copyparty ACL | High-speed file server & WebDAV |
| **`ntfy.vrg.rocks`** | `http://ntfy:80` | `zstd/gzip` | Direct / Token Auth | HTTP push notification publish/subscribe |
| **`home.vrg.rocks`** | `http://host.docker.internal:8123` | `zstd/gzip` | Authentik (Forward Auth) | Home Assistant. Route is active, but `homeassistant` runs only under `--profile standby`. |
| **`mind.vrg.rocks`** | `file_server /mind` | `zstd/gzip` | Authentik (Forward Auth) | Static Quartz PKM Digital Garden |
| **`fam.vrg.rocks`** | `file_server /fam` | `zstd/gzip` | Authentik (Forward Auth) | Static Family Data Vault web application |
| **`scan.vrg.rocks`** | `file_server /scan` | `zstd/gzip` | Authentik (Forward Auth) | Static Homebox Barcode Scanner PWA |
| **`aysynbm.vrg.rocks`** | `file_server /aysynbm` | `zstd/gzip` | Direct Static | Static Async Bookmark Manager frontend |

> [!NOTE]
> All active site blocks except `sol.vrg.rocks` import `(security_headers)`. Multi-host site blocks (`watch`/`jellyfin`, `request`/`jellyseerr`/`seerr`, `byparr`/`flaresolverr`, `qb`/`qbittorrent`, `docs`/`paperless`, `files`/`copyparty`) appear as one row per hostname, so the table holds 34 hostnames across 27 blocks.

### 2.2 Standby Routes (18 Commented Vhosts)

Each vhost below is commented out in `Caddyfile`. Uncomment it only after `docker compose --profile standby up -d <service>` starts the upstream.

| Subdomain / Hostname | Local Upstream Target | Compression | Auth Model / Policy | Special Headers / Notes |
| :--- | :--- | :--- | :--- | :--- |
| **`status.vrg.rocks`** *(Standby)* | `http://gatus:8080` | `zstd/gzip` | Direct (no Authentik) | Gatus public status page |
| **`kuma.vrg.rocks`** *(Standby)* | `http://uptime-kuma:3001` | `zstd/gzip` | Authentik (Forward Auth) | Uptime Kuma monitoring |
| **`beszel.vrg.rocks`** *(Standby)*| `http://beszel:8090` | `zstd/gzip` | Authentik (Forward Auth) | Beszel metrics hub |
| **`dozzle.vrg.rocks`** *(Standby)*| `http://dozzle:8080` | `zstd/gzip` | Authentik (Forward Auth) | Dozzle log viewer |
| **`dockge.vrg.rocks`** *(Standby)*| `http://dockge:5001` | `zstd/gzip` | Authentik (Forward Auth) | Dockge stack manager |
| **`homarr.vrg.rocks`** *(Standby)* | `http://homarr:7575` | `zstd/gzip` | Authentik (Forward Auth) | Homarr dashboard |
| **`wizarr.vrg.rocks`** *(Standby)*| `http://wizarr:5690` | `zstd/gzip` | Authentik (Forward Auth) | Wizarr user invitation portal |
| **`qbm.vrg.rocks`**, **`qbit_manage.vrg.rocks`** *(Standby)* | `http://qbit_manage:8181` | `zstd/gzip` | Authentik (Forward Auth) | qBit Manage Web API |
| **`flood.vrg.rocks`** *(Standby)*| `http://flood:3000` | `zstd/gzip` | Authentik (Forward Auth) | Flood torrent interface |
| **`paperless-ai.vrg.rocks`** *(Standby)* | `http://paperless-ai:3000` | `zstd/gzip` | Authentik (Forward Auth) | Paperless-AI document classifier |
| **`leaf.vrg.rocks`** *(Standby)* | `http://leafwiki:8080` | `zstd/gzip` | Authentik (Forward Auth) | LeafWiki digital garden |
| **`kavita.vrg.rocks`** *(Standby)*| `http://kavita:5000` | `zstd/gzip` | Authentik (Forward Auth) | Kavita digital book reader |
| **`calibre.vrg.rocks`** *(Standby)*| `http://calibre:8080` | `zstd/gzip` | Authentik (Forward Auth) | Calibre desktop VM interface |
| **`calibre-web.vrg.rocks`** *(Standby)*| `http://calibre-web:8083` | `zstd/gzip` | Authentik (Forward Auth) | Calibre-Web reader & manager |
| **`inv.vrg.rocks`** *(Standby)* | `http://homebox:7745` | `zstd/gzip` | Authentik (Forward Auth) | Homebox inventory, CORS restricted to `https://scan.vrg.rocks` (pending SQLite repair) |
| **`vault.vrg.rocks`**, **`pass.vrg.rocks`** *(Standby)*| `http://vaultwarden:80` | `zstd/gzip` | Authentik (Forward Auth) | Vaultwarden password vault |
| **`n8n.vrg.rocks`** *(Standby)* | `http://n8n:5678` | `zstd/gzip` | Authentik (Forward Auth) | n8n workflow automation |
| **`rclone.vrg.rocks`** *(Standby)*| `http://rclone-gui:5572` | `zstd/gzip` | Authentik (Forward Auth) | Rclone Web GUI remote manager |

### 2.3 Edge Authentication Changes (October 2026)

| Hostname | Previous Policy | Current Policy | Effect |
| :--- | :--- | :--- | :--- |
| `dash.vrg.rocks` | Direct / Dashboard | `import forward_auth` | Glance (which reads the Docker socket `ro`) requires SSO at the edge |
| `code.vrg.rocks` | code-server Argon2 Hash only | `import forward_auth` + Argon2 Hash | Two factors in series: Authentik SSO, then the code-server password (Caddyfile comment: "Gated by Authentik SSO + code-server password") |
| `router.vrg.rocks` | Router Native Auth only | `import forward_auth` + Router Native | Router admin UI requires SSO before the router login page loads |
| `byparr.vrg.rocks`, `flaresolverr.vrg.rocks` | Direct Internal API | `import forward_auth` | Edge access requires SSO. Prowlarr is unaffected because it calls `http://flaresolverr:8191` on the bridge, not through Caddy. |
| `qb.vrg.rocks`, `qbittorrent.vrg.rocks` | qBittorrent Native | qBittorrent Native (unchanged, documented exception) | Caddyfile comment: the Android mobile torrent client connects directly and cannot follow SSO redirects |
| `inv.vrg.rocks` | Authentik + wildcard CORS reflection | Commented out, CORS restricted to `https://scan.vrg.rocks` | Homebox is in standby. Credentialed CORS no longer reflects arbitrary origins. |

---

## 3. Network Topology & Cross-Container Communication

```
  +-------------------------------------------------------------------------------+
  | HOST SYSTEM (macOS / OrbStack Bridge Gateway: host.docker.internal)          |
  |                                                                               |
  |   Physical Ports Exposed to LAN/WAN:                                          |
  |   - :80, :443 TCP/UDP (Caddy Reverse Proxy)                                   |
  |   - :42069 TCP/UDP (qBittorrent WAN Wire Protocol)                            |
  |                                                                               |
  |   Loopback-Only Host Ports (127.0.0.1):                                       |
  |   - :9000, :9443 (Authentik SSO HTTP/HTTPS, local debugging)                  |
  |   - :53682 (rclone OAuth callback, ops/standby profile only)                  |
  |                                                                               |
  |   Native macOS Processes:                                                     |
  |   - Jellyfin Metal :8097 (VideoToolbox) <--- Caddy via host.docker.internal   |
  |   - Home Assistant :8123 (standby, network_mode: host)                        |
  |                                                                               |
  |   +-----------------------------------------------------------------------+   |
  |   | DOCKER COMPOSE BRIDGE NETWORK ('sol_default')                         |   |
  |   |                                                                       |   |
  |   |  - Caddy [172.x.x.x] <-------------> Authentik Server (:9000)        |   |
  |   |                                          | (DB Connection)            |   |
  |   |                                          v                            |   |
  |   |                                      PostgreSQL 16 (:5432)            |   |
  |   |                                                                       |   |
  |   |  - Prowlarr (:9696) <---------------> Byparr (:8191)                  |   |
  |   |        |                              (alias: flaresolverr)           |   |
  |   |        | (Torznab APIs)                                               |   |
  |   |        v                                                              |   |
  |   |    Cross-Seed (:2468) <-------------> qBittorrent (:8080)             |   |
  |   |        ^                                      ^                       |   |
  |   |        | (Media Requests)                     | (Atomic Hardlinks)    |   |
  |   |    Radarr (:7878) / Sonarr (:8989) / Lidarr (:8686)                   |   |
  |   |        ^                                                              |   |
  |   |        | (User Media Requests)                                        |   |
  |   |    Seerr (:5055) [DNS: 8.8.8.8, 1.1.1.1] (alias: jellyseerr)          |   |
  |   |        |                                                              |   |
  |   |        v (Library Sync)                                               |   |
  |   |    Jellyfin (:8096)                                                   |   |
  |   |                                                                       |   |
  |   |  - Paperless-Webserver (:8000)                                        |   |
  |   |        |----------> Paperless-Broker (Redis 8 Alpine :6379)           |   |
  |   |        |----------> Paperless-DB (PostgreSQL 17 Debian :5432)         |   |
  |   |        |----------> ntfy (:80) [Webhook Notifications]                |   |
  |   |                                                                       |   |
  |   +-----------------------------------------------------------------------+   |
  +-------------------------------------------------------------------------------+
```

### DNS & Upstream Resolution
1. **OrbStack Host Access (`host.docker.internal`):**
   - Lets Caddy reach host-bound services without IP hardcoding: Jellyfin Metal on `8097` and Home Assistant on `8123`.
   - The Coder workspace template maps `host.docker.internal` to `host-gateway` and rewrites `localhost` / `127.0.0.1` in the agent init script to it.
2. **ISP DNS Filtering Bypass:**
   - Local Indian ISPs often throttle or block TMDb (The Movie Database) API endpoints and public trackers.
   - Seerr overrides Docker default DNS with Google (`8.8.8.8`) and Cloudflare (`1.1.1.1`).
   - Radarr, Sonarr, Bazarr, Lidarr, Prowlarr, Byparr, FlareSolverr (standby), qBittorrent, and Cross-Seed override DNS with Cloudflare (`1.1.1.1`) and Quad9 (`9.9.9.9`).
3. **Network Aliases:**
   - `byparr` answers to `flaresolverr`, so Prowlarr's existing `http://flaresolverr:8191` proxy setting needs no change.
   - `seerr` answers to `jellyseerr` for backward-compatible routing.
   - Do not run the standby `flaresolverr` container next to `byparr`. Both would answer the `flaresolverr` name.

### CORS & Preflight Rule Architecture (`inv.vrg.rocks`, Standby)
The Homebox vhost is commented out while Homebox stays in standby. Its CORS rule is hardened from wildcard origin reflection to one fixed origin:

```caddyfile
# inv.vrg.rocks {
# 	import optimize
# 	import security_headers
# 	import forward_auth
#
# 	@allowed_origins header Origin https://scan.vrg.rocks
# 	header @allowed_origins {
# 		Access-Control-Allow-Origin "https://scan.vrg.rocks"
# 		Access-Control-Allow-Methods "GET, POST, OPTIONS, PUT, DELETE"
# 		Access-Control-Allow-Headers "Origin, Content-Type, Authorization, Accept"
# 		Access-Control-Allow-Credentials true
# 		Vary Origin
# 	}
#
# 	@options {
# 		method OPTIONS
# 		header Origin https://scan.vrg.rocks
# 	}
# 	respond @options 204
#
# 	reverse_proxy http://homebox:7745
# }
```

When restored, this rule lets the mobile scanner PWA on `https://scan.vrg.rocks` run authenticated API queries and item lookups against `https://inv.vrg.rocks`. Requests from any other origin receive no CORS headers, and the browser rejects them.

| Property | Previous Rule | Current Rule |
| :--- | :--- | :--- |
| Origin matcher | `header Origin *` | `header Origin https://scan.vrg.rocks` |
| `Access-Control-Allow-Origin` | `{http.request.header.Origin}` (reflected) | `"https://scan.vrg.rocks"` (fixed) |
| `Vary Origin` | Absent | Present |
| `security_headers` import | Absent | Present |
| Vhost state | Active | Commented (Homebox in standby) |
