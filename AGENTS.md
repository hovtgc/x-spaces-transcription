# Agent playbook

Any agent with a shell. Do not watch the Space in a browser to listen and type.

1. Take a URL. Accept `x.com/i/spaces/<id>`, `x.com/<user>/status/<id>`, or `twitter.com` equivalents.
2. `yt-dlp -f "bestaudio/best" --hls-use-mpegts -o replay.%(ext)s "$URL"`. **Do not remux.** If yt-dlp finds no media, stop — the Space was not recorded or the replay expired.
3. Parse Hydra ID3 from the **raw** download (`space_tape/hydra.py`). This is who was unmuted, ~1 Hz, with handles.
4. Convert a **copy** for ASR: `ffmpeg -i replay.m4a -ac 1 -ar 16000 space.wav`.
5. Run Hugging Face Whisper with `return_timestamps=True` (word-level if you want karaoke).
6. Merge: each Whisper cue gets the Hydra speaker covering its midpoint.
7. Write `cues.json`, `transcript.md`, `audio.mp3`. Always include the original X URL.
8. Do **not** watch the Space in a browser to "listen and type." Whisper is the ear. Hydra is the speaker list.

```bash
space-tape transcribe "$URL" -o ./out
```

## When an agent *does* need a computer

Only if step 1 or 2 fails.

1. Open the Space replay on x.com.
2. Play at 1x (unmute UI is not reliable at 16x).
3. Screenshot or DOM-watch the speaker list / pulsing avatar whenever it changes.
4. Log `{ t: audio.currentTime, handles: [...] }`.
5. Merge that log the same way you merge Hydra regions.

Treat this as `speakers.json` from a different sensor. Same merge code.

## Critical

- Never transcode before parsing ID3.
- Host is not in `HydraParticipants`. Host is slot 0 of `HydraAudioLevel`.
- Replays expire. Download is the archive.
- Public recorded Spaces only. Keep the link to X.
