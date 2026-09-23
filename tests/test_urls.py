import pytest

from app.analysis.video.validator import VideoValidationError
from app.utils.urls import parse_video_url


def test_parse_direct_mp4_link():
    url, name = parse_video_url("https://cdn.example.com/clips/game.mp4")
    assert url.startswith("https://")
    assert name == "game.mp4"


def test_reject_non_http():
    with pytest.raises(VideoValidationError):
        parse_video_url("ftp://files.local/a.mp4")
