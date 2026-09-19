"""Write cues.json, transcript.md, and a speech-bitrate mp3."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


class RenderError(RuntimeError):
    pass


def write_outputs(
    out_dir: str | Path,
    *,
    cues: list[dict],
    source_url: str,
    posted_url: str | None = None,
    title: str = "Space",
    audio_src: str | Path | None = None,
    speakers: list[str] | None = None,
) -> dict[str, Path]:
    dest = Path(out_dir)
    dest.mkdir(parents=True, exist_ok=True)
    json_path = dest / "cues.json"
    md_path = dest / "transcript.md"
    json_path.write_text(
        json.dumps(_public_cues(cues), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(
        transcript_md(
            cues,
            source_url=source_url,
            posted_url=posted_url,
            title=title,
            speakers=speakers,
        ),
        encoding="utf-8",
    )
    written: dict[str, Path] = {"cues": json_path, "transcript": md_path}
    from space_tape.clip import highlights as _highlights

    hits = _highlights(_public_cues(cues))
    hl_path = dest / "highlights.json"
    hl_path.write_text(json.dumps(hits, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    written["highlights"] = hl_path
    if audio_src is not None:
        mp3 = write_mp3(audio_src, dest / "audio.mp3")
        written["audio"] = mp3
    return written


def _public_cues(cues: list[dict]) -> list[dict]:
    out = []
    for cue in cues:
        row = {
            "start": round(float(cue.get("start") or 0), 3),
            "end": round(float(cue.get("end") or 0), 3),
            "speaker": cue.get("speaker") or "unknown",
            "text": cue.get("text") or "",
        }
        if "words" in cue:
            row["words"] = cue["words"]
        out.append(row)
    return out


def transcript_md(
    cues: list[dict],
    *,
    source_url: str,
    posted_url: str | None = None,
    title: str = "Space",
    speakers: list[str] | None = None,
) -> str:
    names = speakers or _speakers_of(cues)
    lines = [
        f"# {title}",
        "",
        f"- Space: {source_url}",
    ]
    if posted_url and posted_url != source_url:
        lines.append(f"- Posted: {posted_url}")
    if names:
        shown = ", ".join(_at(n) for n in names)
        lines.append(f"- Speakers: {shown}")
    lines.append("")
    # One paragraph per speaker turn: back-to-back cues from the same speaker
    # merge, stamped with the turn's first cue. cues.json stays per cue.
    turns: list[list] = []
    for cue in cues:
        text = (cue.get("text") or "").strip()
        if not text:
            continue
        speaker = _at(cue.get("speaker") or "unknown")
        if turns and turns[-1][0] == speaker:
            turns[-1][2].append(text)
        else:
            turns.append([speaker, float(cue.get("start") or 0), [text]])
    for speaker, start, texts in turns:
        # Blank line between turns: markdown otherwise folds them into one paragraph.
        lines.append(f"**{speaker}** [{format_ts(start)}] {' '.join(texts)}")
        lines.append("")
    lines.append("")
    return "\n".join(lines)


def format_ts(t: float) -> str:
    if t < 0:
        t = 0.0
    total = int(round(t))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _at(name: str) -> str:
    if name in {"unknown", "both", "overlap", "silence", "host"}:
        return name
    return name if name.startswith("@") else f"@{name}"


def _speakers_of(cues: list[dict]) -> list[str]:
    seen: list[str] = []
    skip = {"unknown", "both", "overlap", "silence", None, ""}
    for cue in cues:
        sp = cue.get("speaker")
        if sp in skip or sp in seen:
            continue
        seen.append(sp)
    return seen


def wav_for_asr(
    src: str | Path,
    dest: str | Path,
    *,
    chunk_seconds: int | None = None,
) -> list[tuple[Path, float]]:
    """Convert a copy for Whisper. Original replay stays tagged.

    Returns [(wav_path, offset_seconds)]. One entry if unchunked.
    """
    ffmpeg = _ffmpeg()
    dest_path = Path(dest)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    wav = dest_path if dest_path.suffix.lower() == ".wav" else dest_path.with_suffix(".wav")
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(src),
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(wav),
    ]
    _run(cmd, "ffmpeg could not convert the replay to wav")
    if not chunk_seconds:
        return [(wav, 0.0)]
    chunk_dir = wav.parent / "chunks"
    chunk_dir.mkdir(parents=True, exist_ok=True)
    pattern = str(chunk_dir / "c%03d.wav")
    split = [
        ffmpeg,
        "-y",
        "-i",
        str(wav),
        "-f",
        "segment",
        "-segment_time",
        str(chunk_seconds),
        "-reset_timestamps",
        "1",
        pattern,
    ]
    _run(split, "ffmpeg could not chunk the wav")
    files = sorted(chunk_dir.glob("c*.wav"))
    return [(path, idx * float(chunk_seconds)) for idx, path in enumerate(files)]


def write_mp3(src: str | Path, dest: str | Path) -> Path:
    ffmpeg = _ffmpeg()
    dest_path = Path(dest)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(src),
        "-vn",
        "-ac",
        "1",
        "-b:a",
        "40k",
        str(dest_path),
    ]
    _run(cmd, "ffmpeg could not write audio.mp3")
    return dest_path


def _ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise RenderError(
            "ffmpeg is not on PATH. Install ffmpeg, then re-run."
        )
    return path


def _run(cmd: list[str], message: str) -> None:
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip().splitlines()
        tail = err[-1] if err else "ffmpeg failed"
        raise RenderError(f"{message}: {tail[:300]}")
