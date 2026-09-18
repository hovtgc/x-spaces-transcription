from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from space_tape import transcribe as tr


def test_longform_guards_passed_and_greedy() -> None:
    calls: list[dict] = []

    def fake_asr(path, **kwargs):
        calls.append(kwargs)
        return {"chunks": [{"timestamp": (0.0, 1.0), "text": "hi"}]}

    with mock.patch.object(tr, "_pipeline", return_value=fake_asr):
        cues = tr.transcribe("x.wav", chunk_offset=300.0)
    gen = calls[0]["generate_kwargs"]
    assert gen["condition_on_prev_tokens"] is False
    assert gen["no_speech_threshold"] == 0.6
    # A temperature tuple triggers sampling, which crashes on transformers 5.17.
    assert gen["temperature"] == 0.0
    assert cues == [{"start": 300.0, "end": 301.0, "text": "hi"}]


def _raising_asr(message: str):
    def asr(path, **kwargs):
        raise ValueError(message)
    return asr


def test_silent_chunk_with_word_timestamps_is_empty() -> None:
    silent = _raising_asr("torch.cat(): expected a non-empty list of Tensors")
    with mock.patch.object(tr, "_pipeline", return_value=silent):
        assert tr.transcribe("x.wav", word_timestamps=True) == []


def test_other_value_errors_still_raise() -> None:
    for word_timestamps, message in (
        (True, "some other failure"),
        (False, "torch.cat(): expected a non-empty list of Tensors"),
    ):
        with mock.patch.object(tr, "_pipeline", return_value=_raising_asr(message)):
            try:
                tr.transcribe("x.wav", word_timestamps=word_timestamps)
            except ValueError:
                continue
            raise AssertionError(f"swallowed: {word_timestamps} {message}")


if __name__ == "__main__":
    test_longform_guards_passed_and_greedy()
    test_silent_chunk_with_word_timestamps_is_empty()
    test_other_value_errors_still_raise()
    print("ok")
