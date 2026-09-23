from __future__ import annotations

import importlib
import os
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
    env = os.environ.copy()
    env.setdefault("DEBIAN_FRONTEND", "noninteractive")
    completed = subprocess.run(command, check=False, capture_output=True, text=True, env=env)
    if completed.returncode != 0:
        tail = (completed.stderr or completed.stdout or "").strip()[-500:]
        logger.warning("command failed (%s): %s", " ".join(command), tail)
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
    logger.info("installing OpenCV system libraries")
    _run([apt, "update"])
    _run([apt, "install", "-y", "--no-install-recommends", *_APT_PACKAGES])


def _force_headless_opencv() -> None:
    logger.info("installing opencv-python-headless")
    code = _run([sys.executable, "-m", "pip", "install", "--no-cache-dir", "opencv-python-headless"])
    if code != 0:
        logger.warning("opencv-python-headless install failed")
        return
    _run([sys.executable, "-m", "pip", "uninstall", "-y", "opencv-python", "opencv-contrib-python"])


def _needs_repair(exc: BaseException) -> bool:
    text = str(exc)
    return any(
        token in text
        for token in (
            "libxcb",
            "libGL",
            "libgthread",
            "libglib",
            "No module named 'cv2'",
            "No module named cv2",
        )
    )


def ensure_cv2() -> None:
    """Make OpenCV importable on slim Linux images that lack GUI libraries."""
    try:
        importlib.import_module("cv2")
        return
    except ImportError as exc:
        if not _needs_repair(exc):
            raise
        logger.warning("OpenCV import failed (%s); repairing", exc)

    _install_system_libs()
    _force_headless_opencv()
    _purge_cv2_modules()
    try:
        importlib.import_module("cv2")
        logger.info("OpenCV is ready")
    except ImportError as exc:
        raise SystemExit(
            "OpenCV is not installed. In the host image run: "
            "pip install opencv-python-headless && "
            "apt-get install -y libxcb1 libgl1 libglib2.0-0 libgomp1 ffmpeg"
        ) from exc
