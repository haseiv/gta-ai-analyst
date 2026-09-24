import base64

import pytest

from app.services.ytdlp import VideoDownloadError, _friendly_error, _prepare_cookies


def test_age_gate_message():
    text = "[youtube] abc: Sign in to confirm your age. Use --cookies"
    message = _friendly_error(text)
    assert message is not None
    assert "18+" in message


def test_bot_check_message_mentions_cookies():
    message = _friendly_error("Sign in to confirm you're not a bot. Use --cookies")
    assert message is not None
    assert "YTDLP_COOKIES" in message


def test_missing_configured_cookie_file_fails_fast(tmp_path):
    with pytest.raises(VideoDownloadError, match="не найден"):
        _prepare_cookies(str(tmp_path / "missing.txt"), None, tmp_path)


def test_base64_cookies_are_materialized(tmp_path):
    payload = b"# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\tSID\tsecret\n"
    path = _prepare_cookies(None, base64.b64encode(payload).decode(), tmp_path)
    assert path is not None
    assert path.read_bytes() == payload
