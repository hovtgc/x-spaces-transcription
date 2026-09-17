"""Parse Hydra ID3 tags muxed into an X Spaces replay.

X's audio stack writes ID3v2 TXXX frames about once a second:

- JSONMetadata / TIT3  — NTP clock
- HydraParticipants    — people on stage (not listeners, not the host)
- HydraAudioLevel      — int array, one level per on-stage slot

Index mapping that works in practice:

- HydraAudioLevel[0]     = host
- HydraAudioLevel[i + 1] = HydraParticipants[i]
- level 0                = muted / silence
- level ≳ 8              = unmuted and making sound

Parse the **raw** yt-dlp file. ffmpeg remux to .aac / .wav drops every tag.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

LEVEL_ON = 8
KNOWN_DESC = {"JSONMetadata", "HydraParticipants", "HydraAudioLevel"}


def _decode_txxx_payload(payload: bytes) -> tuple[str, str] | None:
    if not payload:
        return None
    body = payload[1:] if payload[0] in (0, 1, 2, 3) else payload
    enc = payload[0] if payload[0] in (0, 1, 2, 3) else 0
    if enc in (1, 2):
        sep = b"\x00\x00"
        idx = body.find(sep)
        if idx < 0:
            return None
        raw_desc, raw_val = body[:idx], body[idx + 2 :]
        encoding = "utf-16" if enc == 1 else "utf-16-be"
        try:
            return (
                raw_desc.decode(encoding, "replace").rstrip("\x00"),
                raw_val.decode(encoding, "replace").rstrip("\x00"),
            )
        except Exception:
            return None
    desc, _, value = body.partition(b"\x00")
    try:
        return (
            desc.decode("utf-8", "replace"),
            value.rstrip(b"\x00").decode("utf-8", "replace"),
        )
    except Exception:
        return None


def _synchsafe(raw: bytes) -> int:
    n = 0
    for b in raw:
        n = (n << 7) | (b & 0x7F)
    return n


def _frame_sizes(raw: bytes) -> list[int]:
    """ID3v2.4 sizes are synchsafe (no high bits). High bits ⇒ v2.3 big-endian."""
    be = int.from_bytes(raw, "big")
    if any(b & 0x80 for b in raw):
        return [be]
    ss = _synchsafe(raw)
    return [ss] if ss == be else [ss, be]


def iter_txxx(data: bytes) -> Iterable[tuple[str, str]]:
    """Yield (description, value) for every TXXX frame that decodes."""
    i = 0
    n = len(data)
    while True:
        i = data.find(b"TXXX", i)
        if i < 0 or i + 10 > n:
            return
        sizes = [s for s in _frame_sizes(data[i + 4 : i + 8]) if 1 <= s <= min(n - (i + 10), 2_000_000)]
        chosen: tuple[int, str, str] | None = None
        fallback: tuple[int, str, str] | None = None
        for size in sizes:
            payload = data[i + 10 : i + 10 + size]
            decoded = _decode_txxx_payload(payload)
            if not decoded:
                continue
            desc, value = decoded
            if not (desc or value):
                continue
            hit = (size, desc, value)
            if desc in KNOWN_DESC:
                chosen = hit
                break
            if fallback is None:
                fallback = hit
        picked = chosen or fallback
        if picked is None:
            i += 4
            continue
        size, desc, value = picked
        yield desc, value
        i += 10 + size


def hydra_series(path: str | Path, host: str | None = None) -> list[dict]:
    """Return ~1 Hz samples of who was unmuted.

    Each row: {t, lv, guests, speaker, active}.
    `host` replaces the `"host"` token (handle without @).
    """
    data = Path(path).read_bytes()
    t0 = None
    participants: list[dict] = []
    rows: list[dict] = []
    last_ntp = None
    host_name = (host or "host").lstrip("@") or "host"

    for desc, value in iter_txxx(data):
        if desc == "JSONMetadata":
            try:
                ntp = float(json.loads(value)["ntp"])
            except Exception:
                continue
            if t0 is None:
                t0 = ntp
            last_ntp = ntp
        elif desc == "HydraParticipants":
            try:
                parsed = json.loads(value)
            except Exception:
                parsed = []
            participants = parsed if isinstance(parsed, list) else []
        elif desc == "HydraAudioLevel":
            try:
                levels = json.loads(value)
            except Exception:
                continue
            if not isinstance(levels, list) or last_ntp is None or t0 is None:
                continue
            t = round(last_ntp - t0, 3)
            active: list[str] = []
            if levels and _as_level(levels[0]) >= LEVEL_ON:
                active.append(host_name)
            for idx, person in enumerate(participants):
                lv = _as_level(levels[idx + 1]) if idx + 1 < len(levels) else 0
                if lv >= LEVEL_ON:
                    active.append(_person_name(person, idx))
            speaker = None
            if len(active) == 1:
                speaker = active[0]
            elif len(active) == 2:
                speaker = "both"
            elif len(active) > 2:
                speaker = "overlap"
            rows.append(
                {
                    "t": t,
                    "lv": levels,
                    "guests": participants,
                    "speaker": speaker,
                    "active": active,
                }
            )
    return rows


def _as_level(value: object) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0


def _person_name(person: object, idx: int) -> str:
    if isinstance(person, dict):
        name = person.get("UserName") or person.get("UserId")
        if isinstance(name, str) and name.strip():
            return name.lstrip("@")
    return f"guest-{idx}"


def regions(series: list[dict], gap: float = 1.5) -> list[dict]:
    """Collapse ~1 Hz samples into [start, end, speaker] runs."""
    out: list[dict] = []
    for row in series:
        sp = row.get("speaker") or "silence"
        if out and out[-1]["speaker"] == sp and row["t"] - out[-1]["end"] <= gap:
            out[-1]["end"] = row["t"]
        else:
            start = out[-1]["end"] if out else row["t"]
            out.append({"start": start, "end": row["t"], "speaker": sp})
    return out
