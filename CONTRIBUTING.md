# Contributing

space-tape is a recorded-Space pipeline. Whisper is the ear. Hydra is the speaker list.

## Don't

- Watch a Space in a browser to "listen and type."
- Remux the replay before parsing ID3. `ffmpeg -c copy` to `.aac` / `.wav` drops every Hydra tag.
- Commit other people's Space audio. Tests use synthetic ID3 fixtures.
- Join a live Space from this tool. If yt-dlp finds no media, the replay is gone. Stop.

## Do

- Keep the original X URL next to every transcript.
- Parse Hydra from the **raw** yt-dlp file, then convert a copy for ASR.
- Bake the host handle from the tweet author / `--host`. Host is slot 0 of `HydraAudioLevel`, not a `HydraParticipants` row.
- Prefer a failing test with a tagged fixture over a prompt-engineered "fix."

## Tests

```bash
python tests/test_download.py
python tests/test_hydra.py
python tests/test_merge.py
python tests/test_urls.py
python tests/test_render.py
python tests/test_transcribe.py
```

No GPU. No X API key. No network.

## Public recorded Spaces only

Don't ship someone else's Space as if you hosted it. The transcript is a reading of a file the user already downloaded from X.
