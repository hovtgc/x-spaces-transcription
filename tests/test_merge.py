from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from space_tape.merge import attach_speakers


def test_midpoint_assignment() -> None:
    regions = [
        {"start": 0.0, "end": 4.0, "speaker": "notpierce69"},
        {"start": 4.0, "end": 8.0, "speaker": "djay44444"},
        {"start": 8.0, "end": 10.0, "speaker": "both"},
    ]
    cues = [
        {"start": 1.0, "end": 3.0, "text": "Hey DJ"},
        {"start": 4.5, "end": 6.5, "text": "yeah"},
        {"start": 8.2, "end": 9.1, "text": "overlap"},
    ]
    out = attach_speakers(cues, regions)
    assert [c["speaker"] for c in out] == ["notpierce69", "djay44444", "both"]


def test_silence_becomes_unknown() -> None:
    regions = [{"start": 0.0, "end": 5.0, "speaker": "silence"}]
    cues = [{"start": 1.0, "end": 2.0, "text": "hmm"}]
    out = attach_speakers(cues, regions)
    assert out[0]["speaker"] == "unknown"


def test_empty_regions() -> None:
    cues = [{"start": 0.0, "end": 1.0, "text": "hi"}]
    out = attach_speakers(cues, [])
    assert out[0]["speaker"] == "unknown"


if __name__ == "__main__":
    test_midpoint_assignment()
    test_silence_becomes_unknown()
    test_empty_regions()
    print("ok")
