from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from space_tape.download import DownloadError, parse_url


def test_spaces_link() -> None:
    info = parse_url("https://x.com/i/spaces/1pKdRDlVbRrJW")
    assert info["kind"] == "space"
    assert info["space_id"] == "1pKdRDlVbRrJW"
    assert info["host"] is None
    assert info["url"] == "https://x.com/i/spaces/1pKdRDlVbRrJW"


def test_status_bakes_host() -> None:
    info = parse_url("https://x.com/notpierce69/status/2100117423017906497")
    assert info["kind"] == "status"
    assert info["host"] == "notpierce69"
    assert info["status_id"] == "2100117423017906497"


def test_twitter_dot_com() -> None:
    info = parse_url("https://twitter.com/i/spaces/1pKdRDlVbRrJW")
    assert info["space_id"] == "1pKdRDlVbRrJW"


def test_rejects_garbage() -> None:
    try:
        parse_url("https://example.com/not-a-space")
    except DownloadError:
        return
    raise AssertionError("expected DownloadError")


if __name__ == "__main__":
    test_spaces_link()
    test_status_bakes_host()
    test_twitter_dot_com()
    test_rejects_garbage()
    print("ok")
