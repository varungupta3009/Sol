#!/usr/bin/env python3
"""
qBittorrent Post-Download Completion Hook for ExFAT / Sol Stack (Option A)
Handles instant, zero-copy relative symlinking for Radarr & Sonarr on PANOPTICON.
"""

import sys
import os
import re
import json
import urllib.request
import urllib.parse
import logging

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(SCRIPT_DIR, "torrent_finished.log")

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

RADARR_API_KEY = "${RADARR_API_KEY}"
RADARR_URL = "http://radarr:7878"

SONARR_API_KEY = "${SONARR_API_KEY}"
SONARR_URL = "http://sonarr:8989"

JELLYFIN_TOKEN = "${JELLYFIN_API_KEY}"
JELLYFIN_URL = "http://jellyfin:8096"

NTFY_URL = "http://ntfy:80/qBittorrent"

def send_ntfy(title, message, priority="default"):
    try:
        req = urllib.request.Request(
            NTFY_URL,
            data=message.encode("utf-8"),
            headers={"Title": title, "Priority": priority},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=5):
            pass
        logging.info("Sent ntfy notification: %s - %s", title, message)
    except Exception as e:
        logging.warning("Failed to send ntfy notification: %s", e)

VIDEO_EXTS = {".mkv", ".mp4", ".iso", ".avi", ".ts", ".m4v"}
SUB_EXTS = {".srt", ".vtt", ".sub", ".idx", ".ass"}

def api_request(url, headers=None, method="GET", data=None):
    if headers is None:
        headers = {}
    if data is not None and isinstance(data, dict):
        data = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, headers=headers, method=method, data=data)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read().decode("utf-8")
            return json.loads(content) if content else {}
    except Exception as e:
        logging.warning("API request failed for %s: %s", url, e)
        return None

def trigger_jellyfin_refresh():
    try:
        api_request(
            f"{JELLYFIN_URL}/Library/Refresh",
            headers={"Authorization": f'MediaBrowser Token="{JELLYFIN_TOKEN}"'},
            method="POST"
        )
        logging.info("Triggered Jellyfin library refresh")
    except Exception as e:
        logging.warning("Failed to trigger Jellyfin refresh: %s", e)

def find_media_files(content_path):
    media = []
    if os.path.isfile(content_path):
        ext = os.path.splitext(content_path)[1].lower()
        if ext in VIDEO_EXTS:
            media.append(content_path)
    elif os.path.isdir(content_path):
        found_videos = []
        found_subs = []
        for root, _, files in os.walk(content_path):
            for f in files:
                if f.startswith("."):
                    continue
                ext = os.path.splitext(f)[1].lower()
                full_path = os.path.join(root, f)
                if ext in VIDEO_EXTS:
                    # Filter out small sample files if not sole file
                    is_sample = bool(re.search(r'\bsample\b', f.lower()) or "sample" in root.lower())
                    try:
                        sz = os.path.getsize(full_path)
                    except OSError:
                        sz = 0
                    if not is_sample or sz > 500 * 1024 * 1024:
                        found_videos.append(full_path)
                elif ext in SUB_EXTS:
                    found_subs.append(full_path)
        media.extend(found_videos)
        media.extend(found_subs)
    return media

def normalize_title(text):
    return re.sub(r'[^a-z0-9]', '', text.lower())

def clean_movie_title(name):
    clean = re.sub(r"[\[\(].*?[\]\)]", "", name)
    clean = clean.replace(".", " ").replace("_", " ").strip()
    match = re.search(r"^(.*?)(?:(?:\s|-|_)+(\d{4}))", clean)
    if match:
        title = match.group(1).strip()
        year = match.group(2).strip()
        return f"{title} ({year})"
    return clean

def process_radarr(torrent_name, content_path, save_path):
    logging.info("Processing Radarr download: %s (path: %s)", torrent_name, content_path)
    media_files = find_media_files(content_path)
    if not media_files:
        logging.warning("No media files found in %s", content_path)
        return

    movies = api_request(f"{RADARR_URL}/api/v3/movie", headers={"X-Api-Key": RADARR_API_KEY})
    matched_movie = None
    if movies:
        t_norm = normalize_title(torrent_name)
        # First try exact or high-confidence match
        for m in movies:
            m_title_norm = normalize_title(m.get("title", ""))
            m_year = str(m.get("year", ""))
            if m_title_norm and m_title_norm in t_norm:
                if m_year and m_year in torrent_name:
                    matched_movie = m
                    break
        # Fallback to title substring without year
        if not matched_movie:
            for m in movies:
                m_title_norm = normalize_title(m.get("title", ""))
                if m_title_norm and len(m_title_norm) >= 4 and m_title_norm in t_norm:
                    matched_movie = m
                    break

    target_dir = None
    movie_id = None
    if matched_movie:
        movie_id = matched_movie.get("id")
        target_dir = matched_movie.get("path")
        logging.info("Matched to Radarr movie ID %s: %s (Path: %s)", movie_id, matched_movie.get("title"), target_dir)
    else:
        folder_name = clean_movie_title(torrent_name)
        target_dir = f"/external/media/movies/{folder_name}"
        logging.info("No direct Radarr match; using derived folder: %s", target_dir)

    os.makedirs(target_dir, exist_ok=True)

    # Create relative symlinks
    for f in media_files:
        fname = os.path.basename(f)
        link_path = os.path.join(target_dir, fname)
        rel_target = os.path.relpath(f, target_dir)
        try:
            if os.path.lexists(link_path):
                os.remove(link_path)
            os.symlink(rel_target, link_path)
            logging.info("Created relative symlink: %s -> %s", link_path, rel_target)
        except Exception as e:
            logging.error("Failed to create symlink %s: %s", link_path, e)

    # Clean AppleDouble files if on ExFAT
    for root, _, files in os.walk(target_dir):
        for f in files:
            if f.startswith("._"):
                try:
                    os.remove(os.path.join(root, f))
                except Exception:
                    pass

    # Trigger Radarr rescan
    if movie_id:
        api_request(
            f"{RADARR_URL}/api/v3/command",
            headers={"X-Api-Key": RADARR_API_KEY},
            method="POST",
            data={"name": "RefreshMovie", "movieIds": [movie_id]}
        )
    else:
        api_request(
            f"{RADARR_URL}/api/v3/command",
            headers={"X-Api-Key": RADARR_API_KEY},
            method="POST",
            data={"name": "RefreshMovie"}
        )

    trigger_jellyfin_refresh()
    send_ntfy("Movie Download Complete", f"{torrent_name} has finished downloading and is linked in Jellyfin.")

def process_sonarr(torrent_name, content_path, save_path):
    logging.info("Processing Sonarr download: %s (path: %s)", torrent_name, content_path)
    media_files = find_media_files(content_path)
    if not media_files:
        logging.warning("No media files found in %s", content_path)
        return

    series_list = api_request(f"{SONARR_URL}/api/v3/series", headers={"X-Api-Key": SONARR_API_KEY})
    matched_series = None
    if series_list:
        t_norm = normalize_title(torrent_name)
        for s in series_list:
            s_title_norm = normalize_title(s.get("title", ""))
            if s_title_norm and s_title_norm in t_norm:
                matched_series = s
                break

    target_dir = None
    series_id = None
    if matched_series:
        series_id = matched_series.get("id")
        target_dir = matched_series.get("path")
        logging.info("Matched to Sonarr series ID %s: %s (Path: %s)", series_id, matched_series.get("title"), target_dir)
    else:
        target_dir = f"/external/media/tv/{torrent_name}"
        logging.info("No direct Sonarr match; using derived folder: %s", target_dir)

    os.makedirs(target_dir, exist_ok=True)

    for f in media_files:
        fname = os.path.basename(f)
        link_path = os.path.join(target_dir, fname)
        rel_target = os.path.relpath(f, target_dir)
        try:
            if os.path.lexists(link_path):
                os.remove(link_path)
            os.symlink(rel_target, link_path)
            logging.info("Created relative symlink: %s -> %s", link_path, rel_target)
        except Exception as e:
            logging.error("Failed to create symlink %s: %s", link_path, e)

    # Clean AppleDouble files
    for root, _, files in os.walk(target_dir):
        for f in files:
            if f.startswith("._"):
                try:
                    os.remove(os.path.join(root, f))
                except Exception:
                    pass

    if series_id:
        api_request(
            f"{SONARR_URL}/api/v3/command",
            headers={"X-Api-Key": SONARR_API_KEY},
            method="POST",
            data={"name": "RefreshSeries", "seriesId": series_id}
        )
    else:
        api_request(
            f"{SONARR_URL}/api/v3/command",
            headers={"X-Api-Key": SONARR_API_KEY},
            method="POST",
            data={"name": "RefreshSeries"}
        )

    trigger_jellyfin_refresh()
    send_ntfy("TV Show Download Complete", f"{torrent_name} has finished downloading and is linked in Jellyfin.")

def main():
    if len(sys.argv) < 3:
        logging.info("Hook called with insufficient arguments: %s", sys.argv)
        sys.exit(0)

    torrent_name = sys.argv[1].strip('\'"') if len(sys.argv) > 1 else ""
    category = sys.argv[2].strip('\'"').lower() if len(sys.argv) > 2 else ""
    content_path = sys.argv[3].strip('\'"') if len(sys.argv) > 3 else ""
    root_path = sys.argv[4].strip('\'"') if len(sys.argv) > 4 else ""
    save_path = sys.argv[5].strip('\'"') if len(sys.argv) > 5 else ""
    info_hash = sys.argv[6].strip('\'"') if len(sys.argv) > 6 else ""

    if not content_path or not os.path.exists(content_path):
        fallback = os.path.join(save_path, torrent_name)
        if os.path.exists(fallback):
            content_path = fallback

    logging.info(
        "Torrent finished trigger: name='%s' category='%s' content_path='%s' save_path='%s' hash='%s'",
        torrent_name, category, content_path, save_path, info_hash
    )

    if category == "radarr":
        process_radarr(torrent_name, content_path, save_path)
    elif category == "sonarr":
        process_sonarr(torrent_name, content_path, save_path)
    else:
        logging.info("Category '%s' is not managed by arr symlink hook. Skipping link creation.", category)
        send_ntfy("Download Complete", f"Torrent '{torrent_name}' (Category: {category or 'None'}) has finished downloading.")

if __name__ == "__main__":
    main()

