"""Download a recorded X Space without remuxing.

KEEP the mpegts/m4a. Do not remux — remux strips Hydra ID3 tags.
yt-dlp follows tweet → Space replay by itself.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse

SPACES_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:x|twitter)\.com/i/spaces/([A-Za-z0-9]+)",
    re.I,
)
STATUS_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:x|twitter)\.com/([A-Za-z0-9_]+)/status/(\d+)",
    re.I,
)


class DownloadError(RuntimeError):
    """yt-dlp found no media, or the binary is missing."""


def parse_url(url: str) -> dict:
    """Accept spaces links, status links, twitter.com equivalents."""
    raw = url.strip()
    if not raw:
        raise DownloadError("Empty URL.")
    spaces = SPACES_RE.search(raw)
    if spaces:
        space_id = spaces.group(1)
        return {
            "kind": "space",
            "url": f"https://x.com/i/spaces/{space_id}",
            "space_id": space_id,
            "status_id": None,
            "host": None,
        }
    status = STATUS_RE.search(raw)
    if status:
        handle, status_id = status.group(1), status.group(2)
        host = None if handle.lower() == "i" else handle
        return {
            "kind": "status",
            "url": f"https://x.com/{handle}/status/{status_id}",
            "space_id": None,
            "status_id": status_id,
            "host": host,
        }
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    host = (parsed.hostname or "").lower()
    if host in {"x.com", "www.x.com", "twitter.com", "www.twitter.com", "mobile.twitter.com"}:
        return {
            "kind": "url",
            "url": raw if "://" in raw else f"https://{raw}",
            "space_id": None,
            "status_id": None,
            "host": None,
        }
    raise DownloadError(
        "Not an X Spaces or status URL. "
        "Expected x.com/i/spaces/<id> or x.com/<user>/status/<id>."
    )


def download(url: str, out_dir: str | Path) -> Path:
    """Fetch the replay with yt-dlp. Refuses remux. Returns the raw file."""
    ytdlp = shutil.which("yt-dlp")
    if not ytdlp:
        raise DownloadError(
            "yt-dlp is not on PATH. Install it: pip install yt-dlp"
        )
    dest = Path(out_dir)
    dest.mkdir(parents=True, exist_ok=True)
    pattern = str(dest / "replay.%(ext)s")
    cmd = [
        ytdlp,
        "-f",
        "bestaudio/best",
        "--hls-use-mpegts",
        # ffmpeg's HLS demuxer and yt-dlp's FixupM3u8 remux both drop the
        # ID3 frames. Native fragments + no fixup keeps Hydra intact.
        "--downloader",
        "m3u8:native",
        "--fixup",
        "never",
        # With --no-part a re-run into the same dir otherwise appends a second
        # full copy onto the existing replay (and Hydra's clock resets mid-file).
        "--force-overwrites",
        "--no-part",
        "-o",
        pattern,
        url,
    ]
    try:
        proc = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise DownloadError("yt-dlp is not on PATH.") from exc
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip() or "yt-dlp failed"
        if _no_media(err):
            raise DownloadError(
                "No media. The Space was not recorded, or the replay expired. "
                "space-tape does not join live Spaces."
            )
        raise DownloadError(err.splitlines()[-1][:400])
    found = _find_replay(dest)
    if found is None:
        raise DownloadError(
            "No media. The Space was not recorded, or the replay expired. "
            "space-tape does not join live Spaces."
        )
    return found


def _no_media(err: str) -> bool:
    lowered = err.lower()
    needles = (
        "no video",
        "no media",
        "requested format is not available",
        "does not exist",
        "unavailable",
        "private",
    )
    return any(n in lowered for n in needles)


def _find_replay(dest: Path) -> Path | None:
    candidates = sorted(
        [p for p in dest.glob("replay.*") if p.is_file() and p.stat().st_size > 0],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    skip = {".json", ".info", ".description", ".jpg", ".png", ".webp"}
    for path in candidates:
        if path.suffix.lower() in skip:
            continue
        return path
    return None
