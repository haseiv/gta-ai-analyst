# GTA AI Analyst

Discord bot that accepts a GTA V / FiveM clip, streams it through computer vision and tracking, then returns a readable coach-style breakdown.

This is an MVP for a small VPS (~2 GB RAM). It does not load the full video into memory.
Gameplay scores require custom GTA/FiveM YOLO weights. The automatically downloaded
COCO model cannot produce gameplay claims; when no custom weights are installed,
the bot skips YOLO entirely instead of downloading a misleading fallback.
For the Majestic 1920×1200 HUD layout, OCR can separately report observed ammo
consumption and increases in the kill counter. This is not an aim score or proof
that a specific opponent was hit or finished.
For the tested 16:9 Majestic combat HUD (including MCL and deathmatch), OCR reads ammo and kill-feed names and
uses Majestic's red row outline to identify the recording player's kills. It can
show a **limited, low-confidence score for confirmed finishes** without asking
for a nickname. It is not an aim, cover, or overall capt skill score.

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
| `MAX_VIDEO_SIZE_MB` | Лимит скачивания, по умолчанию 250 МБ. YouTube качается в 720p |
| `ANALYSIS_FPS` | Sampled analysis rate |
| `MAX_CONCURRENT_ANALYSES` | Keep at `1` on 2 GB RAM |
| `REPLAY_CHANNEL_ID` | Channel for sent replays |
| `REPLAY_RETENTION_MINUTES` | Local replay lifetime |
| `DELETE_REPLAY_AFTER_SEND` | Delete file after a successful send |
| `DEVELOPER_USER_IDS` | Comma-separated Discord user ids |
| `HUMAN_EXAMPLES_TOP_K` | Retrieved training examples per agent |
| `LOG_LEVEL` | Logging level |
| `YTDLP_COOKIES_FILE` | Path to a Netscape-format `cookies.txt` for restricted YouTube videos |
| `YTDLP_COOKIES_BASE64` | Base64-encoded `cookies.txt`, convenient for Docker/cloud secrets |

Never put secrets in Python files.

Discord user `733202645002485772` is the built-in project owner and always has
access to the training commands. Additional maintainers still belong in
`DEVELOPER_USER_IDS`.

For a Docker or cloud deployment, export fresh YouTube cookies in Netscape format,
encode the file with `base64`, and put the result in the secret environment variable
`YTDLP_COOKIES_BASE64`. Do not commit the value to GitHub. If
`YTDLP_COOKIES_FILE` is used instead, the file must exist inside the container.

### YOLO model

Put GTA/FiveM-trained Ultralytics `.pt` weights in `models/gta_custom.pt` and set
`YOLO_MODEL_PATH=models/gta_custom.pt`. A stock YOLOv8 COCO checkpoint is **not**
a gameplay model: the bot detects it automatically, skips its false tracks, and
leaves gameplay scores unavailable instead of inventing an analysis.

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
| `/analyze url:` | Все | Разбор отката по ссылке; авторские киллы в капте определяются по интерфейсу |
| `/status analysis_id:` | Все | Статус анализа |
| `/help` | Все | То же меню |
| `/train_add` | Developers / server admins | Add a completed analysis to the knowledge base |
| `/train_list` | Developers / server admins | List examples |
| `/train_remove` | Developers / server admins | Delete an example |
| `/train_stats` | Developers / server admins | Category counts |

The main bot never auto-confirms its own analysis. Learning controls are limited to
configured developers and Discord server administrators.

### Teacher–student learning

Use `/train_add`, choose **Мой разбор**, set category `Aim` (Russian `Прицел`
and `Трекинг` are accepted), and write the human verdict. Qwen only normalizes
that approved review into a structured label; it is never allowed to approve its
own earlier answer. A small local k-nearest-neighbour student learns the mapping
from local CV/HUD features to those labels. It stays silent until a category has
at least three distilled examples and shows its dataset size and confidence in
the Discord report. **Добавить как есть** remains Qwen context only and cannot
train the local student.

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
- Majestic HUD OCR supports tested 16:10 and 16:9 capt layouts; other HUDs stay unavailable
- Damage, individual target outcomes, and vehicle enter/exit are not detected

Next vision work: annotated GTA frames, crosshair tracking, player/damage detectors,
and validation across other resolutions before enabling an aim score.

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
