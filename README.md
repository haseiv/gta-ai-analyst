# GTA AI Analyst

Discord bot that accepts a GTA V / FiveM clip, streams it through computer vision and tracking, then returns a readable coach-style breakdown.

This is a working MVP for a small VPS (~2 GB RAM). It does not load the full video into memory.

## Architecture

```
Discord Bot
    ↓
asyncio.Queue  (MVP; Redis later)
    ↓
Streamed OpenCV reader  (frame → process → release)
    ↓
YOLO detector + ByteTrack
    ↓
Events + metrics + scores
    ↓
Specialist agents → Head Coach → Critic (1 revision max)
    ↓
Discord embeds + optional replay send
```

Swap `models/default.pt` for `models/gta_custom.pt` without changing the pipeline. The detector interface is `BaseDetector`.

## Installation

### Python

```bash
python -m venv .venv
# Linux
source .venv/bin/activate
# Windows
.venv\Scripts\activate

pip install -r requirements.txt
```

Python 3.12+ is required.

### FFmpeg

Install FFmpeg so `ffprobe` is on `PATH`.

```bash
# Debian/Ubuntu — FFmpeg + OpenCV runtime libs (needed in slim Docker)
sudo apt-get update && sudo apt-get install -y ffmpeg libgl1 libglib2.0-0 libgomp1 libsm6 libxext6 libxrender1 libxcb1
```

### Discord bot

1. Create an application at https://discord.com/developers/applications
2. Enable bot + applications.commands
3. Invite the bot with `bot` and `applications.commands`
4. Put the token in `.env`

### .env

```bash
cp .env.example .env
```

| Variable | Purpose |
| --- | --- |
| `DISCORD_TOKEN` | Bot token |
| `AI_API_KEY` / `AI_MODEL` / `AI_BASE_URL` | OpenAI-compatible HTTP API |
| `YOLO_MODEL_PATH` | Weights file, default `models/default.pt` |
| `DATABASE_URL` | SQLite URL |
| `MAX_VIDEO_SIZE_MB` | Upload cap |
| `ANALYSIS_FPS` | Sampled analysis rate |
| `MAX_CONCURRENT_ANALYSES` | Keep at `1` on 2 GB RAM |
| `REPLAY_CHANNEL_ID` | Channel for sent replays |
| `REPLAY_RETENTION_MINUTES` | Local replay lifetime |
| `DELETE_REPLAY_AFTER_SEND` | Delete file after a successful send |
| `DEVELOPER_USER_IDS` | Comma-separated Discord user ids |
| `HUMAN_EXAMPLES_TOP_K` | Retrieved training examples per agent |
| `LOG_LEVEL` | Logging level |

Never put secrets in Python files.

### YOLO model

Download an Ultralytics `.pt` file (for example YOLOv8n) to `models/default.pt`.

This default model is **not** a GTA/FiveM model. Detection quality on game footage will be limited until you train a custom model.

### AI API

`HTTPAIProvider` calls `{AI_BASE_URL}/chat/completions` with a bearer token. Any OpenAI-compatible endpoint works. If the API is down, CV results are still returned.

## Run

```bash
python main.py
```

## Commands

| Command | Who | What |
| --- | --- | --- |
| `/menu` | Все | Меню с кнопкой «Залить откат» |
| `/analyze url:` | Все | Разбор по прямой ссылке на видео |
| `/status analysis_id:` | Все | Статус анализа |
| `/help` | Все | То же меню |
| `/train_add` | Developers | Add a completed analysis to the knowledge base |
| `/train_list` | Developers | List examples |
| `/train_remove` | Developers | Delete an example |
| `/train_stats` | Developers | Category counts |

The main bot never asks users to confirm an analysis. Learning is developer-only and never auto-trains on AI output.

## Server requirements

- Linux VPS with ~2 GB RAM
- `MAX_CONCURRENT_ANALYSES=1`
- Streamed frame processing only
- Background cleanup of expired replay files

CPU YOLO will be slow. That is expected on this hardware.

## Known MVP limitations

- Stock YOLO is not trained on GTA/FiveM classes
- Positioning cannot judge cover or map geometry
- Aim cannot run without a crosshair detector
- World coordinates are unknown
- Screen distance is **not** meters
- Shots, damage, kills, vehicle enter/exit are reserved event types and are not simulated

Next vision work: custom GTA dataset, HUD detection, crosshair tracking, kill/death/damage detectors, custom classes, GPU worker.

## Custom GTA YOLO model

1. Train a YOLO model with your GTA/FiveM classes
2. Copy weights to `models/gta_custom.pt`
3. Set `YOLO_MODEL_PATH=models/gta_custom.pt`
4. Restart the bot

No pipeline code change is required.

## Future GPU worker architecture

```
Discord Bot → Redis queue → GPU worker → custom GTA model → metrics → AI agents → result
```

The current job interface is a Python `asyncio.Queue`. Do not install Redis/Celery for this MVP.

## Tests

```bash
pytest
```
