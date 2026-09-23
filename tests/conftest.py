from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.config.settings import reset_settings_cache
from app.database.session import init_db, reset_engine


@pytest.fixture
def isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file.as_posix()}")
    monkeypatch.setenv("DISCORD_TOKEN", "")
    reset_settings_cache()
    reset_engine()
    init_db()
    yield db_file
    reset_engine()
    reset_settings_cache()
