from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from space_tape import download as dl


def _captured_cmd() -> list[str]:
    seen: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        seen.append(cmd)
        out = Path(cmd[cmd.index("-o") + 1].replace("%(ext)s", "m4a"))
        out.write_bytes(b"ID3")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    with tempfile.TemporaryDirectory() as tmp, \
            mock.patch.object(dl.shutil, "which", return_value="/usr/bin/yt-dlp"), \
            mock.patch.object(dl.subprocess, "run", side_effect=fake_run):
        dl.download("https://x.com/i/spaces/1pKdRDlVbRrJW", tmp)
    return seen[0]


def test_download_keeps_hydra_id3() -> None:
    # ffmpeg's HLS demuxer and yt-dlp's FixupM3u8 both strip the ID3 frames.
    cmd = _captured_cmd()
    assert cmd[cmd.index("--downloader") + 1] == "m3u8:native"
    assert cmd[cmd.index("--fixup") + 1] == "never"


def test_download_rerun_overwrites() -> None:
    # --no-part + native HLS otherwise appends a second copy on a re-run.
    assert "--force-overwrites" in _captured_cmd()


if __name__ == "__main__":
    test_download_keeps_hydra_id3()
    test_download_rerun_overwrites()
    print("ok")
