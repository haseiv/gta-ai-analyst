from app.services.ytdlp import _friendly_error


def test_age_gate_message():
    text = "[youtube] abc: Sign in to confirm your age. Use --cookies"
    message = _friendly_error(text)
    assert message is not None
    assert "18+" in message
