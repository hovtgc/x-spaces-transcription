"""Hugging Face Whisper — the ear.

English Spaces: openai/whisper-small.en or medium.en.
Mixed language: openai/whisper-large-v3.

Long Spaces should be chunked with ffmpeg (see render.wav_for_asr) so a CPU
box doesn't melt. Add the chunk offset back onto every timestamp.
"""

from __future__ import annotations

from pathlib import Path

DEFAULT_MODEL = "openai/whisper-small.en"


def transcribe(
    wav: str | Path,
    *,
    model: str = DEFAULT_MODEL,
    word_timestamps: bool = False,
    device: str | None = None,
    chunk_offset: float = 0.0,
) -> list[dict]:
    """Return [{start, end, text}] (and optional `words`)."""
    asr = _pipeline(model=model, word_timestamps=word_timestamps, device=device)
    kwargs: dict = {}
    if word_timestamps:
        kwargs["return_timestamps"] = "word"
    out = asr(str(wav), **kwargs)
    return normalize_asr(out, chunk_offset=chunk_offset)


def transcribe_chunks(
    wavs: list[tuple[Path, float]],
    **kwargs,
) -> list[dict]:
    """wavs is [(path, offset_seconds), ...]."""
    cues: list[dict] = []
    for path, offset in wavs:
        cues.extend(transcribe(path, chunk_offset=offset, **kwargs))
    return cues


def normalize_asr(out: object, chunk_offset: float = 0.0) -> list[dict]:
    if not isinstance(out, dict):
        text = str(out or "").strip()
        return [{"start": chunk_offset, "end": chunk_offset, "text": text}] if text else []
    chunks = out.get("chunks") or []
    cues: list[dict] = []
    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        ts = chunk.get("timestamp") or (None, None)
        if not isinstance(ts, (tuple, list)):
            ts = (None, None)
        start_raw, end_raw = (ts + (None, None))[:2]
        text = (chunk.get("text") or "").strip()
        if not text:
            continue
        start = float(start_raw or 0) + chunk_offset
        end = float(end_raw if end_raw is not None else start_raw or 0) + chunk_offset
        cue: dict = {"start": start, "end": end, "text": text}
        words = chunk.get("words")
        if isinstance(words, list):
            cue["words"] = words
        cues.append(cue)
    if cues:
        return cues
    text = (out.get("text") or "").strip()
    if not text:
        return []
    return [{"start": chunk_offset, "end": chunk_offset, "text": text}]


def _pipeline(*, model: str, word_timestamps: bool, device: str | None):
    try:
        from transformers import pipeline
    except ImportError as exc:
        raise RuntimeError(
            "transformers is required for Whisper. "
            "pip install space-tape  (or: pip install transformers torch)"
        ) from exc
    try:
        import torch  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "torch is required for Whisper. A CPU wheel is fine:\n"
            "  pip install torch --index-url https://download.pytorch.org/whl/cpu"
        ) from exc

    resolved_device = device if device is not None else _default_device()
    ts: bool | str = "word" if word_timestamps else True
    return pipeline(
        "automatic-speech-recognition",
        model=model,
        chunk_length_s=30,
        return_timestamps=ts,
        device=resolved_device,
    )


def _default_device() -> str | int:
    try:
        import torch

        if torch.cuda.is_available():
            return 0
    except Exception:
        pass
    return "cpu"
