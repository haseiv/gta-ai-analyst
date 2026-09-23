from pathlib import Path

import pytest

from app.analysis.video.metadata import VideoMetadata
from app.analysis.video.validator import VideoValidationError, validate_extension, validate_size, validate_video_file


def test_reject_bad_extension():
    with pytest.raises(VideoValidationError):
        validate_extension("clip.exe")


def test_accept_supported_extension():
    assert validate_extension("game.MP4") == ".mp4"


def test_reject_oversized_file():
    with pytest.raises(VideoValidationError):
        validate_size(200 * 1024 * 1024, max_mb=100)


def test_validate_file_uses_ffprobe(monkeypatch, tmp_path: Path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"not-a-real-video-but-has-size")

    def fake_probe(_path):
        return VideoMetadata(duration=12.5, width=1280, height=720, fps=60.0, codec="h264")

    monkeypatch.setattr("app.analysis.video.validator.probe_video", fake_probe)
    meta = validate_video_file(video, max_mb=100)
    assert meta.codec == "h264"
    assert meta.width == 1280
