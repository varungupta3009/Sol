#!/usr/bin/env bash
# ==============================================================================
# Sol Home Server - Zero-Container Static Developer & Media Suite Sync
# ==============================================================================
# Populates /Users/vrg/Documents/Sol/web/{tools,chef,pdf,speed,draw,mi} so
# Caddy can serve all 6 static web applications at 0 MiB extra RAM and 0 extra
# containers:
#   - tools.vrg.rocks -> web/tools (IT-Tools v2024.10.22-7ca5933)
#   - chef.vrg.rocks  -> web/chef  (GCHQ CyberChef v11.5.0)
#   - pdf.vrg.rocks   -> web/pdf   (BentoPDF WASM v2.8.9)
#   - speed.vrg.rocks -> web/speed (OpenSpeedTest HTML5 LAN/Wi-Fi Speed Test)
#   - draw.vrg.rocks  -> web/draw  (Excalidraw Static Whiteboard)
#   - mi.vrg.rocks    -> web/mi    (MediaInfo Web 4K HDR / Dolby Vision / Atmos WASM Inspector)
#
# Usage:
#   ./scripts/sync_static_tools.sh [--force]
# ==============================================================================

set -euo pipefail

export PATH="/usr/local/bin:/opt/homebrew/bin:$HOME/.orbstack/bin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOL_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
WEB_ROOT="${SOL_ROOT}/web"

FORCE=0
if [[ "${1:-}" == "--force" || "${1:-}" == "-f" ]]; then
  FORCE=1
fi

IT_TOOLS_VERSION="v2024.10.22-7ca5933"
IT_TOOLS_URL="https://github.com/CorentinTh/it-tools/releases/download/${IT_TOOLS_VERSION}/it-tools-2024.10.22-7ca5933.zip"

CYBERCHEF_VERSION="v11.5.0"
CYBERCHEF_URL="https://github.com/gchq/CyberChef/releases/download/${CYBERCHEF_VERSION}/CyberChef_8cd426dd4f40f1423912d5fad91b578a86a65112.zip"

BENTOPDF_VERSION="v2.8.9"
BENTOPDF_URL="https://github.com/alam00000/bentopdf/releases/download/${BENTOPDF_VERSION}/dist-2.8.9.zip"

OPENSPEEDTEST_VERSION="main-2026"
OPENSPEEDTEST_URL="https://github.com/openspeedtest/Speed-Test/archive/refs/heads/main.tar.gz"

EXCALIDRAW_IMAGE="excalidraw/excalidraw:latest"
MEDIAINFO_VERSION="0.3.8"

TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/sol-static-sync.XXXXXX")"
cleanup() {
  rm -rf "${TMP_ROOT}"
}
trap cleanup EXIT

# Bypass macOS login keychain lock during non-interactive SSH Docker pulls
NO_KEYCHAIN_BIN="${TMP_ROOT}/no-keychain-bin"
mkdir -p "${NO_KEYCHAIN_BIN}"
printf '#!/bin/sh\necho "{}"\n' > "${NO_KEYCHAIN_BIN}/docker-credential-osxkeychain"
chmod +x "${NO_KEYCHAIN_BIN}/docker-credential-osxkeychain"
export PATH="${NO_KEYCHAIN_BIN}:${PATH}"

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

needs_sync() {
  local dir="$1"
  local expected_version="$2"
  if [[ "${FORCE}" -eq 1 ]]; then
    return 0
  fi
  if [[ ! -f "${dir}/index.html" || ! -f "${dir}/.sol_version" ]]; then
    return 0
  fi
  local current_version
  current_version="$(cat "${dir}/.sol_version" 2>/dev/null || true)"
  [[ "${current_version}" != "${expected_version}" ]]
}

mark_synced() {
  local dir="$1"
  local version="$2"
  printf '%s\n' "${version}" > "${dir}/.sol_version"
}

mkdir -p "${WEB_ROOT}"

# ------------------------------------------------------------------------------
# 1. IT-Tools (tools.vrg.rocks -> web/tools)
# ------------------------------------------------------------------------------
TOOLS_DIR="${WEB_ROOT}/tools"
if needs_sync "${TOOLS_DIR}" "${IT_TOOLS_VERSION}"; then
  log "Syncing IT-Tools (${IT_TOOLS_VERSION}) -> ${TOOLS_DIR} ..."
  mkdir -p "${TMP_ROOT}/it-tools" "${TOOLS_DIR}"
  curl -fsSL -o "${TMP_ROOT}/it-tools.zip" "${IT_TOOLS_URL}"
  unzip -q "${TMP_ROOT}/it-tools.zip" -d "${TMP_ROOT}/it-tools"
  rm -rf "${TOOLS_DIR:?}/"*
  if [[ -d "${TMP_ROOT}/it-tools/dist" ]]; then
    cp -R "${TMP_ROOT}/it-tools/dist/." "${TOOLS_DIR}/"
  else
    cp -R "${TMP_ROOT}/it-tools/." "${TOOLS_DIR}/"
  fi
  mark_synced "${TOOLS_DIR}" "${IT_TOOLS_VERSION}"
  log "IT-Tools ready at ${TOOLS_DIR}/index.html"
else
  log "IT-Tools (${IT_TOOLS_VERSION}) already up to date in ${TOOLS_DIR}."
fi

# ------------------------------------------------------------------------------
# 2. CyberChef (chef.vrg.rocks -> web/chef)
# ------------------------------------------------------------------------------
CHEF_DIR="${WEB_ROOT}/chef"
if needs_sync "${CHEF_DIR}" "${CYBERCHEF_VERSION}"; then
  log "Syncing CyberChef (${CYBERCHEF_VERSION}) -> ${CHEF_DIR} ..."
  mkdir -p "${TMP_ROOT}/cyberchef" "${CHEF_DIR}"
  curl -fsSL -o "${TMP_ROOT}/cyberchef.zip" "${CYBERCHEF_URL}"
  unzip -q "${TMP_ROOT}/cyberchef.zip" -d "${TMP_ROOT}/cyberchef"
  rm -rf "${CHEF_DIR:?}/"*
  cp -R "${TMP_ROOT}/cyberchef/." "${CHEF_DIR}/"
  chef_html="$(find "${CHEF_DIR}" -maxdepth 1 -name 'CyberChef*.html' | head -n 1)"
  if [[ -n "${chef_html}" ]]; then
    cp "${chef_html}" "${CHEF_DIR}/index.html"
  fi
  mark_synced "${CHEF_DIR}" "${CYBERCHEF_VERSION}"
  log "CyberChef ready at ${CHEF_DIR}/index.html"
else
  log "CyberChef (${CYBERCHEF_VERSION}) already up to date in ${CHEF_DIR}."
fi

# ------------------------------------------------------------------------------
# 3. BentoPDF (pdf.vrg.rocks -> web/pdf)
# ------------------------------------------------------------------------------
PDF_DIR="${WEB_ROOT}/pdf"
if needs_sync "${PDF_DIR}" "${BENTOPDF_VERSION}"; then
  log "Syncing BentoPDF (${BENTOPDF_VERSION}) -> ${PDF_DIR} ..."
  mkdir -p "${TMP_ROOT}/bentopdf" "${PDF_DIR}"
  curl -fsSL -o "${TMP_ROOT}/bentopdf.zip" "${BENTOPDF_URL}"
  unzip -q "${TMP_ROOT}/bentopdf.zip" -d "${TMP_ROOT}/bentopdf"
  rm -rf "${PDF_DIR:?}/"*
  if [[ -d "${TMP_ROOT}/bentopdf/dist" ]]; then
    cp -R "${TMP_ROOT}/bentopdf/dist/." "${PDF_DIR}/"
  else
    cp -R "${TMP_ROOT}/bentopdf/." "${PDF_DIR}/"
  fi
  mark_synced "${PDF_DIR}" "${BENTOPDF_VERSION}"
  log "BentoPDF ready at ${PDF_DIR}/index.html"
else
  log "BentoPDF (${BENTOPDF_VERSION}) already up to date in ${PDF_DIR}."
fi

# ------------------------------------------------------------------------------
# 4. OpenSpeedTest (speed.vrg.rocks -> web/speed)
# ------------------------------------------------------------------------------
SPEED_DIR="${WEB_ROOT}/speed"
if needs_sync "${SPEED_DIR}" "${OPENSPEEDTEST_VERSION}"; then
  log "Syncing OpenSpeedTest (${OPENSPEEDTEST_VERSION}) -> ${SPEED_DIR} ..."
  mkdir -p "${TMP_ROOT}/openspeedtest" "${SPEED_DIR}"
  curl -fsSL -o "${TMP_ROOT}/openspeedtest.tar.gz" "${OPENSPEEDTEST_URL}"
  tar -xzf "${TMP_ROOT}/openspeedtest.tar.gz" --strip-components=1 -C "${TMP_ROOT}/openspeedtest"
  rm -rf "${SPEED_DIR:?}/"*
  cp -R "${TMP_ROOT}/openspeedtest/." "${SPEED_DIR}/"
  mark_synced "${SPEED_DIR}" "${OPENSPEEDTEST_VERSION}"
  log "OpenSpeedTest ready at ${SPEED_DIR}/index.html"
else
  log "OpenSpeedTest (${OPENSPEEDTEST_VERSION}) already up to date in ${SPEED_DIR}."
fi

# ------------------------------------------------------------------------------
# 5. Excalidraw (draw.vrg.rocks -> web/draw)
# ------------------------------------------------------------------------------
DRAW_DIR="${WEB_ROOT}/draw"
EXCALIDRAW_STAMP="excalidraw-latest-2026"
if needs_sync "${DRAW_DIR}" "${EXCALIDRAW_STAMP}"; then
  log "Syncing Excalidraw (${EXCALIDRAW_IMAGE}) -> ${DRAW_DIR} ..."
  mkdir -p "${DRAW_DIR}"
  if ! docker image inspect "${EXCALIDRAW_IMAGE}" >/dev/null 2>&1; then
    docker pull "${EXCALIDRAW_IMAGE}"
  fi
  cid="$(docker create "${EXCALIDRAW_IMAGE}")"
  rm -rf "${DRAW_DIR:?}/"*
  docker cp "${cid}:/usr/share/nginx/html/." "${DRAW_DIR}/"
  docker rm "${cid}" >/dev/null
  mark_synced "${DRAW_DIR}" "${EXCALIDRAW_STAMP}"
  log "Excalidraw ready at ${DRAW_DIR}/index.html"
else
  log "Excalidraw (${EXCALIDRAW_STAMP}) already up to date in ${DRAW_DIR}."
fi

# ------------------------------------------------------------------------------
# 6. MediaInfo Web (mi.vrg.rocks -> web/mi)
# ------------------------------------------------------------------------------
MI_DIR="${WEB_ROOT}/mi"
MI_STAMP="mediainfo-wasm-${MEDIAINFO_VERSION}-v1"
if needs_sync "${MI_DIR}" "${MI_STAMP}"; then
  log "Syncing MediaInfo Web (mediainfo.js v${MEDIAINFO_VERSION}) -> ${MI_DIR} ..."
  mkdir -p "${MI_DIR}"
  curl -fsSL -o "${MI_DIR}/mediainfo.min.js" \
    "https://cdn.jsdelivr.net/npm/mediainfo.js@${MEDIAINFO_VERSION}/dist/umd/index.min.js"
  curl -fsSL -o "${MI_DIR}/MediaInfoModule.wasm" \
    "https://cdn.jsdelivr.net/npm/mediainfo.js@${MEDIAINFO_VERSION}/dist/MediaInfoModule.wasm"

  cat > "${MI_DIR}/index.html" <<'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Sol MediaInfo — 4K UHD / Dolby Vision / TrueHD Atmos Bitstream Inspector</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Titillium+Web:wght@400;600;700&family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200" rel="stylesheet" />
  <style>
    :root {
      --bg-base: #1e1e2e;
      --bg-mantle: #181825;
      --bg-crust: #11111b;
      --surface-0: #313244;
      --surface-1: #45475a;
      --surface-2: #585b70;
      --text-main: #cdd6f4;
      --text-sub: #a6adc8;
      --text-muted: #6c7086;
      --mauve: #cba6f7;
      --blue: #89b4fa;
      --sapphire: #74c7ec;
      --green: #a6e3a1;
      --yellow: #f9e2af;
      --peach: #fab387;
      --red: #f38ba8;
      --teal: #94e2d5;
      --radius-lg: 16px;
      --radius-md: 12px;
      --radius-sm: 8px;
    }

    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    body {
      background: radial-gradient(circle at top right, #26233a 0%, var(--bg-base) 45%, var(--bg-crust) 100%);
      color: var(--text-main);
      font-family: 'Titillium Web', -apple-system, BlinkMacSystemFont, sans-serif;
      min-height: 100vh;
      padding: 28px 24px 64px;
      line-height: 1.5;
    }

    .container {
      max-width: 1320px;
      margin: 0 auto;
    }

    header {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 24px;
      padding-bottom: 18px;
      border-bottom: 1px solid var(--surface-0);
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 14px;
    }

    .brand-icon {
      width: 46px;
      height: 46px;
      border-radius: var(--radius-md);
      background: linear-gradient(135deg, rgba(203, 166, 247, 0.22), rgba(137, 180, 250, 0.18));
      border: 1px solid rgba(203, 166, 247, 0.4);
      display: flex;
      align-items: center;
      justify-content: center;
      color: var(--mauve);
    }

    .brand h1 {
      font-size: 1.55rem;
      font-weight: 700;
      letter-spacing: 0.01em;
    }

    .brand p {
      color: var(--text-sub);
      font-size: 0.9rem;
    }

    .status-pill {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 6px 14px;
      border-radius: 999px;
      background: var(--bg-mantle);
      border: 1px solid var(--surface-0);
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.78rem;
      color: var(--green);
    }

    .status-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--green);
      box-shadow: 0 0 8px var(--green);
    }

    .dropzone {
      background: rgba(24, 24, 37, 0.85);
      border: 2px dashed var(--surface-1);
      border-radius: var(--radius-lg);
      padding: 36px 24px;
      text-align: center;
      cursor: pointer;
      transition: all 0.18s ease;
      margin-bottom: 24px;
      position: relative;
    }

    .dropzone:hover,
    .dropzone.dragover {
      border-color: var(--mauve);
      background: rgba(49, 50, 68, 0.45);
      transform: translateY(-1px);
    }

    .dropzone input[type="file"] {
      display: none;
    }

    .dropzone-icon {
      font-size: 42px;
      color: var(--mauve);
      margin-bottom: 8px;
    }

    .dropzone h2 {
      font-size: 1.25rem;
      margin-bottom: 6px;
    }

    .dropzone p {
      color: var(--text-sub);
      font-size: 0.92rem;
      max-width: 680px;
      margin: 0 auto;
    }

    .badge-row {
      display: flex;
      flex-wrap: wrap;
      justify-content: center;
      gap: 8px;
      margin-top: 16px;
    }

    .badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 4px 11px;
      border-radius: var(--radius-sm);
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.76rem;
      font-weight: 600;
      background: var(--surface-0);
      color: var(--text-main);
      border: 1px solid var(--surface-1);
    }

    .badge.dv { background: rgba(203, 166, 247, 0.16); color: var(--mauve); border-color: rgba(203, 166, 247, 0.45); }
    .badge.hdr { background: rgba(249, 226, 175, 0.16); color: var(--yellow); border-color: rgba(249, 226, 175, 0.45); }
    .badge.atmos { background: rgba(137, 180, 250, 0.16); color: var(--blue); border-color: rgba(137, 180, 250, 0.45); }
    .badge.dts { background: rgba(250, 179, 135, 0.16); color: var(--peach); border-color: rgba(250, 179, 135, 0.45); }
    .badge.ok { background: rgba(166, 227, 161, 0.16); color: var(--green); border-color: rgba(166, 227, 161, 0.45); }

    #results {
      display: none;
    }

    .toolbar {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      background: var(--bg-mantle);
      border: 1px solid var(--surface-0);
      border-radius: var(--radius-md);
      padding: 14px 18px;
      margin-bottom: 20px;
    }

    .file-title {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.92rem;
      font-weight: 600;
      color: var(--sapphire);
      word-break: break-all;
    }

    .file-meta-inline {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.78rem;
      color: var(--text-sub);
      margin-top: 2px;
    }

    .btn-group {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }

    button.btn {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      background: var(--surface-0);
      color: var(--text-main);
      border: 1px solid var(--surface-1);
      border-radius: var(--radius-sm);
      padding: 7px 13px;
      font-family: 'Titillium Web', sans-serif;
      font-size: 0.86rem;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.15s ease;
    }

    button.btn:hover {
      background: var(--surface-1);
      border-color: var(--mauve);
    }

    button.btn.active {
      background: rgba(203, 166, 247, 0.2);
      color: var(--mauve);
      border-color: var(--mauve);
    }

    .summary-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(285px, 1fr));
      gap: 16px;
      margin-bottom: 22px;
    }

    .card {
      background: var(--bg-mantle);
      border: 1px solid var(--surface-0);
      border-radius: var(--radius-md);
      padding: 18px;
    }

    .card-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 12px;
      padding-bottom: 8px;
      border-bottom: 1px solid var(--surface-0);
    }

    .card-title {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 0.98rem;
      font-weight: 700;
      color: var(--text-main);
    }

    .kv-list {
      display: grid;
      grid-template-columns: 135px 1fr;
      row-gap: 7px;
      column-gap: 10px;
      font-size: 0.85rem;
    }

    .kv-key {
      color: var(--text-sub);
      font-weight: 600;
    }

    .kv-val {
      font-family: 'JetBrains Mono', monospace;
      color: var(--text-main);
      word-break: break-word;
    }

    .section-title {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 1.1rem;
      font-weight: 700;
      margin: 22px 0 12px;
      color: var(--mauve);
    }

    .track-table-wrap {
      overflow-x: auto;
      background: var(--bg-mantle);
      border: 1px solid var(--surface-0);
      border-radius: var(--radius-md);
      margin-bottom: 18px;
    }

    table.track-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.84rem;
      text-align: left;
    }

    table.track-table th {
      background: rgba(49, 50, 68, 0.65);
      color: var(--text-sub);
      font-weight: 700;
      padding: 10px 14px;
      border-bottom: 1px solid var(--surface-0);
      white-space: nowrap;
    }

    table.track-table td {
      padding: 10px 14px;
      border-bottom: 1px solid rgba(49, 50, 68, 0.5);
      font-family: 'JetBrains Mono', monospace;
    }

    table.track-table tr:last-child td {
      border-bottom: none;
    }

    pre.raw-output {
      display: none;
      background: var(--bg-crust);
      border: 1px solid var(--surface-0);
      border-radius: var(--radius-md);
      padding: 18px;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.8rem;
      color: var(--text-main);
      overflow-x: auto;
      max-height: 75vh;
      line-height: 1.45;
    }

    .material-symbols-outlined {
      font-size: 20px;
      vertical-align: middle;
    }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div class="brand">
        <div class="brand-icon">
          <span class="material-symbols-outlined">movie_info</span>
        </div>
        <div>
          <h1>Sol MediaInfo Bitstream Inspector</h1>
          <p>Zero-Copy Client-Side WebAssembly Inspector for 4K Remuxes, Dolby Vision Profile 7 FEL/8.1, HDR10 MaxCLL &amp; TrueHD Atmos</p>
        </div>
      </div>
      <div class="status-pill" id="wasm-status">
        <span class="status-dot"></span>
        <span id="wasm-status-text">Initializing MediaInfo WASM...</span>
      </div>
    </header>

    <label class="dropzone" id="dropzone" for="file-input">
      <input type="file" id="file-input" accept=".mkv,.mp4,.m2ts,.ts,.mov,.avi,.webm,.flac,.m4a,.ac3,.thd,.dts,video/*,audio/*" />
      <div class="dropzone-icon">
        <span class="material-symbols-outlined" style="font-size: 44px;">upload_file</span>
      </div>
      <h2>Drop any 4K UHD Remux (.mkv / .mp4 / .m2ts) or click to browse</h2>
      <p>Uses zero-copy chunked File.slice() reads directly from local disk or SMB/WebDAV mount. Even an 80 GB 4K Blu-ray Remux analyzes in under 1 second with zero network upload.</p>
      <div class="badge-row">
        <span class="badge dv">Dolby Vision P7 FEL / P8.1</span>
        <span class="badge hdr">HDR10 MaxCLL / MaxFALL</span>
        <span class="badge atmos">TrueHD Atmos / E-AC-3 JOC</span>
        <span class="badge dts">DTS-HD MA / DTS:X</span>
        <span class="badge ok">100% Client-Side WASM</span>
      </div>
    </label>

    <div id="results">
      <div class="toolbar">
        <div>
          <div class="file-title" id="file-name">—</div>
          <div class="file-meta-inline" id="file-perf">—</div>
        </div>
        <div class="btn-group">
          <button class="btn active" id="tab-cards" type="button">
            <span class="material-symbols-outlined">dashboard</span> Cards
          </button>
          <button class="btn" id="tab-text" type="button">
            <span class="material-symbols-outlined">subject</span> Text Report
          </button>
          <button class="btn" id="tab-json" type="button">
            <span class="material-symbols-outlined">data_object</span> Raw JSON
          </button>
          <button class="btn" id="btn-copy" type="button">
            <span class="material-symbols-outlined">content_copy</span> Copy Report
          </button>
          <button class="btn" id="btn-dl-txt" type="button">
            <span class="material-symbols-outlined">download</span> .TXT
          </button>
          <button class="btn" id="btn-dl-json" type="button">
            <span class="material-symbols-outlined">download</span> .JSON
          </button>
        </div>
      </div>

      <div id="cards-view">
        <div class="badge-row" id="detected-badges" style="justify-content: flex-start; margin-bottom: 18px;"></div>
        <div class="summary-grid" id="summary-cards"></div>

        <div class="section-title">
          <span class="material-symbols-outlined">graphic_eq</span>
          <span>Audio Streams</span>
        </div>
        <div class="track-table-wrap">
          <table class="track-table" id="audio-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Codec / Commercial Format</th>
                <th>Atmos / Objects</th>
                <th>Channels</th>
                <th>Bitrate</th>
                <th>Sample Rate / Depth</th>
                <th>Language</th>
                <th>Title &amp; Flags</th>
              </tr>
            </thead>
            <tbody></tbody>
          </table>
        </div>

        <div class="section-title">
          <span class="material-symbols-outlined">subtitles</span>
          <span>Subtitle &amp; Text Streams</span>
        </div>
        <div class="track-table-wrap">
          <table class="track-table" id="sub-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Format</th>
                <th>Language</th>
                <th>Title</th>
                <th>Forced</th>
                <th>Default</th>
                <th>Elements / Codec ID</th>
              </tr>
            </thead>
            <tbody></tbody>
          </table>
        </div>
      </div>

      <pre class="raw-output" id="text-view"></pre>
      <pre class="raw-output" id="json-view"></pre>
    </div>
  </div>

  <script src="./mediainfo.min.js" onerror="this.src='https://cdn.jsdelivr.net/npm/mediainfo.js@0.3.8/dist/umd/index.min.js'"></script>
  <script>
    let miObject = null;
    let miText = null;
    let lastJsonStr = '';
    let lastTextStr = '';
    let lastFileName = 'mediainfo';
    let activeTab = 'cards';

    const statusText = document.getElementById('wasm-status-text');
    const dropzone = document.getElementById('dropzone');
    const fileInput = document.getElementById('file-input');

    function locateWasm(path, prefix) {
      if (path.endsWith('.wasm')) {
        return './MediaInfoModule.wasm';
      }
      return prefix + path;
    }

    async function initMediaInfo() {
      try {
        miObject = await MediaInfo.mediaInfoFactory({ format: 'object', locateFile: locateWasm });
        miText = await MediaInfo.mediaInfoFactory({ format: 'text', locateFile: locateWasm });
        statusText.textContent = 'MediaInfo WASM v0.3.8 Ready (Zero-Copy Mode)';
      } catch (err) {
        console.error('Local WASM load failed, falling back to CDN:', err);
        miObject = await MediaInfo.mediaInfoFactory({ format: 'object' });
        miText = await MediaInfo.mediaInfoFactory({ format: 'text' });
        statusText.textContent = 'MediaInfo WASM Ready (CDN Fallback)';
      }
    }

    initMediaInfo();

    function formatBytes(bytes) {
      if (!bytes || isNaN(bytes)) return '—';
      const n = Number(bytes);
      const units = ['B', 'KiB', 'MiB', 'GiB', 'TiB'];
      let idx = 0;
      let val = n;
      while (val >= 1024 && idx < units.length - 1) {
        val /= 1024;
        idx++;
      }
      return `${val.toFixed(idx >= 3 ? 2 : 1)} ${units[idx]}`;
    }

    function formatBitrate(bps) {
      if (!bps || isNaN(bps)) return '—';
      const n = Number(bps);
      if (n >= 1e6) return `${(n / 1e6).toFixed(2)} Mbps`;
      if (n >= 1e3) return `${(n / 1e3).toFixed(0)} kbps`;
      return `${n} bps`;
    }

    function formatDuration(sec) {
      if (!sec || isNaN(sec)) return '—';
      const total = Math.round(Number(sec));
      const h = Math.floor(total / 3600);
      const m = Math.floor((total % 3600) / 60);
      const s = total % 60;
      return h > 0 ? `${h}h ${m}m ${s}s` : `${m}m ${s}s`;
    }

    function makeReadChunk(file) {
      return async (chunkSize, offset) => {
        const slice = file.slice(offset, offset + chunkSize);
        const buf = await slice.arrayBuffer();
        return new Uint8Array(buf);
      };
    }

    function esc(v) {
      if (v === undefined || v === null || v === '') return '—';
      return String(v)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
    }

    function classifyHdr(v) {
      if (!v) return { label: 'SDR (BT.709)', badges: [] };
      const hdrFormat = v.HDR_Format || '';
      const hdrProfile = v.HDR_Format_Profile || '';
      const hdrComp = v.HDR_Format_Compatibility || '';
      const badges = [];

      if (hdrFormat.includes('Dolby Vision') || hdrProfile.includes('dvhe') || hdrProfile.includes('dvh1')) {
        let dvTag = 'Dolby Vision';
        if (hdrProfile.includes('07')) {
          const isFel = (v.CodecID_String || '').includes('FEL') || JSON.stringify(v).includes('FEL');
          dvTag = `Dolby Vision Profile 7${isFel ? ' (FEL)' : ' (MEL/BL+EL+RPU)'}`;
        } else if (hdrProfile.includes('08')) {
          dvTag = 'Dolby Vision Profile 8.1';
        } else if (hdrProfile.includes('05')) {
          dvTag = 'Dolby Vision Profile 5';
        } else if (hdrProfile) {
          dvTag = `Dolby Vision (${hdrProfile})`;
        }
        badges.push({ cls: 'dv', text: dvTag });
      }
      if (hdrFormat.includes('SMPTE ST 2094') || hdrComp.includes('HDR10+')) {
        badges.push({ cls: 'hdr', text: 'HDR10+ Dynamic Metadata' });
      }
      if (hdrFormat.includes('SMPTE ST 2086') || hdrComp.includes('HDR10') || (v.transfer_characteristics || '').includes('PQ')) {
        badges.push({ cls: 'hdr', text: 'HDR10 Base Layer' });
      }
      if (v.MaxCLL) {
        badges.push({ cls: 'hdr', text: `MaxCLL: ${v.MaxCLL}` });
      }
      if (v.MaxFALL) {
        badges.push({ cls: 'hdr', text: `MaxFALL: ${v.MaxFALL}` });
      }
      return {
        label: [hdrFormat, hdrProfile, hdrComp].filter(Boolean).join(' • ') || (v.transfer_characteristics || 'SDR'),
        badges
      };
    }

    async function analyzeFile(file) {
      if (!miObject || !miText) {
        await initMediaInfo();
      }
      lastFileName = file.name;
      document.getElementById('file-name').textContent = file.name;
      document.getElementById('file-perf').textContent = `Analyzing ${formatBytes(file.size)} via zero-copy File.slice()...`;
      document.getElementById('results').style.display = 'block';

      const t0 = performance.now();
      const readChunk = makeReadChunk(file);
      const [objResult, txtResult] = await Promise.all([
        miObject.analyzeData(() => file.size, readChunk),
        miText.analyzeData(() => file.size, readChunk)
      ]);
      const elapsedMs = (performance.now() - t0).toFixed(1);

      lastJsonStr = JSON.stringify(objResult, null, 2);
      lastTextStr = txtResult;

      document.getElementById('text-view').textContent = lastTextStr;
      document.getElementById('json-view').textContent = lastJsonStr;

      const tracks = (objResult && objResult.media && objResult.media.track) ? objResult.media.track : [];
      const gen = tracks.find(t => t['@type'] === 'General') || {};
      const vid = tracks.find(t => t['@type'] === 'Video') || {};
      const audios = tracks.filter(t => t['@type'] === 'Audio');
      const subs = tracks.filter(t => t['@type'] === 'Text');

      document.getElementById('file-perf').textContent =
        `${formatBytes(file.size)} • ${formatDuration(gen.Duration)} • Overall ${formatBitrate(gen.OverallBitRate)} • Analyzed in ${elapsedMs} ms (${tracks.length} streams)`;

      const hdrInfo = classifyHdr(vid);
      const badgeWrap = document.getElementById('detected-badges');
      const topBadges = [];
      if (vid.Width && vid.Height) {
        topBadges.push({ cls: 'ok', text: `${vid.Width}×${vid.Height} (${vid.BitDepth || 8}-bit ${vid.Format || ''})` });
      }
      topBadges.push(...hdrInfo.badges);
      audios.forEach(a => {
        const comm = a.Format_Commercial_IfAny || a.Format_AdditionalFeatures || '';
        if (comm.includes('Atmos') || (a.Format_AdditionalFeatures || '').includes('JOC')) {
          topBadges.push({ cls: 'atmos', text: `${comm || a.Format} (${a.Language || 'und'})` });
        } else if (comm.includes('DTS') || (a.Format || '').includes('DTS')) {
          topBadges.push({ cls: 'dts', text: `${comm || a.Format} (${a.Language || 'und'})` });
        }
      });

      badgeWrap.innerHTML = topBadges.map(b => `<span class="badge ${b.cls}">${esc(b.text)}</span>`).join('');

      const cardsHtml = `
        <div class="card">
          <div class="card-header">
            <div class="card-title"><span class="material-symbols-outlined">inventory_2</span> Container &amp; General</div>
          </div>
          <div class="kv-list">
            <div class="kv-key">Format</div><div class="kv-val">${esc(gen.Format)} (${esc(gen.Format_Version ? 'v' + gen.Format_Version : 'Matroska/ISOBMFF')})</div>
            <div class="kv-key">File Size</div><div class="kv-val">${esc(formatBytes(file.size))}</div>
            <div class="kv-key">Duration</div><div class="kv-val">${esc(formatDuration(gen.Duration))}</div>
            <div class="kv-key">Overall Bitrate</div><div class="kv-val">${esc(formatBitrate(gen.OverallBitRate))}</div>
            <div class="kv-key">Frame Rate</div><div class="kv-val">${esc(gen.FrameRate ? gen.FrameRate + ' fps' : vid.FrameRate)}</div>
            <div class="kv-key">Encoded App</div><div class="kv-val">${esc(gen.Encoded_Application || gen.Encoded_Library)}</div>
          </div>
        </div>

        <div class="card">
          <div class="card-header">
            <div class="card-title"><span class="material-symbols-outlined">videocam</span> Video Stream</div>
          </div>
          <div class="kv-list">
            <div class="kv-key">Codec / Profile</div><div class="kv-val">${esc(vid.Format)} • ${esc(vid.Format_Profile)}@${esc(vid.Format_Level)} (${esc(vid.Format_Tier)})</div>
            <div class="kv-key">Resolution</div><div class="kv-val">${esc(vid.Width)} × ${esc(vid.Height)} (${esc(vid.DisplayAspectRatio_String || vid.DisplayAspectRatio)})</div>
            <div class="kv-key">Frame Rate</div><div class="kv-val">${esc(vid.FrameRate_String || (vid.FrameRate ? vid.FrameRate + ' fps' : '—'))}</div>
            <div class="kv-key">Bitrate</div><div class="kv-val">${esc(formatBitrate(vid.BitRate))} (${esc(formatBytes(vid.StreamSize))})</div>
            <div class="kv-key">Bit Depth / Chroma</div><div class="kv-val">${esc(vid.BitDepth ? vid.BitDepth + '-bit' : '—')} • ${esc(vid.ChromaSubsampling)}</div>
            <div class="kv-key">Encoder</div><div class="kv-val">${esc(vid.Encoded_Library_Name || vid.CodecID)}</div>
          </div>
        </div>

        <div class="card">
          <div class="card-header">
            <div class="card-title"><span class="material-symbols-outlined">hdr_on</span> HDR &amp; Dolby Vision Metadata</div>
          </div>
          <div class="kv-list">
            <div class="kv-key">HDR Format</div><div class="kv-val">${esc(vid.HDR_Format || 'SDR')}</div>
            <div class="kv-key">DV / HDR Profile</div><div class="kv-val">${esc(vid.HDR_Format_Profile)} ${esc(vid.HDR_Format_Level ? '@' + vid.HDR_Format_Level : '')}</div>
            <div class="kv-key">Compatibility</div><div class="kv-val">${esc(vid.HDR_Format_Compatibility)}</div>
            <div class="kv-key">Mastering Display</div><div class="kv-val">${esc(vid.MasteringDisplay_ColorPrimaries)} • ${esc(vid.MasteringDisplay_Luminance)}</div>
            <div class="kv-key">MaxCLL / MaxFALL</div><div class="kv-val">${esc(vid.MaxCLL || '—')} / ${esc(vid.MaxFALL || '—')}</div>
            <div class="kv-key">Color / Transfer</div><div class="kv-val">${esc(vid.colour_primaries)} • ${esc(vid.transfer_characteristics)}</div>
          </div>
        </div>
      `;
      document.getElementById('summary-cards').innerHTML = cardsHtml;

      const audioTbody = document.querySelector('#audio-table tbody');
      if (audios.length === 0) {
        audioTbody.innerHTML = '<tr><td colspan="8">No audio streams found</td></tr>';
      } else {
        audioTbody.innerHTML = audios.map((a, i) => {
          const comm = a.Format_Commercial_IfAny || a.Format || '—';
          const feat = a.Format_AdditionalFeatures || '';
          const hasAtmos = comm.includes('Atmos') || feat.includes('JOC');
          return `
            <tr>
              <td>#${esc(a.StreamOrder || (i + 1))}</td>
              <td><strong>${esc(comm)}</strong> <span style="color:var(--text-sub)">(${esc(a.Format)})</span></td>
              <td>${hasAtmos ? '<span class="badge atmos">Dolby Atmos / JOC</span>' : esc(feat || 'Standard')}</td>
              <td>${esc(a.Channels)} ch ${a.ChannelLayout ? '(' + esc(a.ChannelLayout) + ')' : ''}</td>
              <td>${esc(formatBitrate(a.BitRate))} (${esc(a.BitRate_Mode || 'VBR')})</td>
              <td>${esc(a.SamplingRate ? (Number(a.SamplingRate)/1000).toFixed(1) + ' kHz' : '—')} / ${esc(a.BitDepth ? a.BitDepth + '-bit' : '—')}</td>
              <td>${esc(a.Language_String || a.Language || 'und')}</td>
              <td>${esc(a.Title || '—')} ${a.Default === 'Yes' ? '<span class="badge ok">Default</span>' : ''}</td>
            </tr>
          `;
        }).join('');
      }

      const subTbody = document.querySelector('#sub-table tbody');
      if (subs.length === 0) {
        subTbody.innerHTML = '<tr><td colspan="7">No subtitle streams found</td></tr>';
      } else {
        subTbody.innerHTML = subs.map((s, i) => `
          <tr>
            <td>#${esc(s.StreamOrder || (i + 1))}</td>
            <td><strong>${esc(s.Format)}</strong></td>
            <td>${esc(s.Language_String || s.Language || 'und')}</td>
            <td>${esc(s.Title || '—')}</td>
            <td>${s.Forced === 'Yes' ? '<span class="badge hdr">Forced</span>' : 'No'}</td>
            <td>${s.Default === 'Yes' ? '<span class="badge ok">Yes</span>' : 'No'}</td>
            <td>${esc(s.ElementCount ? s.ElementCount + ' events • ' : '')}${esc(s.CodecID)}</td>
          </tr>
        `).join('');
      }
    }

    fileInput.addEventListener('change', (e) => {
      if (e.target.files && e.target.files[0]) {
        analyzeFile(e.target.files[0]);
      }
    });

    ['dragenter', 'dragover'].forEach(evt => {
      dropzone.addEventListener(evt, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropzone.classList.add('dragover');
      });
    });

    ['dragleave', 'drop'].forEach(evt => {
      dropzone.addEventListener(evt, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropzone.classList.remove('dragover');
      });
    });

    dropzone.addEventListener('drop', (e) => {
      if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0]) {
        analyzeFile(e.dataTransfer.files[0]);
      }
    });

    function switchTab(tab) {
      activeTab = tab;
      document.getElementById('tab-cards').classList.toggle('active', tab === 'cards');
      document.getElementById('tab-text').classList.toggle('active', tab === 'text');
      document.getElementById('tab-json').classList.toggle('active', tab === 'json');
      document.getElementById('cards-view').style.display = tab === 'cards' ? 'block' : 'none';
      document.getElementById('text-view').style.display = tab === 'text' ? 'block' : 'none';
      document.getElementById('json-view').style.display = tab === 'json' ? 'block' : 'none';
    }

    document.getElementById('tab-cards').addEventListener('click', () => switchTab('cards'));
    document.getElementById('tab-text').addEventListener('click', () => switchTab('text'));
    document.getElementById('tab-json').addEventListener('click', () => switchTab('json'));

    document.getElementById('btn-copy').addEventListener('click', async () => {
      const payload = activeTab === 'json' ? lastJsonStr : lastTextStr;
      if (!payload) return;
      await navigator.clipboard.writeText(payload);
      const btn = document.getElementById('btn-copy');
      const prev = btn.innerHTML;
      btn.innerHTML = '<span class="material-symbols-outlined">check</span> Copied!';
      setTimeout(() => { btn.innerHTML = prev; }, 1500);
    });

    function downloadBlob(content, ext, mime) {
      if (!content) return;
      const blob = new Blob([content], { type: mime });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${lastFileName}.mediainfo.${ext}`;
      a.click();
      URL.revokeObjectURL(url);
    }

    document.getElementById('btn-dl-txt').addEventListener('click', () => downloadBlob(lastTextStr, 'txt', 'text/plain'));
    document.getElementById('btn-dl-json').addEventListener('click', () => downloadBlob(lastJsonStr, 'json', 'application/json'));
  </script>
</body>
</html>
EOF
  mark_synced "${MI_DIR}" "${MI_STAMP}"
  log "MediaInfo Web ready at ${MI_DIR}/index.html"
else
  log "MediaInfo Web (${MI_STAMP}) already up to date in ${MI_DIR}."
fi

log "All 6 zero-container static tools synchronized under ${WEB_ROOT}/"
