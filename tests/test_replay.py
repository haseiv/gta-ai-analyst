from datetime import timedelta
from pathlib import Path

from app.config.settings import Settings
from app.database.repository import AnalysisRepository, ReplayRepository
from app.services.replay import ReplayService
from app.services.storage import LocalFileStorage
from app.utils.time import utc_now


def test_replay_duplicate_protection(isolated_db, tmp_path: Path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"1234")
    analyses = AnalysisRepository()
    replays = ReplayRepository()
    analyses.create("A200", 55, None, "clip.mp4")
    analyses.update("A200", video_path=str(video))
    replays.create("A200", utc_now() + timedelta(minutes=30), status="AVAILABLE")
    service = ReplayService(Settings(), LocalFileStorage(tmp_path), analyses, replays)

    ok, _ = service.can_send("A200", 55)
    assert ok
    claimed = replays.claim_for_send("A200")
    assert claimed is not None
    assert claimed.status == "SENDING"
    assert replays.claim_for_send("A200") is None
    service.mark_sent("A200")
    ok, reason = service.can_send("A200", 55)
    assert not ok
    assert "already sent" in reason
