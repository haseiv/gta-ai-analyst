#!/bin/sh
set -eu
if command -v apt-get >/dev/null 2>&1; then
  apt-get update
  apt-get install -y --no-install-recommends \
    ffmpeg libgl1 libglib2.0-0 libgomp1 libsm6 libxext6 libxrender1 libxcb1 || true
fi
python -m pip uninstall -y opencv-python opencv-contrib-python || true
python -m pip install --no-cache-dir opencv-python-headless || true
exec python main.py
