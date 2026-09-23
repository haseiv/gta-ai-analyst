import pytest

from app.analysis.video.validator import VideoValidationError
from app.utils.urls import is_platform_url, parse_video_url


def test_parse_direct_mp4_link():
    url, name = parse_video_url("https://cdn.example.com/clips/game.mp4")
    assert url.startswith("https://")
    assert name == "game.mp4"


def test_parse_youtube_and_drive_and_rutube():
    assert parse_video_url("https://youtu.be/abcdefghijk")[1] == "youtube.mp4"
    assert parse_video_url("https://www.youtube.com/watch?v=abcdefghijk")[1] == "youtube.mp4"
    assert parse_video_url("https://drive.google.com/file/d/abc123/view")[1] == "gdrive.mp4"
    assert parse_video_url("https://rutube.ru/video/abcdef123456/")[1] == "rutube.mp4"
    assert is_platform_url("https://m.youtube.com/watch?v=abcdefghijk")


def test_reject_unknown_page():
    with pytest.raises(VideoValidationError):
        parse_video_url("https://example.com/watch?v=1")


def test_reject_non_http():
    with pytest.raises(VideoValidationError):
        parse_video_url("ftp://files.local/a.mp4")
