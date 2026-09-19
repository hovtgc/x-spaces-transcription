from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from space_tape.clip import clip_cues, highlights, label_for, parse_ts, quote_clip, score_cue


CUES = [
    {"start": 0.0, "end": 11.78, "speaker": "silence", "text": ""},
    {
        "start": 11.78,
        "end": 17.46,
        "speaker": "DavidSacks",
        "text": "I think we're broadcasting. Man, I think we melted the internet there.",
    },
    {
        "start": 18.66,
        "end": 25.7,
        "speaker": "elonmusk",
        "text": "That was insane, sorry. We are actually doing this from David Sacks' Twitter account because it looks like doing it from mine basically broke the Twitter system.",
    },
    {
        "start": 51.38,
        "end": 52.58,
        "speaker": "GovRonDeSantis",
        "text": "I'm here.",
    },
    {
        "start": 125.34,
        "end": 131.02,
        "speaker": "GovRonDeSantis",
        "text": "Well, I am running for president of the United States to lead our great American comeback.",
    },
    {
        "start": 131.42,
        "end": 164.22,
        "speaker": "GovRonDeSantis",
        "text": "American decline is not inevitable. It is a choice.",
    },
]


def test_parse_ts() -> None:
    assert parse_ts(18) == 18.0
    assert parse_ts("18.66") == 18.66
    assert parse_ts("00:18") == 18.0
    assert parse_ts("1:02:03") == 3723.0
    assert parse_ts("00:01:36.2") == 96.2


def test_clip_cues_trims_window() -> None:
    out = clip_cues(CUES, 18.0, 26.0)
    assert len(out) == 1
    assert out[0]["speaker"] == "elonmusk"
    assert out[0]["start"] == 18.66
    assert out[0]["end"] == 25.7


def test_clip_cues_spans_speakers() -> None:
    out = clip_cues(CUES, 10.0, 20.0)
    voiced = [c["speaker"] for c in out if c["text"]]
    assert voiced == ["DavidSacks", "elonmusk"]
    assert out[-1]["end"] == 20.0


def test_quote_keeps_timestamp_and_handle() -> None:
    md = quote_clip(clip_cues(CUES, 18.0, 26.0), source_url="https://x.com/i/spaces/1eaJbrAlZjjJX")
    assert "**@elonmusk**" in md
    assert "[00:00:19]" in md or "[00:00:18]" in md
    assert "That was insane, sorry." in md
    assert "https://x.com/i/spaces/1eaJbrAlZjjJX" in md


def test_highlights_pick_the_chops() -> None:
    hits = highlights(CUES, max_n=5)
    texts = " ".join(h["text"].lower() for h in hits)
    assert "melted the internet" in texts
    assert "insane" in texts
    assert "running for president" in texts
    assert all(h["start"] <= hits[i + 1]["start"] for i, h in enumerate(hits[:-1]))
    assert all("label" in h for h in hits)


def test_silence_does_not_score() -> None:
    assert score_cue(CUES[0]) == 0.0


def test_label_truncates() -> None:
    assert label_for("One two three") == "One two three"
    assert "running for president" in label_for(
        "Well, I am running for president of the United States to lead our great American comeback."
    ).lower()
    assert "melted the internet" in label_for(
        "I think we're broadcasting. Man, I think we melted the internet there."
    ).lower()


if __name__ == "__main__":
    test_parse_ts()
    test_clip_cues_trims_window()
    test_clip_cues_spans_speakers()
    test_quote_keeps_timestamp_and_handle()
    test_highlights_pick_the_chops()
    test_silence_does_not_score()
    test_label_truncates()
    print("ok")
