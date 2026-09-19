"""Chop a transcript into clips and highlights.

cues.json is the working set. A clip is [start, end] over that set.
A highlight is a cue worth jumping to — punchy, named, timed.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from space_tape.render import RenderError, format_ts, _at, _run, _ffmpeg

SKIP = {"silence", "unknown", "both", "overlap", "host", None, ""}

# Moments people actually clip. Generic enough for any Space; the demo
# (melted / insane / running for president) lights up on these.
KEYWORDS = (
    "melted",
    "insane",
    "sorry",
    "broke the internet",
    "half a million",
    "running for president",
    "decline",
    "choice",
    "announcement",
    "never seen",
    "servers",
    "straining",
    "historic",
    "broke twitter",
    "i am running",
    "i'm here",
    "teleprompter",
    "q and a",
    "q&a",
)


def parse_ts(value: str | float | int) -> float:
    """Accept 18, 18.5, 00:18, 1:02:03, 00:01:36.2."""
    if isinstance(value, (int, float)):
        t = float(value)
        if t < 0:
            raise ValueError("timestamp must be >= 0")
        return t
    raw = str(value).strip()
    if not raw:
        raise ValueError("empty timestamp")
    if re.fullmatch(r"\d+(\.\d+)?", raw):
        return float(raw)
    parts = raw.split(":")
    if not 2 <= len(parts) <= 3:
        raise ValueError(f"bad timestamp: {value!r}")
    try:
        nums = [float(p) for p in parts]
    except ValueError as exc:
        raise ValueError(f"bad timestamp: {value!r}") from exc
    if len(nums) == 2:
        m, s = nums
        return m * 60 + s
    h, m, s = nums
    return h * 3600 + m * 60 + s


def clip_cues(
    cues: list[dict],
    start: float,
    end: float,
    *,
    trim: bool = True,
) -> list[dict]:
    """Cues that overlap [start, end]. Optionally trim the first/last to the window."""
    lo, hi = (start, end) if end >= start else (end, start)
    out: list[dict] = []
    for cue in cues:
        a = float(cue.get("start") or 0)
        b = float(cue.get("end") or a)
        if b <= lo or a >= hi:
            continue
        row = {
            "start": max(a, lo) if trim else a,
            "end": min(b, hi) if trim else b,
            "speaker": cue.get("speaker") or "unknown",
            "text": cue.get("text") or "",
        }
        if "words" in cue:
            row["words"] = [
                w
                for w in cue["words"]
                if float(w.get("end") or 0) > lo and float(w.get("start") or 0) < hi
            ]
        out.append(row)
    return out


def quote_clip(cues: list[dict], *, source_url: str | None = None) -> str:
    """Markdown you can paste. Speaker first, timestamp, text. X link at the end."""
    lines: list[str] = []
    for cue in cues:
        text = (cue.get("text") or "").strip()
        if not text:
            continue
        speaker = _at(cue.get("speaker") or "unknown")
        stamp = format_ts(float(cue.get("start") or 0))
        lines.append(f"**{speaker}** [{stamp}] {text}")
        lines.append("")
    if source_url:
        lines.append(source_url)
        lines.append("")
    return "\n".join(lines)


def label_for(text: str, *, words: int = 6) -> str:
    clean = re.sub(r"\s+", " ", (text or "").strip())
    if not clean:
        return "clip"
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", clean) if s.strip()]
    chosen = ""
    for sentence in sentences:
        if any(kw in sentence.lower() for kw in KEYWORDS):
            chosen = sentence
            break
    if not chosen:
        chosen = sentences[0] if sentences else clean
    chosen = chosen.rstrip(".,;:")
    parts = chosen.split(" ")
    if len(parts) <= 10:
        return chosen
    return " ".join(parts[:words]).rstrip(".,;:") + "…"


def score_cue(cue: dict) -> float:
    text = (cue.get("text") or "").strip()
    speaker = cue.get("speaker")
    if not text or speaker in SKIP:
        return 0.0
    start = float(cue.get("start") or 0)
    end = float(cue.get("end") or start)
    dur = end - start
    if dur < 0.5:
        return 0.0
    lower = text.lower()
    kw_hits = sum(1 for kw in KEYWORDS if kw in lower)
    nwords = len(text.split())
    score = 1.0 + min(kw_hits, 2) * 3.0
    if nwords <= 8 and kw_hits:
        score += 2.0
    elif nwords <= 22:
        score += 1.4
    elif nwords > 50:
        score -= 2.0
    if "?" in text and nwords <= 30:
        score += 0.5
    if re.search(r"\bI am\b|\bI'm\b", text):
        score += 0.8
    if 2.0 <= dur <= 16.0:
        score += 0.5
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        if any(kw in sentence.lower() for kw in KEYWORDS) and len(sentence.split()) <= 14:
            score += 1.6
            break
    return score


def highlights(cues: list[dict], *, max_n: int = 8) -> list[dict]:
    """Pick punchy, named cues. Ordered by time, not score."""
    ranked = []
    for i, cue in enumerate(cues):
        s = score_cue(cue)
        if s <= 0:
            continue
        ranked.append((s, i, cue))
    ranked.sort(key=lambda row: (-row[0], row[1]))
    picked: list[dict] = []
    used: list[tuple[float, float]] = []
    for s, _i, cue in ranked:
        a = float(cue.get("start") or 0)
        b = float(cue.get("end") or a)
        if any(_overlap(a, b, u0, u1) > 0.5 * (b - a) for u0, u1 in used):
            continue
        text = (cue.get("text") or "").strip()
        picked.append(
            {
                "start": round(a, 3),
                "end": round(b, 3),
                "speaker": cue.get("speaker") or "unknown",
                "text": text,
                "label": label_for(text),
                "score": round(s, 3),
            }
        )
        used.append((a, b))
        if len(picked) >= max_n:
            break
    picked.sort(key=lambda h: h["start"])
    return picked


def write_clip(
    cues: list[dict],
    start: float,
    end: float,
    dest: str | Path,
    *,
    source_url: str | None = None,
    audio_src: str | Path | None = None,
    title: str = "clip",
) -> dict[str, Path]:
    chopped = clip_cues(cues, start, end)
    dest_path = Path(dest)
    dest_path.mkdir(parents=True, exist_ok=True)
    json_path = dest_path / "clip.json"
    md_path = dest_path / "clip.md"
    json_path.write_text(json.dumps(chopped, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    header = [
        f"# {title}",
        "",
        f"- Window: {format_ts(start)}–{format_ts(end)}",
    ]
    if source_url:
        header.append(f"- Space: {source_url}")
    header.append("")
    md_path.write_text("\n".join(header) + quote_clip(chopped, source_url=None), encoding="utf-8")
    written = {"cues": json_path, "transcript": md_path}
    if audio_src is not None:
        written["audio"] = write_audio_clip(audio_src, dest_path / "clip.mp3", start, end)
    return written


def write_audio_clip(src: str | Path, dest: str | Path, start: float, end: float) -> Path:
    ffmpeg = _ffmpeg()
    dest_path = Path(dest)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    if end <= start:
        raise RenderError("clip end must be after start")
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(src),
        "-ss",
        f"{start:.3f}",
        "-to",
        f"{end:.3f}",
        "-vn",
        "-ac",
        "1",
        "-b:a",
        "40k",
        str(dest_path),
    ]
    _run(cmd, "ffmpeg could not write clip.mp3")
    return dest_path


def load_cues(path: str | Path) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("cues.json must be a list")
    return data


def _overlap(a0: float, a1: float, b0: float, b1: float) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))
