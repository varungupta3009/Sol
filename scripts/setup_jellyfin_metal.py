#!/usr/bin/env python3
import os
import sys
import time
import json
import shutil
import urllib.request
import urllib.error
import subprocess

CONFIG_DIR = "/Users/vrg/Documents/Sol/config/jellyfin_metal"
DATA_DIR = os.path.join(CONFIG_DIR, "data")
CACHE_DIR = os.path.join(CONFIG_DIR, "cache")
LOG_DIR = os.path.join(CONFIG_DIR, "log")
BASE_URL = "http://127.0.0.1:8097"
USERNAME = os.environ.get("JELLYFIN_ADMIN_USER", "VRG")

def get_admin_password():
    if os.environ.get("CORE_PASSWORD"):
        return os.environ["CORE_PASSWORD"]
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("CORE_PASSWORD="):
                    val = line.split("=", 1)[1].strip("'\"")
                    if val:
                        return val
    import getpass
    return getpass.getpass("Enter Jellyfin Admin Password: ")

PASSWORD = get_admin_password()

# 1. Clean slate
print("1. Terminating any running instances...")
subprocess.run(["killall", "jellyfin"], capture_output=True)
time.sleep(1)

if os.path.exists(CONFIG_DIR):
    shutil.rmtree(CONFIG_DIR)

os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

# Write network.xml with port 8097
network_xml = """<?xml version="1.0" encoding="utf-8"?>
<NetworkConfiguration xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <InternalHttpPort>8097</InternalHttpPort>
  <InternalHttpsPort>8921</InternalHttpsPort>
  <PublicHttpPort>8097</PublicHttpPort>
  <PublicHttpsPort>8921</PublicHttpsPort>
</NetworkConfiguration>
"""
with open(os.path.join(CONFIG_DIR, "network.xml"), "w") as f:
    f.write(network_xml)

# 2. Launch process
print("2. Starting native Jellyfin on port 8097...")
cmd = [
    "/Applications/Jellyfin.app/Contents/MacOS/jellyfin",
    "--configdir", CONFIG_DIR,
    "--datadir", DATA_DIR,
    "--cachedir", CACHE_DIR,
    "--logdir", LOG_DIR,
    "--webdir", "/Applications/Jellyfin.app/Contents/Resources/jellyfin-web",
    "--ffmpeg", "/Applications/Jellyfin.app/Contents/MacOS/ffmpeg"
]
proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def api_post(endpoint, data=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Emby-Token"] = token
        headers["Authorization"] = f'MediaBrowser Token="{token}"'
    else:
        headers["Authorization"] = 'MediaBrowser Client="Jellyfin Setup", Device="Script", DeviceId="setup-script", Version="1.0.0"'
    
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(f"{BASE_URL}{endpoint}", data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            res = resp.read().decode("utf-8")
            return json.loads(res) if res else {"status": resp.status}
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8")
        return {"error": str(e), "body": err, "code": e.code}
    except Exception as e:
        return {"error": str(e)}

def api_get(endpoint, token=None):
    headers = {}
    if token:
        headers["X-Emby-Token"] = token
        headers["Authorization"] = f'MediaBrowser Token="{token}"'
    else:
        headers["Authorization"] = 'MediaBrowser Client="Jellyfin Setup", Device="Script", DeviceId="setup-script", Version="1.0.0"'
    req = urllib.request.Request(f"{BASE_URL}{endpoint}", headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8")
        return {"error": str(e), "body": err, "code": e.code}
    except Exception as e:
        return {"error": str(e)}

# 3. Wait for readiness (200 on /Startup/User)
print("3. Waiting for server to finish internal migrations...")
ready = False
for i in range(30):
    res = api_get("/Startup/User")
    if isinstance(res, dict) and "Name" in res:
        ready = True
        break
    time.sleep(1)

if not ready:
    print("ERROR: Server failed to ready startup endpoints.")
    sys.exit(1)

print("   Jellyfin is ready for configuration!")

# 4. Startup Wizard
print("4. Executing Initial Setup Wizard via API...")
user_res = api_post("/Startup/User", {"Name": USERNAME, "Password": PASSWORD})
print(f"   /Startup/User -> {user_res}")

cfg_res = api_post("/Startup/Configuration", {"UICulture": "en-US", "MetadataCountryCode": "IN", "PreferredMetadataLanguage": "en"})
print(f"   /Startup/Configuration -> {cfg_res}")

remote_res = api_post("/Startup/RemoteAccess", {"EnableRemoteAccess": True, "EnableAutomaticPortMapping": True})
print(f"   /Startup/RemoteAccess -> {remote_res}")

comp_res = api_post("/Startup/Complete")
print(f"   /Startup/Complete -> {comp_res}")

# 5. Authenticate Admin User
print("5. Authenticating admin user...")
token = None
user_id = None
for i in range(25):
    time.sleep(1)
    auth_res = api_post("/Users/AuthenticateByName", {"Username": USERNAME, "Pw": PASSWORD})
    if isinstance(auth_res, dict) and "AccessToken" in auth_res:
        token = auth_res["AccessToken"]
        user_id = auth_res["User"]["Id"]
        break
    print(f"   Waiting for auth ({i+1}/25)...")

if not token:
    print("ERROR: Authentication failed:", auth_res)
    sys.exit(1)

print(f"   Authenticated as {USERNAME}! (Token: {token[:10]}...)")

# 6. Configure VideoToolbox
print("6. Configuring Apple VideoToolbox Hardware Acceleration...")
encoding_opts = api_get("/System/Configuration/Encoding", token)
encoding_opts.update({
    "HardwareAccelerationType": "videotoolbox",
    "EnableTonemapping": True,
    "EnableVideoToolboxTonemapping": True,
    "EnableThrottling": True,
    "ThrottleDelaySeconds": 120,
    "EncoderAppPathDisplay": "/Applications/Jellyfin.app/Contents/MacOS/ffmpeg",
    "HardwareDecodingCodecs": ["h264", "hevc", "vc1", "vp9", "av1"],
    "EnableDecodingColorDepth10Hevc": True,
    "EnableDecodingColorDepth10Vp9": True,
    "AllowHevcEncoding": True,
    "AllowAv1Encoding": True
})
api_post("/System/Configuration/Encoding", encoding_opts, token)

# 7. Configure Branding & Abyss CSS Theme
print("7. Applying Abyss Theme & Custom CSS...")
branding_opts = api_get("/System/Configuration/Branding", token)
branding_opts.update({
    "CustomCss": "@import url('https://cdn.jsdelivr.net/gh/AumGupta/abyss-jellyfin@main/abyss.css');",
    "SplashscreenEnabled": True
})
api_post("/System/Configuration/Branding", branding_opts, token)

# 8. Add Media Libraries
print("8. Creating Media Libraries (Internal SSD + PANOPTICON USB)...")
# Movies
movie_paths = ["/Users/vrg/Documents/Sol/data/media/movies"]
if os.path.exists("/Volumes/PANOPTICON/Movies"):
    movie_paths.append("/Volumes/PANOPTICON/Movies")

movie_options = {
    "Enabled": True,
    "EnablePhotos": True,
    "EnableRealtimeMonitor": True,
    "EnableChapterImageExtraction": True,
    "EnableTrickplayImageExtraction": True,
    "ExtractChapterImagesDuringLibraryScan": True,
    "PathInfos": [{"Path": p} for p in movie_paths],
    "TypeOptions": [
        {
            "Type": "Movie",
            "MetadataFetchers": ["TheMovieDb", "The Open Movie Database"],
            "ImageFetchers": ["TheMovieDb", "The Open Movie Database", "Screen Grabber"]
        }
    ]
}
api_post("/Library/VirtualFolders?collectionType=movies&name=Movies&refreshLibrary=true", {"LibraryOptions": movie_options}, token)

# TV Shows
tv_paths = ["/Users/vrg/Documents/Sol/data/media/tv"]
if os.path.exists("/Volumes/PANOPTICON/TV Shows"):
    tv_paths.append("/Volumes/PANOPTICON/TV Shows")

tv_options = {
    "Enabled": True,
    "EnablePhotos": True,
    "EnableRealtimeMonitor": True,
    "EnableChapterImageExtraction": True,
    "PathInfos": [{"Path": p} for p in tv_paths],
    "TypeOptions": [
        {
            "Type": "Series",
            "MetadataFetchers": ["TheTVDB", "TheMovieDb"],
            "ImageFetchers": ["TheTVDB", "TheMovieDb", "Screen Grabber"]
        }
    ]
}
api_post("/Library/VirtualFolders?collectionType=tvshows&name=Shows&refreshLibrary=true", {"LibraryOptions": tv_options}, token)

# 9. Create API Keys for Jellyseerr and Bazarr
print("9. Generating API Keys for Jellyseerr & Bazarr...")
api_post("/Auth/Keys?app=Jellyseerr", None, token)
api_post("/Auth/Keys?app=Bazarr", None, token)

keys = api_get("/Auth/Keys", token)

print("\n" + "="*60)
print("🎉 NATIVE JELLYFIN METAL AUTOMATION COMPLETE!")
print("========================================================")
print(f"URL:              https://metal.vrg.rocks (or http://localhost:8097)")
print(f"Admin User:       {USERNAME}")
print(f"Hardware Accel:   Apple VideoToolbox (M1 Pro Media Engine)")
print(f"Theme:            Abyss Dark Theme (Active)")
print("Libraries Added:")
print(f"  • Movies:       {', '.join(movie_paths)}")
print(f"  • TV Shows:     {', '.join(tv_paths)}")
print("Generated API Keys:")
for k in keys.get("Items", []):
    print(f"  • {k.get('AppName')}: {k.get('AccessToken')}")
print("="*60)
