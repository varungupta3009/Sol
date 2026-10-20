#!/usr/bin/env python3
"""Bootstrap, synchronize, or supervise native macOS Jellyfin Metal on port 8097.

Mirrors the Docker Jellyfin 12.2.0 instance (`config/jellyfin`) into
`config/jellyfin_metal` with zero extra SSD usage for artwork/trickplay:
  - Clones `jellyfin.db` and `introskipper/*.db` via online SQLite `.backup`
    (`immutable=1`), preserving any newer `UserData` watch progress recorded
    on `jellyfin-metal`.
  - Rewrites container paths to native macOS host paths across all 5 path-bearing
    tables (`BaseItems`, `BaseItemImageInfos`, `MediaStreamInfos`, `Chapters`,
    `ImageInfos`) and `data/root/default/*/{*.mblink,options.xml}`:
      /media/external -> /Volumes/PANOPTICON
      /media/internal -> /Users/vrg/Documents/Sol/data/media
      /config         -> /Users/vrg/Documents/Sol/config/jellyfin_metal
  - Symlinks heavy static asset directories (`data/metadata`, `data/data/trickplay`,
    `data/data/subtitles`, `data/data/attachments`, `data/data/collections`,
    `data/data/playlists`, `data/data/splashscreen*.png`, `users`, `cache/omdb`)
    directly to `config/jellyfin`.
  - Copies all 10 installed 12.x plugins (`LDAP-Auth`, `SSO-Auth`, `Intro Skipper`,
    `Jellyfin Enhanced`, `File Transformation`, `Merge Versions`, `Open Subtitles`,
    `Subtitle Extract`, `Chapter Creator`, `TheTVDB`) and rewrites `LDAP-Auth.xml`
    to connect to `127.0.0.1:3890` on the host.
  - Configures Apple M1 Pro `videotoolbox` hardware decoding, encoding, and
    hardware HDR tonemapping (`EnableVideoToolboxTonemapping=true`).
  - In `--daemon` mode (invoked by `launchd` via `/opt/homebrew/bin/python3`),
    synchronizes state and `os.execv`s `/Applications/Jellyfin.app/Contents/MacOS/jellyfin`
    so the server inherits `/opt/homebrew/bin/python3`'s macOS TCC access to
    `~/Documents/Sol` and `/Volumes/PANOPTICON`.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

SOL_BASE = Path("/Users/vrg/Documents/Sol")
DOCKER_CONFIG_DIR = SOL_BASE / "config/jellyfin"
METAL_CONFIG_DIR = SOL_BASE / "config/jellyfin_metal"
METAL_DATA_DIR = METAL_CONFIG_DIR / "data"
METAL_CACHE_DIR = METAL_CONFIG_DIR / "cache"
METAL_LOG_DIR = METAL_CONFIG_DIR / "log"
DOCKER_DB_FILE = DOCKER_CONFIG_DIR / "data/data/jellyfin.db"
METAL_DB_FILE = METAL_DATA_DIR / "data/jellyfin.db"
TRANSCODE_TEMP_DIR = Path("/tmp/jellyfin_metal/transcodes")

JELLYFIN_BIN = "/Applications/Jellyfin.app/Contents/MacOS/jellyfin"
JELLYFIN_WEB = "/Applications/Jellyfin.app/Contents/Resources/jellyfin-web"
JELLYFIN_FFMPEG = "/Applications/Jellyfin.app/Contents/MacOS/ffmpeg"
LAUNCHD_LABEL = "com.vrg.sol.jellyfin-metal"
BASE_URL = "http://127.0.0.1:8097"

PATH_REPLACEMENTS: list[tuple[str, str]] = [
    ("/media/external", "/Volumes/PANOPTICON"),
    ("/media/internal", "/Users/vrg/Documents/Sol/data/media"),
    ("/config", str(METAL_CONFIG_DIR)),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Synchronize and run native macOS Jellyfin Metal on port 8097."
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Sync from config/jellyfin and execv Jellyfin in the foreground (for launchd).",
    )
    parser.add_argument(
        "--sync-only",
        action="store_true",
        help="Synchronize database, plugins, and configs without starting Jellyfin.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Wipe config/jellyfin_metal completely before cloning from config/jellyfin.",
    )
    return parser.parse_args()


def api_get(endpoint: str, token: str | None = None) -> dict | list | None:
    headers = {}
    if token:
        headers["X-Emby-Token"] = token
        headers["Authorization"] = f'MediaBrowser Token="{token}"'
    req = urllib.request.Request(f"{BASE_URL}{endpoint}", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def ensure_symlink(target: Path, link_path: Path) -> None:
    if not target.exists():
        return
    link_path.parent.mkdir(parents=True, exist_ok=True)
    if link_path.is_symlink():
        if os.readlink(link_path) == str(target):
            return
        link_path.unlink()
    elif link_path.exists():
        if link_path.is_dir():
            shutil.rmtree(link_path)
        else:
            link_path.unlink()
    os.symlink(str(target), str(link_path))


def rewrite_paths_in_text(text: str) -> str:
    for old, new in PATH_REPLACEMENTS:
        text = text.replace(old, new)
    return text


def snapshot_sqlite(src_db: Path, dst_db: Path) -> None:
    dst_db.parent.mkdir(parents=True, exist_ok=True)
    for suffix in ("", "-wal", "-shm"):
        p = Path(f"{dst_db}{suffix}")
        if p.exists():
            p.unlink()
    src_con = sqlite3.connect(f"file:{src_db}?immutable=1", uri=True)
    dst_con = sqlite3.connect(str(dst_db))
    src_con.backup(dst_con)
    dst_con.close()
    src_con.close()


def capture_existing_userdata(db_path: Path) -> dict[tuple[str, str, str], tuple]:
    if not db_path.exists():
        return {}
    try:
        con = sqlite3.connect(f"file:{db_path}?immutable=1", uri=True)
        rows = con.execute(
            """
            SELECT ItemId, UserId, CustomDataKey, AudioStreamIndex, IsFavorite,
                   LastPlayedDate, Likes, PlayCount, PlaybackPositionTicks,
                   Played, Rating, SubtitleStreamIndex, RetentionDate
            FROM UserData
            """
        ).fetchall()
        con.close()
        return {(r[0], r[1], r[2]): r for r in rows}
    except Exception:
        return {}


def sync_database(preserve_userdata: bool = True) -> None:
    if not DOCKER_DB_FILE.exists():
        sys.exit(f"ERROR: Source database not found at {DOCKER_DB_FILE}")

    metal_userdata = capture_existing_userdata(METAL_DB_FILE) if preserve_userdata else {}
    snapshot_sqlite(DOCKER_DB_FILE, METAL_DB_FILE)

    con = sqlite3.connect(str(METAL_DB_FILE))
    cur = con.cursor()

    for old, new in PATH_REPLACEMENTS:
        cur.execute(
            "UPDATE BaseItems SET Path = REPLACE(Path, ?, ?) WHERE Path LIKE ?",
            (old, new, f"%{old}%"),
        )
        cur.execute(
            "UPDATE BaseItems SET Data = REPLACE(Data, ?, ?) WHERE Data LIKE ?",
            (old, new, f"%{old}%"),
        )
        cur.execute(
            "UPDATE BaseItemImageInfos SET Path = REPLACE(Path, ?, ?) WHERE Path LIKE ?",
            (old, new, f"%{old}%"),
        )
        cur.execute(
            "UPDATE MediaStreamInfos SET Path = REPLACE(Path, ?, ?) WHERE Path LIKE ?",
            (old, new, f"%{old}%"),
        )
        cur.execute(
            "UPDATE Chapters SET ImagePath = REPLACE(ImagePath, ?, ?) WHERE ImagePath LIKE ?",
            (old, new, f"%{old}%"),
        )
        cur.execute(
            "UPDATE ImageInfos SET Path = REPLACE(Path, ?, ?) WHERE Path LIKE ?",
            (old, new, f"%{old}%"),
        )

    if metal_userdata:
        docker_userdata = {
            (r[0], r[1], r[2]): r
            for r in cur.execute(
                """
                SELECT ItemId, UserId, CustomDataKey, AudioStreamIndex, IsFavorite,
                       LastPlayedDate, Likes, PlayCount, PlaybackPositionTicks,
                       Played, Rating, SubtitleStreamIndex, RetentionDate
                FROM UserData
                """
            ).fetchall()
        }
        to_upsert = []
        for key, m_row in metal_userdata.items():
            d_row = docker_userdata.get(key)
            if d_row is None:
                continue
            m_last = m_row[5] or ""
            d_last = d_row[5] or ""
            m_ticks = m_row[8] or 0
            d_ticks = d_row[8] or 0
            m_count = m_row[7] or 0
            d_count = d_row[7] or 0
            if m_last > d_last or m_count > d_count or (m_last == d_last and m_ticks > d_ticks):
                to_upsert.append(m_row)
        if to_upsert:
            cur.executemany(
                """
                INSERT OR REPLACE INTO UserData (
                    ItemId, UserId, CustomDataKey, AudioStreamIndex, IsFavorite,
                    LastPlayedDate, Likes, PlayCount, PlaybackPositionTicks,
                    Played, Rating, SubtitleStreamIndex, RetentionDate
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                to_upsert,
            )

    con.commit()
    con.close()

    # Snapshot Intro Skipper SQLite databases so skip segments work without lock contention
    src_intro = DOCKER_CONFIG_DIR / "data/data/introskipper"
    dst_intro = METAL_DATA_DIR / "data/introskipper"
    if src_intro.exists():
        dst_intro.mkdir(parents=True, exist_ok=True)
        for db_name in ("introskipper-v2.db", "introskipper.db", "introskipper-cache.db"):
            s_db = src_intro / db_name
            if s_db.exists():
                snapshot_sqlite(s_db, dst_intro / db_name)


def sync_symlinks_and_files() -> None:
    for d in (METAL_CONFIG_DIR, METAL_DATA_DIR, METAL_CACHE_DIR, METAL_LOG_DIR, METAL_DATA_DIR / "data"):
        d.mkdir(parents=True, exist_ok=True)
    TRANSCODE_TEMP_DIR.mkdir(parents=True, exist_ok=True)

    # Shared read/asset directories (0 bytes duplicated on internal NVMe)
    shared_links = [
        (DOCKER_CONFIG_DIR / "data/metadata", METAL_DATA_DIR / "metadata"),
        (DOCKER_CONFIG_DIR / "data/data/trickplay", METAL_DATA_DIR / "data/trickplay"),
        (DOCKER_CONFIG_DIR / "data/data/subtitles", METAL_DATA_DIR / "data/subtitles"),
        (DOCKER_CONFIG_DIR / "data/data/attachments", METAL_DATA_DIR / "data/attachments"),
        (DOCKER_CONFIG_DIR / "data/data/collections", METAL_DATA_DIR / "data/collections"),
        (DOCKER_CONFIG_DIR / "data/data/playlists", METAL_DATA_DIR / "data/playlists"),
        (DOCKER_CONFIG_DIR / "data/data/splashscreen-upload.png", METAL_DATA_DIR / "data/splashscreen-upload.png"),
        (DOCKER_CONFIG_DIR / "data/data/splashscreen.png", METAL_DATA_DIR / "data/splashscreen.png"),
        (DOCKER_CONFIG_DIR / "users", METAL_CONFIG_DIR / "users"),
        (DOCKER_CONFIG_DIR / "cache/omdb", METAL_CACHE_DIR / "omdb"),
    ]
    for src, dst in shared_links:
        ensure_symlink(src, dst)

    # Copy ScheduledTasks settings
    src_tasks = DOCKER_CONFIG_DIR / "data/data/ScheduledTasks"
    dst_tasks = METAL_DATA_DIR / "data/ScheduledTasks"
    if src_tasks.exists():
        if dst_tasks.exists():
            shutil.rmtree(dst_tasks)
        shutil.copytree(src_tasks, dst_tasks)

    # Copy library root definitions and rewrite container paths -> macOS host paths
    src_root = DOCKER_CONFIG_DIR / "data/root"
    dst_root = METAL_DATA_DIR / "root"
    if src_root.exists():
        if dst_root.exists():
            shutil.rmtree(dst_root)
        shutil.copytree(src_root, dst_root)
        for path in dst_root.rglob("*"):
            if path.is_file() and path.suffix in (".mblink", ".xml", ".collection"):
                content = path.read_text(encoding="utf-8")
                updated = rewrite_paths_in_text(content)
                if path.name == "options.xml":
                    # Avoid concurrent scan-time image extraction races with Docker Jellyfin
                    updated = updated.replace(
                        "<ExtractChapterImagesDuringLibraryScan>true</ExtractChapterImagesDuringLibraryScan>",
                        "<ExtractChapterImagesDuringLibraryScan>false</ExtractChapterImagesDuringLibraryScan>",
                    ).replace(
                        "<ExtractTrickplayImagesDuringLibraryScan>true</ExtractTrickplayImagesDuringLibraryScan>",
                        "<ExtractTrickplayImagesDuringLibraryScan>false</ExtractTrickplayImagesDuringLibraryScan>",
                    )
                if updated != content:
                    path.write_text(updated, encoding="utf-8")

    # Copy plugins and plugin configurations
    src_plugins = DOCKER_CONFIG_DIR / "data/plugins"
    dst_plugins = METAL_DATA_DIR / "plugins"
    if src_plugins.exists():
        dst_plugins.mkdir(parents=True, exist_ok=True)
        for item in src_plugins.iterdir():
            target_item = dst_plugins / item.name
            if item.name == "configurations":
                if target_item.exists():
                    shutil.rmtree(target_item)
                shutil.copytree(
                    item,
                    target_item,
                    ignore=shutil.ignore_patterns("*.bak.*"),
                )
            elif item.is_dir():
                if target_item.exists():
                    shutil.rmtree(target_item)
                shutil.copytree(item, target_item)
            elif item.is_file():
                shutil.copy2(item, target_item)

    # Adapt LDAP-Auth.xml for host loopback (127.0.0.1:3890)
    ldap_xml = dst_plugins / "configurations/LDAP-Auth.xml"
    if ldap_xml.exists():
        tree = ET.parse(ldap_xml)
        root = tree.getroot()
        srv = root.find("LdapServer")
        if srv is not None:
            srv.text = "127.0.0.1"
        ET.indent(tree, space="  ")
        tree.write(ldap_xml, encoding="utf-8", xml_declaration=True)

    # Disable duplicate IntroSkipper background fingerprint jobs on Metal
    intro_xml = dst_plugins / "configurations/IntroSkipper.xml"
    if intro_xml.exists():
        tree = ET.parse(intro_xml)
        root = tree.getroot()
        auto_detect = root.find("AutoDetectIntros")
        if auto_detect is not None:
            auto_detect.text = "false"
        ET.indent(tree, space="  ")
        tree.write(intro_xml, encoding="utf-8", xml_declaration=True)


def write_server_xml_configs() -> None:
    # 1. logging.default.json and database.xml
    for fname in ("logging.default.json", "database.xml"):
        src = DOCKER_CONFIG_DIR / fname
        if src.exists():
            shutil.copy2(src, METAL_CONFIG_DIR / fname)

    # 2. branding.xml
    src_branding = DOCKER_CONFIG_DIR / "branding.xml"
    if src_branding.exists():
        text = rewrite_paths_in_text(src_branding.read_text(encoding="utf-8"))
        (METAL_CONFIG_DIR / "branding.xml").write_text(text, encoding="utf-8")

    # 3. network.xml (Port 8097 / 8921)
    network_xml = """<?xml version="1.0" encoding="utf-8"?>
<NetworkConfiguration xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <BaseUrl />
  <EnableHttps>false</EnableHttps>
  <RequireHttps>false</RequireHttps>
  <CertificatePath />
  <CertificatePassword />
  <InternalHttpPort>8097</InternalHttpPort>
  <InternalHttpsPort>8921</InternalHttpsPort>
  <PublicHttpPort>8097</PublicHttpPort>
  <PublicHttpsPort>8921</PublicHttpsPort>
  <AutoDiscovery>true</AutoDiscovery>
  <EnableUPnP>false</EnableUPnP>
  <EnableIPv4>true</EnableIPv4>
  <EnableIPv6>false</EnableIPv6>
  <EnableRemoteAccess>true</EnableRemoteAccess>
  <LocalNetworkSubnets />
  <LocalNetworkAddresses />
  <KnownProxies />
  <IgnoreVirtualInterfaces>true</IgnoreVirtualInterfaces>
  <VirtualInterfaceNames>
    <string>veth</string>
  </VirtualInterfaceNames>
  <EnablePublishedServerUriByRequest>false</EnablePublishedServerUriByRequest>
  <PublishedServerUriBySubnet />
  <RemoteIPFilter />
  <IsRemoteIPFilterBlacklist>false</IsRemoteIPFilterBlacklist>
</NetworkConfiguration>
"""
    (METAL_CONFIG_DIR / "network.xml").write_text(network_xml, encoding="utf-8")

    # 4. system.xml (cloned from Docker Jellyfin with native paths + Sol Metal ServerName + HW Trickplay)
    src_system = DOCKER_CONFIG_DIR / "system.xml"
    if src_system.exists():
        text = rewrite_paths_in_text(src_system.read_text(encoding="utf-8"))
        tree = ET.fromstring(text)
        sname = tree.find("ServerName")
        if sname is not None:
            sname.text = "Sol Metal"
        tp = tree.find("TrickplayOptions")
        if tp is not None:
            hw_acc = tp.find("EnableHwAcceleration")
            if hw_acc is not None:
                hw_acc.text = "true"
            hw_enc = tp.find("EnableHwEncoding")
            if hw_enc is not None:
                hw_enc.text = "true"
        ET.indent(tree, space="  ")
        ET.ElementTree(tree).write(
            METAL_CONFIG_DIR / "system.xml", encoding="utf-8", xml_declaration=True
        )

    # 5. encoding.xml (Apple M1 Pro VideoToolbox HW acceleration + HDR tonemapping)
    encoding_xml = f"""<?xml version="1.0" encoding="utf-8"?>
<EncodingOptions xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <EncodingThreadCount>-1</EncodingThreadCount>
  <TranscodingTempPath>{TRANSCODE_TEMP_DIR}</TranscodingTempPath>
  <FallbackFontPath />
  <EnableFallbackFont>false</EnableFallbackFont>
  <EnableAudioVbr>false</EnableAudioVbr>
  <DownMixAudioBoost>2</DownMixAudioBoost>
  <DownMixStereoAlgorithm>None</DownMixStereoAlgorithm>
  <MaxMuxingQueueSize>2048</MaxMuxingQueueSize>
  <EnableThrottling>true</EnableThrottling>
  <ThrottleDelaySeconds>120</ThrottleDelaySeconds>
  <EnableSegmentDeletion>true</EnableSegmentDeletion>
  <SegmentKeepSeconds>720</SegmentKeepSeconds>
  <HardwareAccelerationType>videotoolbox</HardwareAccelerationType>
  <EncoderAppPath>{JELLYFIN_FFMPEG}</EncoderAppPath>
  <EncoderAppPathDisplay>{JELLYFIN_FFMPEG}</EncoderAppPathDisplay>
  <VaapiDevice>/dev/dri/renderD128</VaapiDevice>
  <QsvDevice />
  <EnableTonemapping>true</EnableTonemapping>
  <EnableVppTonemapping>false</EnableVppTonemapping>
  <EnableVideoToolboxTonemapping>true</EnableVideoToolboxTonemapping>
  <TonemappingAlgorithm>bt2390</TonemappingAlgorithm>
  <TonemappingMode>auto</TonemappingMode>
  <TonemappingRange>auto</TonemappingRange>
  <TonemappingDesat>0</TonemappingDesat>
  <TonemappingPeak>100</TonemappingPeak>
  <TonemappingParam>0</TonemappingParam>
  <VppTonemappingBrightness>16</VppTonemappingBrightness>
  <VppTonemappingContrast>1</VppTonemappingContrast>
  <H264Crf>23</H264Crf>
  <H265Crf>28</H265Crf>
  <EncoderPreset>auto</EncoderPreset>
  <DeinterlaceDoubleRate>false</DeinterlaceDoubleRate>
  <DeinterlaceMethod>yadif</DeinterlaceMethod>
  <EnableDecodingColorDepth10Hevc>true</EnableDecodingColorDepth10Hevc>
  <EnableDecodingColorDepth10Vp9>true</EnableDecodingColorDepth10Vp9>
  <EnableDecodingColorDepth10HevcRext>true</EnableDecodingColorDepth10HevcRext>
  <EnableDecodingColorDepth12HevcRext>true</EnableDecodingColorDepth12HevcRext>
  <EnableEnhancedNvdecDecoder>true</EnableEnhancedNvdecDecoder>
  <PreferSystemNativeHwDecoder>true</PreferSystemNativeHwDecoder>
  <EnableIntelLowPowerH264HwEncoder>false</EnableIntelLowPowerH264HwEncoder>
  <EnableIntelLowPowerHevcHwEncoder>false</EnableIntelLowPowerHevcHwEncoder>
  <EnableHardwareEncoding>true</EnableHardwareEncoding>
  <AllowHevcEncoding>true</AllowHevcEncoding>
  <AllowAv1Encoding>false</AllowAv1Encoding>
  <EnableSubtitleExtraction>false</EnableSubtitleExtraction>
  <SubtitleExtractionTimeoutMinutes>30</SubtitleExtractionTimeoutMinutes>
  <HardwareDecodingCodecs>
    <string>h264</string>
    <string>hevc</string>
    <string>vc1</string>
    <string>vp9</string>
    <string>av1</string>
  </HardwareDecodingCodecs>
  <AllowOnDemandMetadataBasedKeyframeExtractionForExtensions>
    <string>mkv</string>
  </AllowOnDemandMetadataBasedKeyframeExtractionForExtensions>
</EncodingOptions>
"""
    (METAL_CONFIG_DIR / "encoding.xml").write_text(encoding_xml, encoding="utf-8")


def sync_all(reset: bool = False) -> None:
    if reset and METAL_CONFIG_DIR.exists():
        shutil.rmtree(METAL_CONFIG_DIR)
    sync_symlinks_and_files()
    write_server_xml_configs()
    sync_database(preserve_userdata=not reset)


def jellyfin_cmd() -> list[str]:
    return [
        JELLYFIN_BIN,
        "--configdir",
        str(METAL_CONFIG_DIR),
        "--datadir",
        str(METAL_DATA_DIR),
        "--cachedir",
        str(METAL_CACHE_DIR),
        "--logdir",
        str(METAL_LOG_DIR),
        "--webdir",
        JELLYFIN_WEB,
        "--ffmpeg",
        JELLYFIN_FFMPEG,
    ]


def main() -> None:
    args = parse_args()

    if args.daemon:
        sync_all(reset=args.reset)
        cmd = jellyfin_cmd()
        os.execv(cmd[0], cmd)

    if args.sync_only:
        print("Synchronizing config/jellyfin -> config/jellyfin_metal...")
        sync_all(reset=args.reset)
        print("Synchronization complete.")
        return

    uid = os.getuid()
    plist_path = Path.home() / f"Library/LaunchAgents/{LAUNCHD_LABEL}.plist"

    print("1. Stopping any running native Jellyfin Metal instance...")
    if plist_path.exists():
        subprocess.run(
            ["launchctl", "bootout", f"gui/{uid}/{LAUNCHD_LABEL}"],
            capture_output=True,
            check=False,
        )
    subprocess.run(["killall", "jellyfin"], capture_output=True, check=False)
    time.sleep(1)

    print("2. Synchronizing database, plugins, users, and libraries from Docker Jellyfin...")
    sync_all(reset=args.reset)

    print("3. Starting native Jellyfin Metal on port 8097...")
    if plist_path.exists():
        subprocess.run(
            ["launchctl", "bootstrap", f"gui/{uid}", str(plist_path)],
            capture_output=True,
            check=False,
        )
        subprocess.run(
            ["launchctl", "kickstart", "-k", f"gui/{uid}/{LAUNCHD_LABEL}"],
            capture_output=True,
            check=False,
        )
    else:
        subprocess.Popen(
            jellyfin_cmd(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

    for _ in range(45):
        info = api_get("/System/Info/Public")
        if isinstance(info, dict) and "ServerName" in info:
            print(
                f"   Native Jellyfin Metal is online at {BASE_URL} "
                f"(ServerName: {info.get('ServerName')}, Version: {info.get('Version')})."
            )
            return
        time.sleep(1)

    print("ERROR: Native Jellyfin Metal failed to respond on port 8097 within 45s.")
    sys.exit(1)


if __name__ == "__main__":
    main()
