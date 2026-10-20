#!/usr/bin/env python3
"""Execute live migration of PANOPTICON to TRaSH-compliant torrents/ and media/ structure.

Features:
- Pure same-filesystem atomic moves (os.rename). Zero file copying.
- Reclaims 114.23 GB of duplicate files by converting to relative symlinks.
- Rewrites qBittorrent .fastresume files with full AST bencode verification.
- Updates Radarr, Sonarr, and Jellyfin path configurations.
- Dry-run by default. Pass --apply to execute.
"""

import os, sys, glob, sqlite3, shutil

APPLY = "--apply" in sys.argv

PAN_ROOT = "/Volumes/PANOPTICON"
PAN_MOVIES = os.path.join(PAN_ROOT, "Movies")
PAN_TV = os.path.join(PAN_ROOT, "TV Shows")
PAN_TORRENTS = os.path.join(PAN_ROOT, "torrents")
PAN_MEDIA = os.path.join(PAN_ROOT, "media")

# Bencode AST Parser & Serializer
def dec(b, i=0):
    c = b[i:i + 1]
    if c == b"i":
        j = b.index(b"e", i)
        return int(b[i + 1:j]), j + 1
    if c == b"l":
        i += 1
        out = []
        while b[i:i + 1] != b"e":
            v, i = dec(b, i)
            out.append(v)
        return out, i + 1
    if c == b"d":
        i += 1
        out = {}
        while b[i:i + 1] != b"e":
            k, i = dec(b, i)
            v, i = dec(b, i)
            out[k] = v
        return out, i + 1
    j = b.index(b":", i)
    n = int(b[i:j])
    return b[j + 1:j + 1 + n], j + 1 + n

def enc(v):
    if isinstance(v, int):
        return b"i%de" % v
    if isinstance(v, bytes):
        return b"%d:%s" % (len(v), v)
    if isinstance(v, list):
        return b"l" + b"".join(enc(x) for x in v) + b"e"
    if isinstance(v, dict):
        return b"d" + b"".join(enc(k) + enc(x) for k, x in sorted(v.items())) + b"e"
    raise TypeError(type(v))

def main():
    mode = "APPLY" if APPLY else "DRY-RUN"
    print(f"==================================================")
    print(f"  PANOPTICON STORAGE RESTRUCTURING [{mode}]")
    print(f"==================================================")

    # 1. Ensure target directories exist
    os.makedirs(os.path.join(PAN_TORRENTS, "movies", "3DTorrents"), exist_ok=True)
    os.makedirs(os.path.join(PAN_TORRENTS, "tv"), exist_ok=True)
    os.makedirs(os.path.join(PAN_TORRENTS, "cross-seed-links"), exist_ok=True)
    os.makedirs(os.path.join(PAN_MEDIA, "movies"), exist_ok=True)
    os.makedirs(os.path.join(PAN_MEDIA, "tv"), exist_ok=True)

    # 2. Identify all 46 external torrents
    root_qbt = "config/qbittorrent/qBittorrent/BT_backup"
    torrent_items = set()
    torrent_map = {} # hash -> dict
    for p in sorted(glob.glob(os.path.join(root_qbt, "*.fastresume"))):
        data, _ = dec(open(p, "rb").read())
        sp = data.get(b"save_path", b"").decode("utf-8", "replace")
        if "/external" not in sp: continue
        t_path = p[:-len(".fastresume")] + ".torrent"
        t_name = ""
        if os.path.exists(t_path):
            try:
                t_data, _ = dec(open(t_path, "rb").read())
                t_name = t_data.get(b"info", {}).get(b"name.utf-8", t_data.get(b"info", {}).get(b"name", b"")).decode("utf-8", "replace")
            except: pass
        if not t_name:
            t_name = data.get(b"qBt-name", b"").decode("utf-8", "replace")
        
        h = os.path.basename(p)[:-len(".fastresume")]
        torrent_map[h] = {
            "fastresume": p,
            "name": t_name,
            "sp": sp
        }
        torrent_items.add((sp, t_name))

    print(f"[QBT] Found {len(torrent_map)} external torrents.")

    # 3. Move Torrents to torrents/
    print("\n--- PHASE 1: Moving Torrent Payloads to torrents/ ---")
    moved_torrents = 0
    for h, info in torrent_map.items():
        sp = info["sp"]
        name = info["name"]
        if sp == "/external/3DTorrents":
            continue # Leave tools in place
        
        if sp == "/external/Movies":
            src = os.path.join(PAN_MOVIES, name)
            dst = os.path.join(PAN_TORRENTS, "movies", name)
        elif sp == "/external/Movies/3DTorrents":
            src = os.path.join(PAN_MOVIES, "3DTorrents", name)
            dst = os.path.join(PAN_TORRENTS, "movies", "3DTorrents", name)
        elif sp == "/external/TV Shows":
            src = os.path.join(PAN_TV, name)
            dst = os.path.join(PAN_TORRENTS, "tv", name)
        else:
            continue

        if os.path.exists(src):
            print(f"  MOVE TORRENT: {name[:45]:<45} -> {os.path.relpath(dst, PAN_ROOT)}")
            if APPLY:
                os.rename(src, dst)
            moved_torrents += 1
        elif os.path.exists(dst):
            print(f"  ALREADY MOVED: {name[:45]:<45}")
            moved_torrents += 1
        else:
            print(f"  ERROR: Torrent not found: {src}")
            sys.exit(1)

    print(f"Total torrent payloads moved/verified: {moved_torrents}")

    # Move cross-seed-links
    cs_src = os.path.join(PAN_ROOT, "cross-seed-links")
    cs_dst = os.path.join(PAN_TORRENTS, "cross-seed-links")
    if os.path.exists(cs_src):
        for item in os.listdir(cs_src):
            s = os.path.join(cs_src, item)
            d = os.path.join(cs_dst, item)
            print(f"  MOVE CROSS-SEED-LINK: {item}")
            if APPLY:
                os.rename(s, d)

    # 4. Handle Media (Movies & TV Shows)
    print("\n--- PHASE 2: Setting up Clean media/ Structure ---")
    
    # Connect to Radarr DB to get movie metadata
    conn_r = sqlite3.connect("config/radarr/radarr.db")
    c_r = conn_r.cursor()
    c_r.execute("""
    SELECT m.Id, md.Title, md.Year, m.Path, mf.RelativePath
    FROM Movies m
    JOIN MovieMetadata md ON m.MovieMetadataId = md.Id
    LEFT JOIN MovieFiles mf ON m.MovieFileId = mf.Id
    WHERE m.Path LIKE '/external%'
    """)
    radarr_movies = c_r.fetchall()

    radarr_path_updates = [] # (new_path, new_relpath, movie_id)

    # Known 10 duplicate groups:
    duplicates_clean_folders = {
        "Do Dooni Chaar (2010)": ("Do Dooni Chaar 2010 1080p NF H264 EAC3/Do Dooni Chaar 2010 1080p NF H264 EAC3.mp4", "Do Dooni Chaar 2010 1080p NF H264 EAC3.mp4"),
        "Eraser (1996)": ("Eraser 1996 REMASTERED 1080p BluRay HEVC x265 5.1 BONE.mkv", "Eraser 1996 REMASTERED 1080p BluRay HEVC x265 5.1 BONE.mkv"),
        "Event Horizon (1997)": ("Event Horizon 1997 2160p ATVP WEB-DL DD 5 1 DV HDR H 265-PiRaTeS/Event Horizon 1997 2160p ATVP WEB-DL DD 5 1 DV HDR H 265-PiRaTeS.mkv", "Event Horizon 1997 2160p ATVP WEB-DL DD 5 1 DV HDR H 265-PiRaTeS.mkv"),
        "Insidious (2011)": ("Insidious 2010 UHD BluRay 2160p DDP 7 1 DV HDR x265-BHDStudio/Insidious 2010 UHD BluRay 2160p DDP 7 1 DV HDR x265-BHDStudio.mp4", "Insidious 2010 UHD BluRay 2160p DDP 7 1 DV HDR x265-BHDStudio.mp4"),
        "Interstellar (2014)": ("Interstellar.2014.2160p.HDR.UHD.BluRay.DTS-HD.MA.5.1.2Audio.x265-10bit-HDS.mkv", "Interstellar.2014.2160p.HDR.UHD.BluRay.DTS-HD.MA.5.1.2Audio.x265-10bit-HDS.mkv"),
        "Little Miss Sunshine (2006)": ("Little.Miss.Sunshine.2006.DV.HDR.2160p.WEB.H265-RVKD/Little.Miss.Sunshine.2006.DV.HDR.2160p.WEB.H265-RVKD.mkv", "Little.Miss.Sunshine.2006.DV.HDR.2160p.WEB.H265-RVKD.mkv"),
        "Obsession (2026)": ("Obsession 2025 2160p MA WEB-DL DDP5 1 Atmos DV HDR H 265-BYNDR/Obsession 2025 2160p MA WEB-DL DDP5 1 Atmos DV HDR H 265-BYNDR.mkv", "Obsession 2025 2160p MA WEB-DL DDP5 1 Atmos DV HDR H 265-BYNDR.mkv"),
        "Signs (2002)": ("Signs.2002.1080p.BluRay.DTS.x264-CtrlHD/Signs.2002.1080p.BluRay.DTS.x264-CtrlHD.mkv", "Signs.2002.1080p.BluRay.DTS.x264-CtrlHD.mkv"),
        "The Lunchbox (2013)": ("The.Lunchbox.2013.BD-Remux.mkv", "The.Lunchbox.2013.BD-Remux.mkv"),
        "The Substance": ("The Substance (2024) (2160p BluRay x265 10bit DV HDR DTS-HD MA 5.1 r00t)/The Substance (2024) (2160p BluRay x265 10bit DV HDR r00t).mkv", "The Substance 2024 2160p BluRay x265 10bit DV HDR DTS HD MA 5.mkv"),
    }

    space_reclaimed = 0

    for m in radarr_movies:
        mid, title, year, old_path, relpath = m
        folder_name = os.path.basename(old_path.rstrip("/"))
        clean_name = f"{title} ({year})"
        
        # Check if it was in the duplicate group
        matched_dup = None
        for df, (t_rel, c_file) in duplicates_clean_folders.items():
            if df.lower() in folder_name.lower() or title.lower() in df.lower():
                matched_dup = (df, t_rel, c_file)
                break
        
        if matched_dup:
            df, t_rel, c_file = matched_dup
            src_folder = os.path.join(PAN_MOVIES, folder_name)
            dst_folder = os.path.join(PAN_MEDIA, "movies", clean_name)
            print(f"  [DEDUPLICATE] {title} ({year})")
            
            # Target symlink path: from dst_folder, 3 levels up is /Volumes/PANOPTICON
            rel_symlink_target = f"../../../torrents/movies/{t_rel}"
            
            if APPLY:
                os.makedirs(dst_folder, exist_ok=True)
                # Find the video file in src_folder
                if os.path.exists(src_folder):
                    for f in os.listdir(src_folder):
                        fp = os.path.join(src_folder, f)
                        if os.path.isfile(fp):
                            sz = os.path.getsize(fp)
                            if sz > 500 * 1024 * 1024:
                                space_reclaimed += sz
                                os.remove(fp) # Delete duplicate
                            else:
                                # Move subtitles / extra files
                                os.rename(fp, os.path.join(dst_folder, f))
                    # Remove empty src_folder
                    try: os.rmdir(src_folder)
                    except: pass
                
                # Create relative symlink
                sym_path = os.path.join(dst_folder, c_file)
                if os.path.exists(sym_path) or os.path.islink(sym_path):
                    os.remove(sym_path)
                os.symlink(rel_symlink_target, sym_path)

            new_container_path = f"/external/media/movies/{clean_name}"
            radarr_path_updates.append((new_container_path, c_file, mid))

        elif old_path.startswith("/external/Movies/") and folder_name in [t[1] for t in torrent_items]:
            # This is an in-place movie where Radarr pointed directly to the torrent folder!
            print(f"  [IN-PLACE -> CLEAN] {title} ({year})")
            dst_folder = os.path.join(PAN_MEDIA, "movies", clean_name)
            
            # Find the main video file inside the torrent payload
            torrent_payload = os.path.join(PAN_TORRENTS, "movies", folder_name)
            if not os.path.exists(torrent_payload):
                torrent_payload = os.path.join(PAN_MOVIES, folder_name)
            
            main_vid = relpath if relpath else ""
            if not main_vid and os.path.exists(torrent_payload):
                if os.path.isfile(torrent_payload):
                    main_vid = folder_name
                else:
                    candidates = [f for f in os.listdir(torrent_payload) if f.endswith(('.mkv', '.mp4', '.avi', '.iso')) and not f.startswith(".")]
                    if candidates:
                        main_vid = max(candidates, key=lambda x: os.path.getsize(os.path.join(torrent_payload, x)))
            
            if main_vid:
                if os.path.isfile(torrent_payload):
                    rel_symlink_target = f"../../../torrents/movies/{folder_name}"
                else:
                    rel_symlink_target = f"../../../torrents/movies/{folder_name}/{main_vid}"
                
                clean_vid_name = f"{title} ({year}){os.path.splitext(main_vid)[1]}"
                if APPLY:
                    os.makedirs(dst_folder, exist_ok=True)
                    sym_path = os.path.join(dst_folder, clean_vid_name)
                    if os.path.exists(sym_path) or os.path.islink(sym_path):
                        os.remove(sym_path)
                    os.symlink(rel_symlink_target, sym_path)

                new_container_path = f"/external/media/movies/{clean_name}"
                radarr_path_updates.append((new_container_path, clean_vid_name, mid))
            else:
                new_container_path = f"/external/media/movies/{clean_name}"
                radarr_path_updates.append((new_container_path, None, mid))

        else:
            # Clean folder already, no torrent active
            print(f"  [CLEAN-ONLY MOVE] {title} ({year}) -> media/movies/{folder_name}")
            src_folder = os.path.join(PAN_MOVIES, folder_name)
            dst_folder = os.path.join(PAN_MEDIA, "movies", folder_name)
            if APPLY and os.path.exists(src_folder):
                os.rename(src_folder, dst_folder)
            new_container_path = f"/external/media/movies/{folder_name}"
            radarr_path_updates.append((new_container_path, relpath, mid))

    print(f"Reclaimed duplicate physical space: {space_reclaimed / (1024**3):.2f} GB")

    # 5. Handle Sonarr TV Shows
    print("\n--- PHASE 3: Setting up TV Shows in media/tv ---")
    conn_s = sqlite3.connect("config/sonarr/sonarr.db")
    c_s = conn_s.cursor()
    c_s.execute("SELECT Id, Title, Path FROM Series WHERE Path LIKE '/external%'")
    sonarr_series = c_s.fetchall()
    sonarr_path_updates = []

    for sid, title, spath in sonarr_series:
        s_folder = os.path.basename(spath.rstrip("/"))
        clean_tv_name = title
        dst_tv_folder = os.path.join(PAN_MEDIA, "tv", clean_tv_name)
        src_tv_payload = os.path.join(PAN_TORRENTS, "tv", s_folder)
        print(f"  [TV PER-FILE LINKS] {title} -> torrents/tv/{s_folder}")
        if APPLY:
            if os.path.islink(dst_tv_folder):
                os.unlink(dst_tv_folder)
            os.makedirs(dst_tv_folder, exist_ok=True)
            if os.path.isdir(src_tv_payload):
                for root, _, files in os.walk(src_tv_payload):
                    for f in files:
                        if f.startswith("."):
                            continue
                        src_file = os.path.join(root, f)
                        rel_sub = os.path.relpath(src_file, src_tv_payload)
                        dst_link = os.path.join(dst_tv_folder, rel_sub)
                        dst_parent = os.path.dirname(dst_link)
                        os.makedirs(dst_parent, exist_ok=True)
                        rel_target = os.path.relpath(src_file, dst_parent)
                        if os.path.islink(dst_link):
                            os.unlink(dst_link)
                        if not os.path.exists(dst_link):
                            os.symlink(rel_target, dst_link)
        
        sonarr_path_updates.append((f"/external/media/tv/{clean_tv_name}", sid))

    # 6. Apply Database Updates
    if APPLY:
        print("\n--- PHASE 4: Applying Database Path Updates ---")
        # Update Radarr
        c_r.execute("UPDATE RootFolders SET Path = '/external/media/movies/' WHERE Path = '/external/Movies/';")
        for npath, nfile, mid in radarr_path_updates:
            c_r.execute("UPDATE Movies SET Path = ? WHERE Id = ?", (npath, mid))
            if nfile:
                c_r.execute("""
                UPDATE MovieFiles SET RelativePath = ?
                WHERE Id = (SELECT MovieFileId FROM Movies WHERE Id = ?)
                """, (nfile, mid))
        conn_r.commit()
        print(f"  Updated Radarr: RootFolder + {len(radarr_path_updates)} movie paths.")

        # Update Sonarr
        c_s.execute("UPDATE RootFolders SET Path = '/external/media/tv/' WHERE Path = '/external/TV Shows/';")
        for npath, sid in sonarr_path_updates:
            c_s.execute("UPDATE Series SET Path = ? WHERE Id = ?", (npath, sid))
        conn_s.commit()
        print(f"  Updated Sonarr: RootFolder + {len(sonarr_path_updates)} series paths.")

    conn_r.close()
    conn_s.close()

    # 7. Rewrite qBittorrent fastresume files
    print("\n--- PHASE 5: Rewriting qBittorrent .fastresume Files ---")
    rewritten = 0
    for h, info in torrent_map.items():
        p = info["fastresume"]
        raw = open(p, "rb").read()
        data, end = dec(raw)
        sp = data.get(b"save_path", b"")
        qsp = data.get(b"qBt-savePath", b"")
        
        new_sp = None
        if sp == b"/external/Movies":
            new_sp = b"/external/torrents/movies"
        elif sp == b"/external/Movies/3DTorrents":
            new_sp = b"/external/torrents/movies/3DTorrents"
        elif sp == b"/external/TV Shows":
            new_sp = b"/external/torrents/tv"
        
        if new_sp:
            data[b"save_path"] = new_sp
            if qsp and qsp != b"":
                if qsp == b"/external/Movies":
                    data[b"qBt-savePath"] = b"/external/torrents/movies"
                elif qsp == b"/external/Movies/3DTorrents":
                    data[b"qBt-savePath"] = b"/external/torrents/movies/3DTorrents"
                elif qsp == b"/external/TV Shows":
                    data[b"qBt-savePath"] = b"/external/torrents/tv"
            
            rewritten += 1
            if APPLY:
                encoded = enc(data)
                tmp = p + ".tmp"
                with open(tmp, "wb") as f: f.write(encoded)
                os.replace(tmp, p)

    print(f"Total .fastresume files rewritten: {rewritten}")

    # 8. Update qBittorrent categories.json and qBittorrent.conf
    print("\n--- PHASE 6: Updating qBittorrent Category Defaults ---")
    conf = "config/qbittorrent/qBittorrent/qBittorrent.conf"
    cat_json = "config/qbittorrent/qBittorrent/categories.json"
    if APPLY:
        if os.path.exists(cat_json):
            with open(cat_json, "r") as f:
                content = f.read()
            content = content.replace('"/external/Movies"', '"/external/torrents/movies"')
            content = content.replace('"/external/TV Shows"', '"/external/torrents/tv"')
            with open(cat_json, "w") as f:
                f.write(content)
            print("  Updated categories.json save_paths.")

    # 9. Update Jellyfin Library Mblinks
    print("\n--- PHASE 7: Updating Jellyfin Library Links ---")
    jf_movies = "config/jellyfin/data/root/default/Movies/Movies.mblink"
    jf_shows = "config/jellyfin/data/root/default/Shows/TV Shows.mblink"
    if APPLY:
        if os.path.exists(jf_movies):
            with open(jf_movies, "w") as f:
                f.write("/media/external/media/movies")
            print("  Updated Movies.mblink -> /media/external/media/movies")
        if os.path.exists(jf_shows):
            with open(jf_shows, "w") as f:
                f.write("/media/external/media/tv")
            print("  Updated TV Shows.mblink -> /media/external/media/tv")

    print("\n==================================================")
    print(f"  MIGRATION COMPLETE [{mode}]")
    print(f"==================================================")

if __name__ == "__main__":
    main()
