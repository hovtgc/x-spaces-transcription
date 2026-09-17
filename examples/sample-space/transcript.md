# Sample Space

- Space: sample (synthetic pipeline output — not a real Space)
- Speakers: @tape_op (host), @second_mic

**[00:00:01] @tape_op** This is what a Space looks like after space-tape runs.
**[00:00:05] @tape_op** A replay is just a file. You do not need a browser, and you do not need an X API key.
**[00:00:13] @second_mic** Whisper heard the words. Hydra tagged who was unmuted. About once a second, X writes that into the audio as ID3.
**[00:00:22] @tape_op** HydraAudioLevel slot zero is the host. Everyone else on stage sits in HydraParticipants.
**[00:00:30] @second_mic** If you remux to wav before you parse, those tags are gone. The transcript still has words. It has no speakers.
**[00:00:38] @tape_op** So the pipeline is: yt-dlp, keep the mpegts, parse Hydra, then convert a copy for Whisper.
**[00:00:49] @second_mic** Each Whisper cue gets the Hydra region covering its midpoint. That is the whole diarizer. We are not guessing voices.
**[00:00:57] @tape_op** Overlaps stay labeled as both. The mix is one channel. Do not pretend Whisper can split two people talking at once.
**[00:01:07] @second_mic** The product is cues.json. Start, end, speaker, text. Plus transcript.md and a small mp3 for a player.
**[00:01:17] @tape_op** Always keep the original X URL. Playback on a site is a convenience. X is the source.
**[00:01:26] @second_mic** Public recorded Spaces only. Replays expire, so the download is the archive. Listeners never appear in the tags.
**[00:01:34] @tape_op** If yt-dlp finds no media, stop. The Space was not recorded, or the replay is gone. This tool does not join live.
**[00:01:46] @second_mic** Drop a raw replay on the player page to parse Hydra in the browser. Nothing is uploaded. The file already had the speaker list.
**[00:01:54] @tape_op** That is space-tape. Fork it. Run it on a shell. Host the git as a page.
