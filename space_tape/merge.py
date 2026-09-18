"""Attach Hydra speakers onto Whisper cues.

For each Whisper cue [start, end, text], pick the Hydra speaker who was
unmuted for the largest share of the cue. That is the whole diarizer: you are
reading who X thought was unmuted, not guessing voices.

Not the midpoint: Hydra ticks ~1 Hz and drops to level 0 between words, so a
talker's run is peppered with <=1 s "silence" blips. A midpoint that lands in
one would mark a line `unknown` that the speaker plainly owns.
"""

from __future__ import annotations

from bisect import bisect_left
from collections import defaultdict
from itertools import accumulate

FALLBACK_SPAN = 1.0  # a cue that overlaps no voiced region looks at its own second


def attach_speakers(cues: list[dict], regions: list[dict]) -> list[dict]:
    voiced = sorted(
        (
            r
            for r in regions
            if r.get("speaker") not in ("silence", None, "") and r["end"] > r["start"]
        ),
        key=lambda r: r["start"],
    )
    starts = [r["start"] for r in voiced]
    # reach[i] = latest end among voiced[0..i]: once it is <= lo, nothing at or
    # before i can overlap, even if a Hydra clock jump left regions out of order.
    reach = list(accumulate((r["end"] for r in voiced), max))

    def shares(lo: float, hi: float) -> dict[str, float]:
        share: dict[str, float] = defaultdict(float)
        i = bisect_left(starts, hi)
        while i > 0 and reach[i - 1] > lo:
            i -= 1
            r = voiced[i]
            overlap = min(hi, r["end"]) - max(lo, r["start"])
            if overlap > 0:
                share[r["speaker"]] += overlap
        return share

    out: list[dict] = []
    for cue in cues:
        start = float(cue.get("start") or 0)
        end = float(cue.get("end") or start)
        share = shares(start, end) if end > start else {}
        if not share:
            mid = (start + end) / 2
            share = shares(mid - FALLBACK_SPAN / 2, mid + FALLBACK_SPAN / 2)
        speaker = max(share, key=share.get) if share else "unknown"
        out.append({**cue, "start": start, "end": end, "speaker": speaker})
    return out
