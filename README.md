# space-tape

Open-source **X Spaces transcription**.

> The page is the git.

Give it a Spaces link (or the tweet that posted the replay). Get a timed transcript with speakers, plus the audio file. Keep the original X link next to the result.

Whisper is the ear. Hydra is the speaker list.

## Demo

The Space [@elonmusk posted](https://x.com/elonmusk/status/1661498079386931206) on 24 May 2023 — DeSantis announcement, servers straining, ~667,000 trying to get in.

https://x.com/i/spaces/1eaJbrAlZjjJX

Play the tape on the **Space Tape** site (this git as a page). Cues live in [`examples/1eaJbrAlZjjJX`](examples/1eaJbrAlZjjJX). Audio is the **real replay**. Click a highlight to play just that chop. Shift-click a range to copy a timestamped quote. Hydra lives in the raw mpegts — remux strips it.

<!-- PLAYER -->

```bash
pip install git+https://github.com/hovtgc/x-spaces-transcription.git
space-tape transcribe "https://x.com/elonmusk/status/1661498079386931206"
```

Package name: `space-tape`. You get `cues.json`, `transcript.md`, and `audio.mp3`. No browser. No X API key. No virtual computer.

Repo: [hovtgc/x-spaces-transcription](https://github.com/hovtgc/x-spaces-transcription)

---

## Do you need a virtual computer?

**No — not for recorded Spaces.**

A replay is just a file. Three things come out of it:

| Signal | Where it lives | Tool |
| --- | --- | --- |
| Words | mixed audio | [Hugging Face Whisper](https://huggingface.co/openai/whisper-large-v3) (`transformers` ASR pipeline) |
| Who is unmuted | ID3 tags muxed into the HLS/m4a (`HydraParticipants`, `HydraAudioLevel`, NTP) | [`space_tape/hydra.py`](space_tape/hydra.py) |
| Identity (handle, pfp, X user id) | those same Hydra tags | no API call required |

A browser agent watching the unmute UI is a **fallback**, not the pipeline.

If you have the replay **as downloaded** (`.m4a` / `.ts` from yt-dlp), skip the computer. An agent only needs a **shell** (`yt-dlp`, `ffmpeg`, Python).

---

## Pipeline

```
Spaces or tweet URL
        │
        ▼
 yt-dlp ──► replay.m4a / replay.ts   (keep ID3)
        │
        ├─────────────────────────────┐
        ▼                             ▼
 parse Hydra ID3              ffmpeg → 16 kHz mono wav
 (who's unmuted, ~1 Hz)               │
        │                             ▼
        │                     Hugging Face Whisper
        │                     (segments + optional words)
        ▼                             ▼
        └──────────── merge ──────────┘
                      │
                      ▼
         cues.json + highlights.json + transcript.md + audio.mp3
         (and the original X URL, untouched)
```

See [AGENTS.md](AGENTS.md) for the agent playbook.

---

## Quick start

Accept any of:

```
https://x.com/i/spaces/1pKdRDlVbRrJW
https://x.com/notpierce69/status/2100117423017906497
https://twitter.com/i/spaces/...
```

```bash
# KEEP the mpegts/m4a. Do not remux yet — remux strips Hydra tags.
space-tape transcribe "https://x.com/i/spaces/1pKdRDlVbRrJW" -o ./out
space-tape transcribe "https://x.com/user/status/123" --model openai/whisper-small.en
```

Python:

```python
from space_tape.download import download, parse_url
from space_tape.hydra import hydra_series, regions
from space_tape.merge import attach_speakers
from space_tape.transcribe import transcribe
from space_tape.render import wav_for_asr, write_outputs
```

System: `ffmpeg`. Whisper weights: Apache 2.0.

English Spaces: `openai/whisper-small.en` or `medium.en`. Mixed language: `openai/whisper-large-v3`.

---

## Hydra

X's audio stack is called **Hydra**. About once a second it writes ID3v2 frames into the stream:

| Frame | Description |
| --- | --- |
| `TXXX JSONMetadata` | `{ "HydraVersion": 4, "ntp": … }` — clock |
| `TXXX HydraParticipants` | JSON array of people **on stage** (not listeners) |
| `TXXX HydraAudioLevel` | JSON int array, one level per on-stage slot |

**Index mapping that worked in practice:**

- `HydraAudioLevel[0]` = host
- `HydraAudioLevel[i+1]` = `HydraParticipants[i]`
- level `0` = muted / silence
- level `≳ 8` = unmuted and making sound

NTP is seconds. Subtract the first NTP to get media time `t`.

**Critical: parse the raw yt-dlp file.** `ffmpeg -c copy` to `.aac` or transcoding to wav **drops every Hydra tag**. So do yt-dlp's default ffmpeg HLS downloader and its FixupM3u8 remux: download with `--downloader m3u8:native --fixup never`. Parse first, then convert a copy for Whisper.

Host is not in `HydraParticipants`. Bake the host handle from the tweet author or `--host`.

Drop a raw replay on the [Player](/player) tab (or `space-tape hydra replay.m4a`). Nothing is uploaded.

---

## Output

`cues.json` — this is the product.

```json
[
  {
    "start": 5.004,
    "end": 7.003,
    "speaker": "notpierce69",
    "text": "Hey DJ, I don't think anyone else is gonna show up."
  }
]
```

`transcript.md` keeps the X URL. Playback on a site is a convenience. X is the source.

Suggested player: one `<audio>` + the cue list. Highlight the cue whose `[start, end]` contains `audio.currentTime`.

`highlights.json` is the same cues, chopped to the lines people actually clip.

```bash
space-tape highlights out/cues.json -n 8
space-tape clip out/cues.json --from 00:18 --to 00:26 --audio out/audio.mp3 -o ./clip
```

`--from` / `--to` take `18`, `00:18`, or `1:02:03`. You get `clip.json`, `clip.md` (timestamped quote), and `clip.mp3` if you pass `--audio`.

---

## Gotchas (paid for in blood)

- **Never transcode before parsing ID3.** The `.aac`/`.wav` will transcribe and have zero speakers.
- Hydra ticks ~1 Hz and drops a talker to level 0 between words. Assign each cue to the speaker live for most of it, not the one at its midpoint: midpoints land in those 1 s gaps.
- Host is slot 0 of `HydraAudioLevel`.
- `HydraParticipants` is **on-stage only**. Listeners never appear.
- Empty `[]` participants + `[0]` levels = nobody talking, or host muted.
- yt-dlp + X will break. Pin yt-dlp, document the last working version.
- Replays expire. Download is the archive.
- Whisper hallucinates on long silence (`Thank you.` x23). Use its sequential long-form decoding with the no-speech guard, not the pipeline's `chunk_length_s`.
- Display names change. Bake the handle.

---

## Ethics / ToS

- Public recorded Spaces only.
- Keep the link to X. You are making a transcript, not a mirror.
- Don't ship other people's Spaces as if you hosted them.
- Whisper weights: Apache 2.0 (openai/whisper). Hydra tags are in a file the user already received from X.

MIT. Use it, fork it, host the git as a page.
