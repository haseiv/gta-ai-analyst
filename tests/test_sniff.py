from pathlib import Path

from app.analysis.video.sniff import is_webpage_payload
from app.analysis.video.validator import VideoValidationError, validate_video_file


def test_html_saved_as_mp4_is_webpage(tmp_path: Path):
    fake = tmp_path / "gameplay.mp4"
    fake.write_text("<!DOCTYPE html><html><body>youtube</body></html>", encoding="utf-8")
    assert is_webpage_payload(fake) is True


def test_validate_rejects_html_mp4(tmp_path: Path):
    fake = tmp_path / "gameplay.mp4"
    fake.write_text("<html>not video</html>", encoding="utf-8")
    try:
        validate_video_file(fake, max_mb=100)
        raise AssertionError("should fail")
    except VideoValidationError as exc:
        assert "веб-страница" in exc.user_message
