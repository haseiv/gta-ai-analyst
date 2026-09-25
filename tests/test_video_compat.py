import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.analysis.video import compat
from app.analysis.video.reader import iter_sampled_frames


def test_compatible_video_is_not_transcoded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"video")
    monkeypatch.setattr(compat, "decodes_first_frame", lambda _path: True)
    assert compat.ensure_cv_compatible(source, 1000) == source
    assert source.exists()


def test_undecodable_video_is_transcoded_to_h264(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"av1")

    def decodes(path: Path) -> bool:
        return path.name.endswith("_cv.mp4") and path.exists()

    def fake_run(command, **_kwargs):
        Path(command[-1]).write_bytes(b"h264")
        assert "libx264" in command
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(compat, "decodes_first_frame", decodes)
    monkeypatch.setattr(compat.subprocess, "run", fake_run)
    converted = compat.ensure_cv_compatible(source, 1000)
    assert converted.name == "source_cv.mp4"
    assert converted.read_bytes() == b"h264"
    assert not source.exists()


def test_reader_rejects_open_video_with_zero_decoded_frames(monkeypatch: pytest.MonkeyPatch):
    class EmptyCapture:
        def isOpened(self):
            return True

        def get(self, _key):
            return 30.0

        def read(self):
            return False, None

        def release(self):
            return None

    fake_cv2 = SimpleNamespace(
        VideoCapture=lambda _path: EmptyCapture(),
        CAP_PROP_FPS=5,
    )
    monkeypatch.setitem(sys.modules, "cv2", fake_cv2)
    with pytest.raises(RuntimeError, match="zero frames"):
        list(iter_sampled_frames(Path("empty.mp4"), 5.0))
