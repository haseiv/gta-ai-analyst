from __future__ import annotations

import importlib
import shutil
import subprocess
import sys

from app.utils.logging import get_logger

logger = get_logger(__name__)

_APT_PACKAGES = [
    "ffmpeg",
    "libgl1",
    "libglib2.0-0",
    "libgomp1",
    "libsm6",
    "libxext6",
    "libxrender1",
    "libxcb1",
]


def _run(command: list[str]) -> int:
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode != 0 and completed.stderr:
        logger.warning("command failed: %s", " ".join(command))
    return completed.returncode


def _purge_cv2_modules() -> None:
    for name in list(sys.modules):
        if name == "cv2" or name.startswith("cv2."):
            del sys.modules[name]


def _install_system_libs() -> None:
    apt = shutil.which("apt-get")
    if apt is None:
        logger.warning("apt-get is not available; cannot install libxcb1 automatically")
        return
    _run([apt, "update"])
    _run([apt, "install", "-y", "--no-install-recommends", *_APT_PACKAGES])


def _force_headless_opencv() -> None:
    _run([sys.executable, "-m", "pip", "uninstall", "-y", "opencv-python", "opencv-contrib-python"])
    _run([sys.executable, "-m", "pip", "install", "--no-cache-dir", "opencv-python-headless"])


def ensure_cv2() -> None:
    """Make OpenCV importable on slim Linux images that lack GUI libraries."""
    try:
        importlib.import_module("cv2")
        return
    except ImportError as exc:
        text = str(exc)
        if not any(token in text for token in ("libxcb", "libGL", "libgthread", "libglib")):
            raise
        logger.warning("OpenCV import failed (%s); installing runtime libraries", text)

    _install_system_libs()
    _force_headless_opencv()
    _purge_cv2_modules()
    try:
        importlib.import_module("cv2")
    except ImportError as exc:
        raise SystemExit(
            "OpenCV still cannot start. Install system packages: "
            "apt-get install -y libxcb1 libgl1 libglib2.0-0 libgomp1 ffmpeg"
        ) from exc
