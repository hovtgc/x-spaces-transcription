"""Attach Hydra speakers onto Whisper cues.

For each Whisper cue [start, end, text], pick the Hydra region that covers
the midpoint. That is the whole diarizer: you are reading who X thought was
unmuted, not guessing voices.
"""

from __future__ import annotations


def attach_speakers(cues: list[dict], regions: list[dict]) -> list[dict]:
    out: list[dict] = []
    j = 0
    n = len(regions)
    for cue in cues:
        start = float(cue.get("start") or 0)
        end = float(cue.get("end") or start)
        mid = (start + end) / 2
        while j + 1 < n and regions[j]["end"] < mid:
            j += 1
        speaker = regions[j]["speaker"] if j < n else "unknown"
        if speaker in ("silence", None, ""):
            speaker = "unknown"
        out.append({**cue, "start": start, "end": end, "speaker": speaker})
    return out
