#!/usr/bin/env python3
"""Merge historical Overseerr request history into the live Seerr database.

Sources (read-only, snapshotted to a temp dir before reading):
  - config/overseerr/db/db.sqlite3       (retired Overseerr, 45 media, 10 requests)
  - ~/Movies/overseerr/db/db.sqlite3     (older Overseerr copy, 43 media, same 10 requests)

Target:
  - config/seerr/db/db.sqlite3           (live Seerr, container "seerr")

Behaviour:
  - Dry-run by default. The full merge runs against a temp copy of the target and
    prints every action. The live target is never opened.
  - --apply refuses to run while the "seerr" container is running. On macOS +
    OrbStack/VirtioFS, host-side writes to a WAL-mode DB that a container also
    has open desynchronize the -shm index and corrupt B-tree pages.
  - --apply writes a timestamped backup next to the target with the SQLite
    online backup API, then merges in one IMMEDIATE transaction. It runs
    PRAGMA integrity_check and PRAGMA foreign_key_check before COMMIT and rolls
    back on any failure.
  - Users are matched by lower-cased email. Media rows are matched by
    (mediaType, tmdbId). Requests are deduplicated by
    (mediaId, is4k, requestedById), so re-runs insert nothing (idempotent).
  - media.createdAt is moved back to the Overseerr value only when Overseerr's
    timestamp is older.
  - Missing media_request rows are inserted with the original createdAt,
    updatedAt, status, is4k, type, requestedById, modifiedById, and every other
    column that exists in both schemas. TV requests also copy season_request rows.
  - Users are never created. A request whose requester email has no Seerr user
    is skipped and reported.

Usage (run on the Sol host from the repo root):
  python3 scripts/merge_overseerr_history.py                 # dry-run
  docker compose stop seerr
  python3 scripts/merge_overseerr_history.py --apply
  docker compose start seerr
"""

from __future__ import annotations

import argparse
import datetime as dt
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCES = [
    REPO_ROOT / "config" / "overseerr" / "db" / "db.sqlite3",
    Path.home() / "Movies" / "overseerr" / "db" / "db.sqlite3",
]
DEFAULT_TARGET = REPO_ROOT / "config" / "seerr" / "db" / "db.sqlite3"
DEFAULT_CONTAINER = "seerr"

# Columns that are remapped or regenerated instead of copied verbatim.
REQUEST_REMAPPED = {"id", "mediaId", "requestedById", "modifiedById"}
MEDIA_REMAPPED = {"id"}
SEASON_REMAPPED = {"id", "requestId"}

DATETIME_FORMATS = (
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S",
)


class MergeError(RuntimeError):
    pass


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def log(msg: str = "") -> None:
    print(msg, flush=True)


def parse_ts(value):
    """Parse a TypeORM SQLite datetime string. Returns None if unparsable."""
    if value is None:
        return None
    text = str(value).strip().replace("Z", "")
    if "+" in text[10:]:
        text = text[: 10 + text[10:].index("+")]
    for fmt in DATETIME_FORMATS:
        try:
            return dt.datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def is_sqlite(path: Path) -> bool:
    try:
        with open(path, "rb") as fh:
            return fh.read(16).startswith(b"SQLite format 3")
    except OSError:
        return False


def snapshot(db: Path, workdir: Path, label: str) -> Path:
    """Copy db plus its -wal into workdir. SQLite replays the WAL on open.

    The -shm file is never copied. SQLite rebuilds it from the WAL.
    """
    dest_dir = workdir / label
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / db.name
    shutil.copy2(db, dest)
    wal = db.with_name(db.name + "-wal")
    if wal.exists():
        shutil.copy2(wal, dest.with_name(dest.name + "-wal"))
    return dest


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


def table_info(conn: sqlite3.Connection, table: str) -> dict:
    """Return {column: (notnull, default, pk)} in declaration order."""
    cols = {}
    for _cid, name, _type, notnull, dflt, pk in conn.execute(
        f'PRAGMA table_info("{table}")'
    ):
        cols[name] = (bool(notnull), dflt, bool(pk))
    if not cols:
        raise MergeError(f"table {table!r} not found")
    return cols


def insert_row(conn, table: str, tcols: dict, values: dict) -> int:
    names = [c for c in tcols if c in values and c != "id"]
    missing = [
        c
        for c, (notnull, dflt, pk) in tcols.items()
        if notnull and dflt is None and not pk and c not in values
    ]
    if missing:
        raise MergeError(
            f"{table}: target NOT NULL columns without default are absent "
            f"from source: {missing}"
        )
    cols_sql = ", ".join(f'"{c}"' for c in names)
    marks = ", ".join("?" for _ in names)
    cur = conn.execute(
        f'INSERT INTO "{table}" ({cols_sql}) VALUES ({marks})',
        [values[c] for c in names],
    )
    return cur.lastrowid


def container_running(name: str) -> bool:
    """True if running. Raises MergeError if the Docker CLI cannot answer."""
    docker = shutil.which("docker")
    if docker is None:
        raise MergeError("docker CLI not found. Cannot prove the container is stopped.")
    res = subprocess.run(
        [docker, "ps", "--filter", f"name=^{name}$", "--format", "{{.Names}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if res.returncode != 0:
        raise MergeError(f"docker ps failed: {res.stderr.strip()}")
    return name in res.stdout.split()


def check_integrity(conn: sqlite3.Connection, label: str) -> None:
    rows = [r[0] for r in conn.execute("PRAGMA integrity_check")]
    if rows != ["ok"]:
        raise MergeError(f"{label}: integrity_check failed: {rows[:5]}")
    fk = conn.execute("PRAGMA foreign_key_check").fetchall()
    if fk:
        raise MergeError(f"{label}: foreign_key_check failed: {fk[:5]}")


# ----------------------------------------------------------------------------
# Source loading
# ----------------------------------------------------------------------------
def load_source(path: Path, label: str) -> dict:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    try:
        check_integrity(conn, f"source {label}")
        src = {
            "label": label,
            "users": {
                r["id"]: (r["email"] or "").strip().lower()
                for r in conn.execute("SELECT id, email FROM user")
            },
            "media": {r["id"]: dict(r) for r in conn.execute("SELECT * FROM media")},
            "requests": [
                dict(r)
                for r in conn.execute("SELECT * FROM media_request ORDER BY id")
            ],
            "seasons": defaultdict(list),
        }
        if table_exists(conn, "season_request"):
            for r in conn.execute("SELECT * FROM season_request ORDER BY id"):
                src["seasons"][r["requestId"]].append(dict(r))
        return src
    finally:
        conn.close()


# ----------------------------------------------------------------------------
# Merge (runs identically on the dry-run copy and on the live target)
# ----------------------------------------------------------------------------
def merge(conn: sqlite3.Connection, sources: list) -> dict:
    stats = defaultdict(int)
    t_media_cols = table_info(conn, "media")
    t_req_cols = table_info(conn, "media_request")
    t_season_cols = (
        table_info(conn, "season_request")
        if table_exists(conn, "season_request")
        else None
    )

    t_users = {}
    for uid, email in conn.execute("SELECT id, email FROM user"):
        if email:
            t_users[email.strip().lower()] = uid

    t_media = {}
    for mid, mtype, tmdb, created in conn.execute(
        "SELECT id, mediaType, tmdbId, createdAt FROM media"
    ):
        t_media[(mtype, tmdb)] = [mid, created]

    t_req_keys = set()
    for mid, is4k, uid in conn.execute(
        "SELECT mediaId, is4k, requestedById FROM media_request"
    ):
        t_req_keys.add((mid, int(bool(is4k)), uid))

    log("Target users by email:")
    for email, uid in sorted(t_users.items(), key=lambda kv: kv[1]):
        log(f"  id={uid:<3} {email}")
    log()

    for src in sources:
        label = src["label"]
        log(f"--- Source: {label} ---")
        log(
            f"  media={len(src['media'])} requests={len(src['requests'])} "
            f"users={len(src['users'])}"
        )

        # 1. media.createdAt backdating for every matched media row.
        for smedia in src["media"].values():
            key = (smedia["mediaType"], smedia["tmdbId"])
            if key not in t_media:
                stats["media_absent_in_target"] += 1
                continue
            tid, tcreated = t_media[key]
            s_ts, t_ts = parse_ts(smedia.get("createdAt")), parse_ts(tcreated)
            if s_ts is None or t_ts is None:
                log(
                    f"  WARN media {key}: unparsable createdAt "
                    f"src={smedia.get('createdAt')!r} tgt={tcreated!r}"
                )
                stats["media_createdAt_unparsable"] += 1
                continue
            if s_ts < t_ts:
                conn.execute(
                    "UPDATE media SET createdAt=? WHERE id=?",
                    (smedia["createdAt"], tid),
                )
                t_media[key][1] = smedia["createdAt"]
                log(
                    f"  UPDATE media id={tid} {key[0]} tmdb={key[1]} createdAt "
                    f"{tcreated} -> {smedia['createdAt']}"
                )
                stats["media_createdAt_backdated"] += 1

        # 2. media_request inserts.
        for req in src["requests"]:
            smedia = src["media"].get(req["mediaId"])
            if smedia is None:
                log(f"  SKIP request src_id={req['id']}: orphan mediaId={req['mediaId']}")
                stats["request_skipped_orphan"] += 1
                continue
            key = (smedia["mediaType"], smedia["tmdbId"])
            r_email = src["users"].get(req["requestedById"], "")
            m_email = src["users"].get(req.get("modifiedById"), "")
            desc = (
                f"src_id={req['id']} {key[0]} tmdb={key[1]} status={req.get('status')} "
                f"is4k={req.get('is4k')} createdAt={req.get('createdAt')} by={r_email or '?'}"
            )

            t_uid = t_users.get(r_email)
            if t_uid is None:
                log(f"  SKIP request {desc}: requester email not in Seerr")
                stats["request_skipped_no_user"] += 1
                continue

            if key not in t_media:
                values = {c: v for c, v in smedia.items() if c not in MEDIA_REMAPPED}
                new_mid = insert_row(conn, "media", t_media_cols, values)
                t_media[key] = [new_mid, smedia.get("createdAt")]
                log(f"  INSERT media id={new_mid} {key[0]} tmdb={key[1]} (needed by request)")
                stats["media_inserted"] += 1
            t_mid = t_media[key][0]

            dedupe = (t_mid, int(bool(req.get("is4k"))), t_uid)
            if dedupe in t_req_keys:
                log(f"  KEEP request {desc}: already present in Seerr")
                stats["request_already_present"] += 1
                continue

            values = {c: v for c, v in req.items() if c not in REQUEST_REMAPPED}
            values["mediaId"] = t_mid
            values["requestedById"] = t_uid
            if "modifiedById" in t_req_cols:
                values["modifiedById"] = t_users.get(m_email) if m_email else None
            new_rid = insert_row(conn, "media_request", t_req_cols, values)
            t_req_keys.add(dedupe)
            log(f"  INSERT media_request id={new_rid} {desc}")
            stats["request_inserted"] += 1

            seasons = src["seasons"].get(req["id"], [])
            if seasons and t_season_cols is None:
                raise MergeError("target has no season_request table for a TV request")
            for season in seasons:
                s_values = {c: v for c, v in season.items() if c not in SEASON_REMAPPED}
                s_values["requestId"] = new_rid
                insert_row(conn, "season_request", t_season_cols, s_values)
                stats["season_request_inserted"] += 1
        log()
    return stats


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--source", action="append", type=Path,
                    help="Overseerr db.sqlite3 (repeatable, default: both known copies)")
    ap.add_argument("--target", type=Path, default=DEFAULT_TARGET,
                    help=f"Seerr db.sqlite3 (default: {DEFAULT_TARGET})")
    ap.add_argument("--container", default=DEFAULT_CONTAINER,
                    help="Seerr container name that must be stopped for --apply")
    ap.add_argument("--apply", action="store_true",
                    help="Write to the live target (default is dry-run)")
    args = ap.parse_args()

    sources = args.source or DEFAULT_SOURCES
    mode = "APPLY" if args.apply else "DRY-RUN"
    log("=" * 64)
    log(f" Overseerr -> Seerr history merge [{mode}]")
    log("=" * 64)

    target = args.target.expanduser().resolve()
    if not is_sqlite(target):
        log(f"ERROR: target is missing or not SQLite: {target}")
        return 1

    with tempfile.TemporaryDirectory(prefix="overseerr_merge_") as tmp:
        workdir = Path(tmp)

        loaded = []
        for i, src_path in enumerate(sources):
            src_path = src_path.expanduser().resolve()
            if not is_sqlite(src_path):
                log(f"WARN: skipping missing or non-SQLite source: {src_path}")
                continue
            snap = snapshot(src_path, workdir, f"src{i}")
            loaded.append(load_source(snap, str(src_path)))
        if not loaded:
            log("ERROR: no readable Overseerr source")
            return 1

        if args.apply:
            try:
                if container_running(args.container):
                    log(f"REFUSED: container {args.container!r} is running. "
                        f"Run: docker compose stop {args.container}")
                    return 2
            except MergeError as exc:
                log(f"REFUSED: {exc}")
                return 2
            stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
            backup = target.with_name(f"{target.name}.pre-overseerr-merge-{stamp}.bak")
            conn = sqlite3.connect(str(target), isolation_level=None)
            with sqlite3.connect(str(backup)) as bconn:
                conn.backup(bconn)
            log(f"Backup written: {backup}")
        else:
            log("Target snapshot copied to a temp dir. The live target is not opened.")
            log("Note: the copy is not atomic while seerr runs. Re-run before --apply.")
            conn = sqlite3.connect(str(snapshot(target, workdir, "target")),
                                   isolation_level=None)

        try:
            conn.execute("PRAGMA foreign_keys=ON")
            check_integrity(conn, "target (before)")
            conn.execute("BEGIN IMMEDIATE")
            try:
                stats = merge(conn, loaded)
                check_integrity(conn, "target (after, uncommitted)")
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
            if args.apply:
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            counts = {
                t: conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
                for t in ("user", "media", "media_request")
            }
        except (MergeError, sqlite3.Error) as exc:
            log(f"ERROR: {exc}. Nothing was committed.")
            return 1
        finally:
            conn.close()

    log("Summary:")
    for k in sorted(stats):
        log(f"  {k:<32} {stats[k]}")
    log(f"  target rows after merge         {counts}")
    if not args.apply:
        log("\nDRY-RUN complete. Stop seerr and pass --apply to write.")
    else:
        log(f"\nAPPLY complete. Start seerr: docker compose start {args.container}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
