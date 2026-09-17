from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from space_tape.render import format_ts, transcript_md


def test_format_ts() -> None:
    assert format_ts(5.004) == "00:00:05"
    assert format_ts(96) == "00:01:36"
    assert format_ts(3723) == "01:02:03"


def test_transcript_keeps_x_url() -> None:
    cues = [
        {
            "start": 5.004,
            "end": 7.003,
            "speaker": "notpierce69",
            "text": "Hey DJ, I don't think anyone else is gonna show up.",
        }
    ]
    md = transcript_md(
        cues,
        source_url="https://x.com/i/spaces/1pKdRDlVbRrJW",
        posted_url="https://x.com/notpierce69/status/2100117423017906497",
        title="Explorer Initiation",
        speakers=["notpierce69", "djay44444"],
    )
    assert "https://x.com/i/spaces/1pKdRDlVbRrJW" in md
    assert "https://x.com/notpierce69/status/2100117423017906497" in md
    assert "**[00:00:05] @notpierce69**" in md
    assert "@djay44444" in md


if __name__ == "__main__":
    test_format_ts()
    test_transcript_keeps_x_url()
    print("ok")
