# 03. Ingress, Routing & Network Architecture

> **Scope:** Reverse proxy configuration, SSL/TLS termination, HTTP/3 transport, identity middleware integration, network topology, and DNS routing on `Sol`.  
> **Proxy Engine:** Caddy v2.11.7 (`caddy:${CADDY_TAG:-latest}`) with automatic Let's Encrypt / ZeroSSL certificate provisioning.  
> **Primary Domain:** `*.vrg.rocks`  
> **Upstream Host Gateway:** `host.docker.internal` (OrbStack / macOS Bridge)  
> **Caddyfile State:** 41 active site blocks (31 reverse-proxy/redirect blocks + 10 static web app blocks, covering 48 active hostnames) and 12 commented standby vhost blocks (13 standby hostnames)  
> **Last Synced to Ground Truth:** 2026-10-20  

---

## 1. Edge Proxy Architecture & Middleware

Caddy (`caddy:latest`, running Caddy v2.11.7) is the single ingress gateway and static file server for the Sol home server (`compose/core.yml`). It terminates TLS 1.3 and HTTP/3 (QUIC), enforces baseline security headers, runs edge authentication via Tinyauth v5.2.0 (`tinyauth:3000`), compresses text responses (`zstd`/`gzip`), serves 10 static web applications directly from container bind mounts with zero extra container RAM, and proxies dynamic traffic to internal Docker bridge endpoints or LAN devices.

```
                                      [ Inbound Traffic ]
                                     https://<subdomain>.vrg.rocks
                                               |
                                               v
                                +------------------------------+
                                |      Caddy v2.11.7 Proxy     |
                                |  (:80, :443 TCP, :443 UDP)   |
                                +--------------+---------------+
                                               |
                     +-------------------------+-------------------------+
                     |                                                   |
                     v                                                   v
        [ 10 Static Web Handlers ]                          [ 31 Reverse Proxy / Redirect Blocks ]
        --------------------------                          --------------------------------------
        - mind.vrg.rocks    (/mind)    [Admin SSO]          - Edge Forward-Auth via Tinyauth (:3000)
        - fam.vrg.rocks     (/fam)     [SSO]                - Native OIDC via Tinyauth (auth.vrg.rocks)
        - scan.vrg.rocks    (/scan)    [Admin SSO]          - Unified LDAP via LLDAP (:3890 / :17170)
        - aysynbm.vrg.rocks (/aysynbm) [Admin SSO]          - Method/Path-Selective Edge Gates (send, ntfy)
        - tools.vrg.rocks   (/tools)   [SSO]                - External LAN Gateway (Router 192.168.50.1)
        - chef.vrg.rocks    (/chef)    [SSO]                - Compression (zstd/gzip) except Jellyfin streams
        - pdf.vrg.rocks     (/pdf)     [SSO]
        - speed.vrg.rocks   (/speed)   [SSO + POST /upload*]
        - draw.vrg.rocks    (/draw)    [SSO]
        - mi.vrg.rocks      (/mi)      [SSO]
```

### Container Healthcheck & Mount Configuration (`compose/core.yml`)

- **Ports:** `80:80`, `443:443`, `443:443/udp` (HTTP/3 QUIC).
- **Healthcheck:** `wget --no-verbose --tries=1 --spider http://127.0.0.1:2019/config/ || exit 1` (`interval: 30s`, `timeout: 5s`, `retries: 3`, `start_period: 10s`), querying Caddy's loopback Admin API on `127.0.0.1:2019`.
- **Volumes:**
  - `./Caddyfile:/etc/caddy/Caddyfile:ro`
  - `./data/caddy:/data` (persists ACME account keys and Let's Encrypt TLS certificates for all active `*.vrg.rocks` domains)
  - `./config/caddy:/config`
  - `./quartz/public:/mind:ro` and `./web/{fam,scan,aysynbm,tools,chef,pdf,speed,draw,mi}:/<mount>:ro`

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

# Text & Asset Compression
(optimize) {
	encode zstd gzip
}

# Baseline Security Headers
(security_headers) {
	header {
		X-Content-Type-Options nosniff
		X-Frame-Options SAMEORIGIN
		Referrer-Policy strict-origin-when-cross-origin
		Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
		Permissions-Policy "accelerometer=(), camera=(self), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()"
		X-Permitted-Cross-Domain-Policies none
		-Server
	}
}

# Forward-Auth Middleware (Provider-Agnostic: Tinyauth Active / Authentik Standby)
(forward_auth) {
	forward_auth tinyauth:3000 {
		uri /api/auth/caddy
		copy_headers Remote-User Remote-Name Remote-Email Remote-Groups Remote-Sub
		trusted_proxies private_ranges
	}
}

# Static Website Engine (Handles routing, clean URLs, compression & error fallbacks)
(static_site) {
	import optimize
	import security_headers
	@immutable path *.js *.css *.wasm *.woff *.woff2 *.svg *.png *.jpg *.jpeg *.webp *.avif *.ico
	header @immutable Cache-Control "public, max-age=604800, stale-while-revalidate=86400"
	route {
		try_files {path} {path}.html {path}/ =404
		file_server
	}
	handle_errors {
		@custom_err file /{err.status_code}.html
		handle @custom_err {
			rewrite * /{err.status_code}.html
			file_server
		}
		respond "{err.status_code} {err.status_text}" {err.status_code}
	}
}
```

### Static Site Directive Ordering & Error Handling

1. **Auth Before Filesystem Probing (`route` Block):** In Caddy v2's default directive order, `try_files` (`rewrite`) is sorted before `forward_auth`. Wrapping `try_files {path} {path}.html {path}/ =404` and `file_server` inside `route { ... }` places the entire block at the `route` priority slot, after `forward_auth`. Unauthenticated requests are rejected with `401`/`302` by `tinyauth:3000` before Caddy probes the filesystem, preventing path-existence leakage.
2. **Guarded Error Pages (`@custom_err`):** Only `/mind` (`quartz/public/404.html`) ships a custom error page. In `(static_site)`, `handle_errors` checks `@custom_err file /{err.status_code}.html` before rewriting, and falls back to `respond "{err.status_code} {err.status_text}" {err.status_code}` when no custom HTML file exists. This prevents missing `/401.html` or `/404.html` rewrites from collapsing into `HTTP 400`.
3. **Immutable Asset Caching (`@immutable`):** Static JS, CSS, WebAssembly (`.wasm`), font (`.woff`, `.woff2`), and image assets receive `Cache-Control: public, max-age=604800, stale-while-revalidate=86400` so large client-side bundles (such as CyberChef, BentoPDF, Excalidraw, IT-Tools, and MediaInfo `.wasm`) load from browser cache on repeat visits.

### Streaming Transport (`watch.vrg.rocks`, `jellyfin.vrg.rocks` & Standby `metal.vrg.rocks`)

Jellyfin streaming routes omit `import optimize` (preventing CPU compression overhead on H.264/HEVC/AV1 media streams) and configure 32 KiB HTTP proxy read/write buffers with 120-second keepalive connections:

```caddyfile
reverse_proxy http://jellyfin:8096 {
	transport http {
		read_buffer 32768
		write_buffer 32768
		keepalive 120s
	}
}
```

---

## 2. Master Reverse Proxy Routing Table

### 2.1 Active Dynamic & Redirect Routes (31 Site Blocks / 38 Hostnames)

| Subdomain / Hostname | Upstream Target | Compression | Auth Model / Edge Policy | Special Rules / Notes |
| :--- | :--- | :--- | :--- | :--- |
| **`auth.vrg.rocks`** | `http://tinyauth:3000` | `zstd/gzip` | Tinyauth v5.2.0 Native | Primary Google OAuth & OpenID Connect (OIDC) provider |
| **`login.vrg.rocks`**, **`tinyauth.vrg.rocks`** | *(Redirect)* | `zstd/gzip` | Public 301 Redirect | `redir https://auth.vrg.rocks{uri} permanent` |
| **`arcane.vrg.rocks`** | `http://arcane:3552` | `zstd/gzip` | Native OIDC (`tinyauth`) | Auto-redirects via `OIDC_AUTO_REDIRECT_TO_PROVIDER=true`, admin-only consent |
| **`router.vrg.rocks`** | `http://192.168.50.1` | `zstd/gzip` | Tinyauth Forward-Auth (Admin ACL) + Router Auth | Locked to `VRG` via `TINYAUTH_APPS_ROUTER_OAUTH_WHITELIST` |
| **`ldap.vrg.rocks`** | `http://lldap:17170` | `zstd/gzip` | Tinyauth Forward-Auth (Admin ACL) + LLDAP Auth | Locked to `VRG` via `TINYAUTH_APPS_LDAP_OAUTH_WHITELIST` |
| **`dash.vrg.rocks`** | `http://glance:8080` | `zstd/gzip` | Tinyauth Forward-Auth | Glance dashboard (`/sol`, `/stats`, `/radar`) |
| **`sol.vrg.rocks`** | *(Redirect)* | N/A | Public 302 Redirect | `import security_headers` + `redir https://dash.vrg.rocks/sol 302` |
| **`watch.vrg.rocks`**, **`jellyfin.vrg.rocks`** | `http://jellyfin:8096` | *(Bypassed)* | Jellyfin Native (`LDAP-Auth` + `SSO-Auth` OIDC) | 32 KiB read/write buffers, `keepalive 120s` |
| **`request.vrg.rocks`**, **`jellyseerr.vrg.rocks`**, **`seerr.vrg.rocks`** | `http://seerr:5055` | `zstd/gzip` | Tinyauth Forward-Auth + Jellyfin LDAP/Quick Connect | Unified Seerr media discovery and request portal |
| **`radarr.vrg.rocks`** | `http://radarr:7878` | `zstd/gzip` | Tinyauth Forward-Auth (Admin ACL) + `External` Auth | Locked to `VRG` via `TINYAUTH_APPS_RADARR_OAUTH_WHITELIST` |
| **`sonarr.vrg.rocks`** | `http://sonarr:8989` | `zstd/gzip` | Tinyauth Forward-Auth (Admin ACL) + `External` Auth | Locked to `VRG` via `TINYAUTH_APPS_SONARR_OAUTH_WHITELIST` |
| **`bazarr.vrg.rocks`** | `http://bazarr:6767` | `zstd/gzip` | Tinyauth Forward-Auth (Admin ACL) + `auth.type: null` | Locked to `VRG` via `TINYAUTH_APPS_BAZARR_OAUTH_WHITELIST` |
| **`lidarr.vrg.rocks`** | `http://lidarr:8686` | `zstd/gzip` | Tinyauth Forward-Auth (Admin ACL) + `External` Auth | Locked to `VRG` via `TINYAUTH_APPS_LIDARR_OAUTH_WHITELIST` |
| **`prowlarr.vrg.rocks`** | `http://prowlarr:9696` | `zstd/gzip` | Tinyauth Forward-Auth (Admin ACL) + `External` Auth | Locked to `VRG` via `TINYAUTH_APPS_PROWLARR_OAUTH_WHITELIST` |
| **`byparr.vrg.rocks`** | `http://byparr:8191` | `zstd/gzip` | Tinyauth Forward-Auth (Admin ACL) | Locked to `VRG` via `TINYAUTH_APPS_BYPARR_OAUTH_WHITELIST` |
| **`flaresolverr.vrg.rocks`** | *(Redirect)* | `zstd/gzip` | Public 301 Redirect | `redir https://byparr.vrg.rocks{uri} permanent` |
| **`qb.vrg.rocks`**, **`qbittorrent.vrg.rocks`** | `http://qbittorrent:8080` | `zstd/gzip` | qBittorrent Native Auth | Forward-auth omitted so Android mobile client connects without SSO redirects |
| **`qui.vrg.rocks`** | `http://qui:7476` | `zstd/gzip` | Tinyauth Forward-Auth (Admin ACL) + `QUI__AUTH_DISABLED` | Locked to `VRG` via `TINYAUTH_APPS_QUI_OAUTH_WHITELIST` |
| **`docs.vrg.rocks`**, **`paperless.vrg.rocks`** | `http://paperless-webserver:8000` | `zstd/gzip` | Native OIDC (`tinyauth`) | Auto-redirects via `PAPERLESS_REDIRECT_LOGIN_TO_SSO=true` |
| **`ignis.vrg.rocks`** | `http://ignis:8080` | `zstd/gzip` | Tinyauth Forward-Auth (Admin ACL) | Locked to `VRG` via `TINYAUTH_APPS_IGNIS_OAUTH_WHITELIST` |
| **`notes.vrg.rocks`** | *(Redirect)* | `zstd/gzip` | Public 301 Redirect | `redir https://ignis.vrg.rocks{uri} permanent` |
| **`links.vrg.rocks`** | `http://readeck:8000` | `zstd/gzip` | Native OIDC (`tinyauth`) | Forward-auth omitted so Readeck native OIDC and `/api/*` bearer tokens work |
| **`code.vrg.rocks`** | `http://code-server:8443` | `zstd/gzip` | Tinyauth Forward-Auth (Admin ACL) + `AUTH=none` | Locked to `VRG` via `TINYAUTH_APPS_CODE_OAUTH_WHITELIST` |
| **`coder.vrg.rocks`** | `http://coder:7080` | `zstd/gzip` | Native OIDC (`tinyauth`) | `redir /login /api/v2/users/oidc/callback 302`, admin-only consent |
| **`pb.vrg.rocks`** | `http://pocketbase:8090` | `zstd/gzip` | Tinyauth Forward-Auth (Admin ACL) | `@root path /` -> `redir @root /_/ 302` to PocketBase Admin UI |
| **`files.vrg.rocks`**, **`copyparty.vrg.rocks`** | `http://copyparty:3923` | `zstd/gzip` | Tinyauth Forward-Auth + `Remote-Email` Header Auth | Maps `Remote-Email` via `idp-hm-usr` in `copyparty.conf` |
| **`ntfy.vrg.rocks`** | `http://ntfy:80` | `zstd/gzip` | Selective Forward-Auth on `@pub` | Unauthenticated external `POST`/`PUT` gated by `forward_auth`, subscriptions and `Authorization` tokens pass directly |
| **`inv.vrg.rocks`** | `http://homebox:7745` | `zstd/gzip` | Native OIDC (`tinyauth`) | Active route with strict CORS for `https://scan.vrg.rocks` |
| **`backrest.vrg.rocks`** | `http://backrest:9898` | `zstd/gzip` | Tinyauth Forward-Auth (Admin ACL) + `auth.disabled` | Locked to `VRG` via `TINYAUTH_APPS_BACKREST_OAUTH_WHITELIST` |
| **`send.vrg.rocks`** | `http://enclosed:8787` | `zstd/gzip` | Selective Forward-Auth on `@create_note` | `max_size 60MB`, `/` and `/api/notes[/]` gated by `forward_auth`, `/@*` and `/api/notes/*` public for recipients |
| **`fly.vrg.rocks`** | `http://airtrail:3000` | `zstd/gzip` | Native OIDC (`tinyauth`) | Auto-redirects via `OAUTH_AUTO_LOGIN=true` |

### 2.2 Active Zero-Container Static Web Applications (10 Site Blocks / 10 Hostnames)

All 10 static web applications are served directly by Caddy's `file_server` using the `(static_site)` snippet and consume `0 MiB` of additional container memory.

| Subdomain / Hostname | Container Root Mount | Host Source Path | Edge ACL Policy | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **`mind.vrg.rocks`** | `/mind` | `./quartz/public` | Admin-only (`TINYAUTH_APPS_MIND_OAUTH_WHITELIST`) | Quartz 4 PKM Digital Garden (`404.html` custom fallback) |
| **`fam.vrg.rocks`** | `/fam` | `./web/fam` | Allowlisted users (`import forward_auth`) | Family Data Vault (`vault.enc` AES-GCM client-side bundle) |
| **`scan.vrg.rocks`** | `/scan` | `./web/scan` | Admin-only (`TINYAUTH_APPS_SCAN_OAUTH_WHITELIST`) | Homebox Mobile Barcode Scanner PWA (`camera=(self)` permitted) |
| **`aysynbm.vrg.rocks`** | `/aysynbm` | `./web/aysynbm` | Admin-only (`TINYAUTH_APPS_AYSYNBM_OAUTH_WHITELIST`) | Async Bookmark Manager static PWA |
| **`tools.vrg.rocks`** | `/tools` | `./web/tools` | Allowlisted users (`import forward_auth`) | IT-Tools developer utilities suite (80+ client-side tools) |
| **`chef.vrg.rocks`** | `/chef` | `./web/chef` | Allowlisted users (`import forward_auth`) | GCHQ CyberChef data & crypto toolkit (`v10.19.4`) |
| **`pdf.vrg.rocks`** | `/pdf` | `./web/pdf` | Allowlisted users (`import forward_auth`) | BentoPDF client-side WebAssembly PDF suite (50+ tools) |
| **`speed.vrg.rocks`** | `/speed` | `./web/speed` | Allowlisted users (`import forward_auth`) | OpenSpeedTest HTML5 LAN/Wi-Fi 6 benchmark (`max_size 500MB`, `route @upload { respond 200 }`, `no-store` on `/downloading*` and `/upload*`) |
| **`draw.vrg.rocks`** | `/draw` | `./web/draw` | Allowlisted users (`import forward_auth`) | Excalidraw client-side whiteboard |
| **`mi.vrg.rocks`** | `/mi` | `./web/mi` | Allowlisted users (`import forward_auth`) | Sol MediaInfo WebAssembly 4K HDR / Dolby Vision / Atmos bitstream inspector |

### 2.3 Standby Routes (12 Commented Vhost Blocks / 13 Hostnames)

Each vhost below is commented out in `Caddyfile`. Uncomment it only after starting the corresponding `--profile standby` container or native macOS daemon.

| Subdomain / Hostname | Upstream Target | Compression | Auth Model / Edge Policy | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **`status.vrg.rocks`** *(Standby)* | `http://gatus:8080` | `zstd/gzip` | `import forward_auth` | Gatus status page (`compose/monitoring.yml`) |
| **`beszel.vrg.rocks`** *(Standby)* | `http://beszel:8090` | `zstd/gzip` | `import forward_auth` | Beszel metrics hub (`compose/monitoring.yml`) |
| **`dozzle.vrg.rocks`** *(Standby)* | `http://dozzle:8080` | `zstd/gzip` | `import forward_auth` | Dozzle container log viewer (`compose/monitoring.yml`) |
| **`metal.vrg.rocks`** *(Standby)* | `http://host.docker.internal:8097` | *(Bypassed)* | Jellyfin Native Auth | Native macOS Jellyfin Metal VideoToolbox instance (`scripts/setup_jellyfin_metal.py`) |
| **`wizarr.vrg.rocks`** *(Standby)* | `http://wizarr:5690` | `zstd/gzip` | `import forward_auth` | Wizarr invitation portal (`compose/media.yml`) |
| **`cs.vrg.rocks`** *(Standby)* | `http://cross-seed:2468` | `zstd/gzip` | `import forward_auth` + `TINYAUTH_APPS_CS_OAUTH_WHITELIST` | Reserved route if Cross-Seed is re-enabled |
| **`paperless-ai.vrg.rocks`** *(Standby)* | `http://paperless-ai:3000` | `zstd/gzip` | `import forward_auth` | Paperless-AI classifier (`compose/paperless.yml`) |
| **`leaf.vrg.rocks`** *(Standby)* | `http://leafwiki:8080` | `zstd/gzip` | `import forward_auth` | LeafWiki markdown wiki (`compose/knowledge.yml`) |
| **`kavita.vrg.rocks`** *(Standby)* | `http://kavita:5000` | `zstd/gzip` | `import forward_auth` | Kavita book/manga reader (`compose/knowledge.yml`) |
| **`home.vrg.rocks`** *(Standby)* | `http://host.docker.internal:8123` | `zstd/gzip` | `import forward_auth` | Home Assistant (`compose/utilities.yml`, `network_mode: host`) |
| **`vault.vrg.rocks`**, **`pass.vrg.rocks`** *(Standby)* | `http://vaultwarden:80` | `zstd/gzip` | `import forward_auth` | Vaultwarden password vault (`compose/utilities.yml`) |
| **`n8n.vrg.rocks`** *(Standby)* | `http://n8n:5678` | `zstd/gzip` | `import forward_auth` | n8n workflow automation (`compose/utilities.yml`) |

---

## 3. Selective Route Handlers (`speed`, `send`, `ntfy`, `inv`, `pb`)

### 3.1 `speed.vrg.rocks` (OpenSpeedTest Upload & No-Store Stream Rules)

Caddy's static `file_server` returns `HTTP 405 Method Not Allowed` on `POST` requests. To support OpenSpeedTest's HTML5 upload throughput test (`POST /upload*`) and prevent browser/proxy caching of benchmark payloads:

```caddyfile
speed.vrg.rocks {
	import forward_auth
	root * /speed
	request_body {
		max_size 500MB
	}
	@speed_streams path /downloading* /upload*
	header @speed_streams Cache-Control "no-store, no-cache, must-revalidate, max-age=0"
	@upload {
		method POST
		path /upload*
	}
	route @upload {
		respond 200
	}
	import static_site
}
```

### 3.2 `send.vrg.rocks` (Enclosed Zero-Knowledge E2EE Note Creation Gate)

Creating encrypted notes or file drops (`/` and `/api/notes[/]`) is gated behind `import forward_auth` (with a 60 MB request body cap covering base64-encoded 50 MB encrypted attachments), while recipient links (`/@*` and `/api/notes/<id>`) remain public so external recipients can decrypt shared links in their browser without a Sol account:

```caddyfile
send.vrg.rocks {
	import optimize
	import security_headers
	request_body {
		max_size 60MB
	}
	@create_note {
		path / /api/notes /api/notes/
	}
	handle @create_note {
		import forward_auth
		reverse_proxy http://enclosed:8787
	}
	handle {
		reverse_proxy http://enclosed:8787
	}
}
```

### 3.3 `ntfy.vrg.rocks` (External Unauthenticated Publish Gate)

Internal containers (`paperless-webserver`, `radarr`, `sonarr`, `backrest`) publish to `http://ntfy:80` over the internal `sol_default` bridge network. At the public `ntfy.vrg.rocks` ingress edge, unauthenticated `POST`/`PUT` requests without an `Authorization` header are gated by `import forward_auth`, while mobile app topic subscriptions (`GET`/WebSocket) and token-authenticated publishes pass directly to `ntfy:80`:

```caddyfile
ntfy.vrg.rocks {
	import optimize
	import security_headers
	@pub {
		method POST PUT
		not header Authorization *
	}
	handle @pub {
		import forward_auth
		reverse_proxy http://ntfy:80
	}
	handle {
		reverse_proxy http://ntfy:80
	}
}
```

### 3.4 `inv.vrg.rocks` (Homebox CORS Policy for `scan.vrg.rocks`)

`inv.vrg.rocks` is active and protected by Homebox's native OIDC (`HBOX_OIDC_AUTO_REDIRECT=true`). Its CORS rules permit credentialed cross-origin requests exclusively from the `https://scan.vrg.rocks` barcode scanner PWA:

```caddyfile
inv.vrg.rocks {
	import optimize
	import security_headers

	@allowed_origins header Origin https://scan.vrg.rocks
	header @allowed_origins {
		Access-Control-Allow-Origin "https://scan.vrg.rocks"
		Access-Control-Allow-Methods "GET, POST, OPTIONS, PUT, DELETE"
		Access-Control-Allow-Headers "Origin, Content-Type, Authorization, Accept"
		Access-Control-Allow-Credentials true
		Vary Origin
	}

	@options {
		method OPTIONS
		header Origin https://scan.vrg.rocks
	}
	respond @options 204

	reverse_proxy http://homebox:7745
}
```

---

## 4. Network Topology & Cross-Container Communication

```
  +-------------------------------------------------------------------------------+
  | HOST SYSTEM (macOS M1 Pro / OrbStack Bridge Gateway: host.docker.internal)    |
  |                                                                               |
  |   Physical Ports Exposed to LAN/WAN:                                          |
  |   - :80, :443 TCP/UDP (Caddy v2.11.7 Reverse Proxy & Static Web Server)       |
  |   - :42069 TCP/UDP (qBittorrent WAN BitTorrent Wire Protocol)                 |
  |                                                                               |
  |   Loopback-Only Host Ports (127.0.0.1):                                       |
  |   - :53682 (rclone OAuth callback, ops profile only)                          |
  |                                                                               |
  |   Standby Native macOS / Host Processes:                                      |
  |   - Jellyfin Metal :8097 (standby, VideoToolbox)                              |
  |   - Home Assistant :8123 (standby, network_mode: host)                        |
  |   - Beszel Agent :45876 (standby, network_mode: host)                         |
  |                                                                               |
  |   +-----------------------------------------------------------------------+   |
  |   | DOCKER COMPOSE BRIDGE NETWORK ('sol_default' - 29 Active Containers)  |   |
  |   |                                                                       |   |
  |   |  - Caddy (:80/:443) <--------------> Tinyauth v5.2.0 (:3000)          |   |
  |   |                                          |                            |   |
  |   |                                          +--> LLDAP (:3890 / :17170)  |   |
  |   |                                                                       |   |
  |   |  - Prowlarr (:9696) <--------------> Byparr (:8191)                   |   |
  |   |        |                              (network alias: flaresolverr)   |   |
  |   |        v                                                              |   |
  |   |    qBittorrent (:8080) <-----------> QUI v1.32.0 (:7476)              |   |
  |   |        ^                                                              |   |
  |   |        | (Option A ExFAT Symlinks + Internal Hardlinks)               |   |
  |   |    Radarr (:7878) / Sonarr (:8989) / Lidarr (:8686) / Bazarr (:6767)  |   |
  |   |        ^                                                              |   |
  |   |        | (Media Requests)                                             |   |
  |   |    Seerr (:5055) [DNS: 8.8.8.8, 1.1.1.1] (alias: jellyseerr)          |   |
  |   |        |                                                              |   |
  |   |        v (Library Sync & LDAP Auth)                                   |   |
  |   |    Jellyfin (:8096) <--------------> LLDAP (:3890)                    |   |
  |   |                                                                       |   |
  |   |  - Paperless-Webserver (:8000)                                        |   |
  |   |        |----------> Paperless-Broker (Redis 8 Alpine :6379, 256mb)    |   |
  |   |        |----------> Paperless-DB (PostgreSQL 17 Alpine :5432)         |   |
  |   |        |----------> ntfy (:80) [Internal Webhook Notifications]       |   |
  |   |                                                                       |   |
  |   |  - AirTrail (:3000) --------------> AirTrail-DB (PG 17 Alpine :5432)  |   |
  |   |  - Glance (:8080), Arcane (:3552), Ignis (:8080), Readeck (:8000)     |   |
  |   |  - code-server (:8443), Coder (:7080), PocketBase (:8090)             |   |
  |   |  - Copyparty (:3923), Homebox (:7745), Backrest (:9898), Enclosed     |   |
  |   +-----------------------------------------------------------------------+   |
  +-------------------------------------------------------------------------------+
```

### DNS & Upstream Resolution

1. **OrbStack Host Access (`host.docker.internal`):** Allows Caddy and Coder workspaces to reach host-bound services (`8097` for standby Jellyfin Metal and `8123` for standby Home Assistant) without hardcoding LAN IPs.
2. **ISP DNS Filtering Bypass:**
   - `seerr` overrides Docker DNS with Google (`8.8.8.8`) and Cloudflare (`1.1.1.1`).
   - `radarr`, `sonarr`, `bazarr`, `lidarr`, `prowlarr`, `byparr`, and `qbittorrent` override DNS with Cloudflare (`1.1.1.1`) and Quad9 (`9.9.9.9`) to bypass ISP tracker/TMDb filtering.
3. **Docker Network Aliases:**
   - `byparr` registers the network alias `flaresolverr` on `sol_default`, allowing Prowlarr's IndexerProxy (`http://flaresolverr:8191`, 90s timeout) to route directly to Byparr.
   - `seerr` registers the network alias `jellyseerr` for backward compatibility.
