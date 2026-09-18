from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from space_tape.hydra import regions
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


def test_silence_blip_at_midpoint_keeps_speaker() -> None:
    # Hydra drops to 0 between words; a 1 s blip under the midpoint must not
    # turn a line the speaker owns into `unknown`.
    regions = [
        {"start": 10.0, "end": 12.5, "speaker": "suavecito585"},
        {"start": 12.5, "end": 13.5, "speaker": "silence"},
        {"start": 13.5, "end": 16.0, "speaker": "suavecito585"},
    ]
    cues = [{"start": 10.0, "end": 16.0, "text": "a whole sentence"}]
    out = attach_speakers(cues, regions)
    assert out[0]["speaker"] == "suavecito585"


def test_majority_overlap_wins() -> None:
    regions = [
        {"start": 0.0, "end": 1.5, "speaker": "AunySillyMe"},
        {"start": 1.5, "end": 6.0, "speaker": "suavecito585"},
    ]
    cues = [{"start": 1.0, "end": 6.0, "text": "mostly suave"}]
    out = attach_speakers(cues, regions)
    assert out[0]["speaker"] == "suavecito585"


def test_zero_length_cue_uses_its_second() -> None:
    regions = [{"start": 4.0, "end": 6.0, "speaker": "djay44444"}]
    cues = [{"start": 5.0, "end": 5.0, "text": "Okay."}]
    out = attach_speakers(cues, regions)
    assert out[0]["speaker"] == "djay44444"


def test_short_cue_keeps_the_speaker_covering_it() -> None:
    # Widening is a fallback only: b covers the whole cue, a never touches it.
    regions = [
        {"start": 0.0, "end": 1.0, "speaker": "a"},
        {"start": 1.0, "end": 1.2, "speaker": "b"},
        {"start": 1.2, "end": 2.0, "speaker": "a"},
    ]
    out = attach_speakers([{"start": 1.05, "end": 1.15, "text": "x"}], regions)
    assert out[0]["speaker"] == "b"


def test_hydra_clock_reversal_does_not_hide_covering_region() -> None:
    # regions() over a clock that jumps back: a=[0,200], b=[200,1], c=[1,2].
    series = [{"t": float(t), "speaker": "a"} for t in range(201)]
    series += [{"t": 1.0, "speaker": "b"}, {"t": 2.0, "speaker": "c"}]
    out = attach_speakers([{"start": 100.0, "end": 101.0, "text": "x"}], regions(series))
    assert out[0]["speaker"] == "a"


def test_empty_regions() -> None:
    cues = [{"start": 0.0, "end": 1.0, "text": "hi"}]
    out = attach_speakers(cues, [])
    assert out[0]["speaker"] == "unknown"


if __name__ == "__main__":
    test_midpoint_assignment()
    test_silence_becomes_unknown()
    test_silence_blip_at_midpoint_keeps_speaker()
    test_majority_overlap_wins()
    test_zero_length_cue_uses_its_second()
    test_short_cue_keeps_the_speaker_covering_it()
    test_hydra_clock_reversal_does_not_hide_covering_region()
    test_empty_regions()
    print("ok")
