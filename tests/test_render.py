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
    assert "\n**@notpierce69** [00:00:05] " in md
    assert "@djay44444" in md


def test_transcript_merges_same_speaker_turns() -> None:
    cues = [
        {"start": 1.0, "end": 2.0, "speaker": "a", "text": "One."},
        {"start": 2.0, "end": 3.0, "speaker": "a", "text": "Two."},
        {"start": 3.0, "end": 4.0, "speaker": "b", "text": "Three."},
        {"start": 4.0, "end": 5.0, "speaker": "a", "text": "Four."},
    ]
    md = transcript_md(cues, source_url="https://x.com/i/spaces/x")
    body = [line for line in md.splitlines() if line.startswith("**")]
    assert body == [
        "**@a** [00:00:01] One. Two.",
        "**@b** [00:00:03] Three.",
        "**@a** [00:00:04] Four.",
    ]


if __name__ == "__main__":
    test_format_ts()
    test_transcript_keeps_x_url()
    test_transcript_merges_same_speaker_turns()
    print("ok")
