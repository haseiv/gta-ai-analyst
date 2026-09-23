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


def _run(command: list[str]) -> tuple[int, str]:
    env = os.environ.copy()
    env.setdefault("DEBIAN_FRONTEND", "noninteractive")
    completed = subprocess.run(command, check=False, capture_output=True, text=True, env=env)
    output = ((completed.stdout or "") + "\n" + (completed.stderr or "")).strip()
    if completed.returncode != 0:
        logger.warning("command failed rc=%s: %s", completed.returncode, output[-1200:])
    else:
        logger.info("command ok: %s", output[-400:])
    return completed.returncode, output


def _purge_cv2_modules() -> None:
    for name in list(sys.modules):
        if name == "cv2" or name.startswith("cv2."):
            del sys.modules[name]


def _install_system_libs() -> None:
    apt = shutil.which("apt-get")
    if apt is None:
        logger.warning("apt-get is not available")
        return
    logger.info("installing OpenCV system libraries")
    _run([apt, "update"])
    _run([apt, "install", "-y", "--no-install-recommends", *_APT_PACKAGES])


def _reinstall_headless() -> None:
    logger.info("force-reinstall opencv-python-headless into %s", sys.executable)
    _run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--force-reinstall",
            "--no-cache-dir",
            "--break-system-packages",
            "opencv-python-headless",
        ]
    )
    _run([sys.executable, "-m", "pip", "show", "opencv-python-headless"])


def _needs_repair(exc: BaseException) -> bool:
    text = str(exc)
    return any(
        token in text
        for token in ("libxcb", "libGL", "libgthread", "libglib", "No module named")
    )


def ensure_cv2() -> None:
    try:
        importlib.import_module("cv2")
        return
    except ImportError as exc:
        if not _needs_repair(exc):
            raise
        logger.warning("OpenCV import failed (%s); repairing", exc)

    _install_system_libs()
    _reinstall_headless()
    _purge_cv2_modules()
    try:
        importlib.import_module("cv2")
        logger.info("OpenCV is ready")
    except ImportError as exc:
        logger.error("sys.path=%s", sys.path)
        raise SystemExit(f"OpenCV import still failed: {exc}") from exc
