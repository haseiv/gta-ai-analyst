from app.config.settings import Settings, reset_settings_cache, get_settings


def test_developer_ids_parse_from_csv():
    settings = Settings(developer_user_ids="1, 2, 3")
    assert settings.developer_user_ids == [1, 2, 3]
    assert settings.is_developer(2)
    assert not settings.is_developer(9)


def test_settings_read_env(monkeypatch):
    monkeypatch.setenv("MAX_VIDEO_SIZE_MB", "50")
    monkeypatch.setenv("ANALYSIS_FPS", "4")
    monkeypatch.setenv("DEVELOPER_USER_IDS", "42")
    reset_settings_cache()
    settings = get_settings()
    assert settings.max_video_size_mb == 50
    assert settings.analysis_fps == 4
    assert settings.developer_user_ids == [42]
    reset_settings_cache()
