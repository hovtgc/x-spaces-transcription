"""space-tape transcribe <url> — recorded X Spaces → cues.json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from space_tape import __version__
from space_tape.clip import highlights, load_cues, parse_ts, write_clip
from space_tape.download import DownloadError, download, parse_url
from space_tape.hydra import hydra_series, regions
from space_tape.merge import attach_speakers
from space_tape.render import RenderError, transcript_md, wav_for_asr, write_outputs
from space_tape.transcribe import DEFAULT_MODEL, transcribe_chunks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="space-tape",
        description=(
            "Open-source X Spaces transcription. "
            "Whisper is the ear. Hydra is the speaker list."
        ),
    )
    parser.add_argument("--version", action="version", version=f"space-tape {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("transcribe", help="Download a recorded Space and emit cues + transcript")
    t.add_argument("url", help="x.com/i/spaces/<id> or x.com/<user>/status/<id>")
    t.add_argument("-o", "--out", default="./out", help="Output directory (default: ./out)")
    t.add_argument("--model", default=DEFAULT_MODEL, help=f"Whisper model (default: {DEFAULT_MODEL})")
    t.add_argument("--host", default=None, help="Host handle (baked over the Hydra 'host' token)")
    t.add_argument("--title", default="Space", help="Title written into transcript.md")
    t.add_argument("--chunk-seconds", type=int, default=300, help="ASR chunk length; 0 to disable")
    t.add_argument("--word-timestamps", action="store_true", help="Ask Whisper for word-level timestamps")
    t.add_argument("--device", default=None, help="transformers device (cpu, 0, …)")
    t.add_argument("--keep-wav", action="store_true", help="Leave space.wav next to the outputs")

    h = sub.add_parser("hydra", help="Parse Hydra ID3 from a raw replay file (no Whisper)")
    h.add_argument("file", help="Raw yt-dlp replay (.m4a / .ts). Do not remux first.")
    h.add_argument("--host", default=None, help="Host handle replacing the 'host' token")
    h.add_argument("-o", "--out", default=None, help="Write regions JSON here instead of stdout")

    c = sub.add_parser("clip", help="Chop cues.json to a timestamp window")
    c.add_argument("cues", help="Path to cues.json")
    c.add_argument("--from", dest="start", required=True, help="Start (18, 00:18, 1:02:03)")
    c.add_argument("--to", dest="end", required=True, help="End timestamp")
    c.add_argument("-o", "--out", default="./clip", help="Output directory (default: ./clip)")
    c.add_argument("--audio", default=None, help="Optional audio file to cut to clip.mp3")
    c.add_argument("--url", default=None, help="Original X URL, written into clip.md")
    c.add_argument("--title", default="clip", help="Title written into clip.md")

    hl = sub.add_parser("highlights", help="Pick punchy cues from cues.json")
    hl.add_argument("cues", help="Path to cues.json")
    hl.add_argument("-n", "--max", dest="max_n", type=int, default=8, help="How many (default: 8)")
    hl.add_argument("-o", "--out", default=None, help="Write highlights.json here (default: stdout)")

    args = parser.parse_args(argv)
    try:
        if args.cmd == "transcribe":
            return _cmd_transcribe(args)
        if args.cmd == "hydra":
            return _cmd_hydra(args)
        if args.cmd == "clip":
            return _cmd_clip(args)
        if args.cmd == "highlights":
            return _cmd_highlights(args)
    except (DownloadError, RenderError, RuntimeError, ValueError) as exc:
        print(f"space-tape: {exc}", file=sys.stderr)
        return 1
    return 2


def _cmd_transcribe(args: argparse.Namespace) -> int:
    info = parse_url(args.url)
    host = (args.host or info.get("host") or "").lstrip("@") or None
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"download  {info['url']}", file=sys.stderr)
    replay = download(info["url"], out_dir)
    print(f"replay    {replay.name}  ({replay.stat().st_size} bytes)", file=sys.stderr)

    print("hydra     parse ID3 (speakers)", file=sys.stderr)
    series = hydra_series(replay, host=host)
    hydra_regions = regions(series)
    if not series:
        print(
            "hydra     no Hydra tags — speakers will be 'unknown'. "
            "Did something remux this file?",
            file=sys.stderr,
        )

    wav = out_dir / "space.wav"
    chunk_seconds = args.chunk_seconds if args.chunk_seconds and args.chunk_seconds > 0 else None
    print("ffmpeg    16 kHz mono wav", file=sys.stderr)
    chunks = wav_for_asr(replay, wav, chunk_seconds=chunk_seconds)

    print(f"whisper   {args.model}", file=sys.stderr)
    cues = transcribe_chunks(
        chunks,
        model=args.model,
        word_timestamps=args.word_timestamps,
        device=args.device,
    )
    merged = attach_speakers(cues, hydra_regions)

    source_url = info["url"]
    posted = source_url if info["kind"] == "status" else None
    if info["kind"] == "status":
        posted = source_url
        # Keep a spaces URL in the transcript when we have one later; for a
        # status link, yt-dlp followed it. Write the URL the user gave.
        source_url = info["url"]

    written = write_outputs(
        out_dir,
        cues=merged,
        source_url=source_url,
        posted_url=posted,
        title=args.title,
        audio_src=replay,
        speakers=_speakers(merged, host),
    )
    if not args.keep_wav:
        _cleanup_wav(out_dir)
    print(f"wrote     {written['cues']}", file=sys.stderr)
    print(f"wrote     {written['transcript']}", file=sys.stderr)
    if "audio" in written:
        print(f"wrote     {written['audio']}", file=sys.stderr)
    if "highlights" in written:
        print(f"wrote     {written['highlights']}", file=sys.stderr)
    print(transcript_md(merged[:3], source_url=source_url, title=args.title) if merged else "(no cues)", file=sys.stderr)
    return 0


def _cmd_hydra(args: argparse.Namespace) -> int:
    path = Path(args.file)
    if not path.is_file():
        raise RuntimeError(f"not a file: {path}")
    series = hydra_series(path, host=args.host)
    hydra_regions = regions(series)
    payload = {"samples": len(series), "regions": hydra_regions}
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


def _cmd_clip(args: argparse.Namespace) -> int:
    cues = load_cues(args.cues)
    start = parse_ts(args.start)
    end = parse_ts(args.end)
    written = write_clip(
        cues,
        start,
        end,
        args.out,
        source_url=args.url,
        audio_src=args.audio,
        title=args.title,
    )
    for kind, path in written.items():
        print(f"wrote     {path}", file=sys.stderr)
    return 0


def _cmd_highlights(args: argparse.Namespace) -> int:
    cues = load_cues(args.cues)
    hits = highlights(cues, max_n=args.max_n)
    text = json.dumps(hits, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote     {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(text)
    return 0


def _speakers(cues: list[dict], host: str | None) -> list[str]:
    names: list[str] = []
    if host:
        names.append(host)
    skip = {"unknown", "both", "overlap", "silence", "host", None, ""}
    for cue in cues:
        sp = cue.get("speaker")
        if sp in skip or sp in names:
            continue
        names.append(sp)
    return names


def _cleanup_wav(out_dir: Path) -> None:
    wav = out_dir / "space.wav"
    if wav.exists():
        wav.unlink()
    chunks = out_dir / "chunks"
    if chunks.is_dir():
        for child in chunks.glob("*"):
            child.unlink()
        chunks.rmdir()


if __name__ == "__main__":
    raise SystemExit(main())
