from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from space_tape.hydra import hydra_series, iter_txxx, regions


def txxx(desc: str, value: str) -> bytes:
    body = b"\x03" + desc.encode("utf-8") + b"\x00" + value.encode("utf-8") + b"\x00"
    return b"TXXX" + len(body).to_bytes(4, "big") + b"\x00\x00" + body


def tagged_clip(*, synchsafe: bool = False) -> bytes:
    """~10s of Hydra ticks: host 0–4s, guest 4–8s, both 8–10s."""
    guest = {
        "ParticipantIndex": 1,
        "UserId": "1eWKyPLBZDnQA",
        "UserName": "djay44444",
        "SessionId": "595fec0b-252b-48af-a2f4-f356c4855e3b",
        "ProfileUrl": "https://pbs.twimg.com/profile_images/example.jpg",
    }
    t0 = 3998530786.0
    frames = bytearray(b"ID3\x04\x00\x00\x00\x00\x00\x00")
    for i in range(11):
        ntp = t0 + i
        if i < 4:
            levels = [78]
        elif i < 8:
            levels = [0, 63]
        else:
            levels = [54, 61]
        frames += _maybe_synchsafe(
            txxx("JSONMetadata", json.dumps({"HydraVersion": 4, "ntp": ntp})),
            synchsafe,
        )
        frames += _maybe_synchsafe(
            txxx("HydraParticipants", json.dumps([guest])),
            synchsafe,
        )
        frames += _maybe_synchsafe(
            txxx("HydraAudioLevel", json.dumps(levels)),
            synchsafe,
        )
    return bytes(frames)


def _maybe_synchsafe(frame: bytes, synchsafe: bool) -> bytes:
    if not synchsafe:
        return frame
    size = int.from_bytes(frame[4:8], "big")
    ss = bytes(
        [
            (size >> 21) & 0x7F,
            (size >> 14) & 0x7F,
            (size >> 7) & 0x7F,
            size & 0x7F,
        ]
    )
    return frame[:4] + ss + frame[8:]


def test_iter_txxx_roundtrip(tmp_path: Path | None = None) -> None:
    data = tagged_clip()
    descs = [d for d, _ in iter_txxx(data)]
    assert descs.count("JSONMetadata") == 11
    assert descs.count("HydraParticipants") == 11
    assert descs.count("HydraAudioLevel") == 11


def test_host_is_slot_zero(tmp_path: Path | None = None) -> None:
    path = Path(__file__).parent / "fixtures"
    path.mkdir(exist_ok=True)
    clip = path / "tagged_clip.bin"
    clip.write_bytes(tagged_clip())
    series = hydra_series(clip, host="notpierce69")
    assert series[0]["speaker"] == "notpierce69"
    assert series[0]["active"] == ["notpierce69"]
    assert series[5]["speaker"] == "djay44444"
    assert series[9]["speaker"] == "both"
    assert "notpierce69" in series[9]["active"]
    assert "djay44444" in series[9]["active"]


def test_regions_collapse() -> None:
    series = hydra_series(_write_tmp(tagged_clip()), host="notpierce69")
    runs = regions(series)
    speakers = [r["speaker"] for r in runs]
    assert speakers == ["notpierce69", "djay44444", "both"]
    for run in runs:
        assert run["end"] >= run["start"]


def test_synchsafe_id3v24() -> None:
    series = hydra_series(_write_tmp(tagged_clip(synchsafe=True)), host="notpierce69")
    assert len(series) == 11
    assert series[0]["speaker"] == "notpierce69"
    assert series[5]["speaker"] == "djay44444"


def test_empty_file_is_empty_series(tmp_path: Path | None = None) -> None:
    series = hydra_series(_write_tmp(b"not an id3 file at all"))
    assert series == []


def _write_tmp(data: bytes) -> Path:
    dest = Path(__file__).parent / "fixtures"
    dest.mkdir(exist_ok=True)
    path = dest / "tmp.bin"
    path.write_bytes(data)
    return path


if __name__ == "__main__":
    test_iter_txxx_roundtrip()
    test_host_is_slot_zero()
    test_regions_collapse()
    test_synchsafe_id3v24()
    test_empty_file_is_empty_series()
    print("ok")
