from __future__ import annotations

from app.ai.schemas import CoachReport, CriticResult, PipelinePayload
from app.utils.time import format_timestamp


def _metric(payload: PipelinePayload, name: str) -> float | None:
    for item in payload.metrics:
        if item.get("name") == name and item.get("status") != "insufficient_data":
            value = item.get("value")
            return float(value) if value is not None else None
    return None


def build_local_coach_report(payload: PipelinePayload) -> dict:
    duration = format_timestamp(payload.duration)
    frames = int((payload.metadata or {}).get("analyzed_frames") or 0)
    tracks = len(payload.tracks)
    targets = _metric(payload, "targets_detected")
    changes = _metric(payload, "direction_changes")
    visibility = _metric(payload, "average_target_visibility")
    events = payload.events

    if tracks == 0:
        summary = (
            f"Ролик {duration} обработан ({frames} кадров). "
            "Стандартный YOLO не нашёл устойчивых объектов на экране — "
            "это ограничение модели на GTA/FiveM, а не оценка твоей игры. "
            "Текстовый разбор механик без своих весов и без ИИ-API сейчас невозможен."
        )
        strengths = []
        mistakes = [
            "Детектор не увидел игроков, машины и цели — по этим кадрам ошибки геймплея посчитать нельзя."
        ]
        recommendations = [
            "Поставь свою GTA YOLO в models/gta_custom.pt и укажи YOLO_MODEL_PATH.",
            "Чтобы бот писал живой разбор, заполни AI_BASE_URL, AI_API_KEY и AI_MODEL.",
            "Снимай откат без сильного блюра и HUD на весь экран — стоковому YOLO так проще.",
        ]
    else:
        target_text = f"{int(targets)}" if targets is not None else "несколько"
        summary = (
            f"Ролик {duration}, разобрано {frames} кадров, треков: {tracks}. "
            f"На экране модель отметила около {target_text} объектов. "
            "Оценки считаются только из того, что реально увидел детектор. "
            "Мир GTA в метрах, укрытия и прицел здесь не измеряются."
        )
        strengths = []
        if visibility and visibility >= 2:
            strengths.append(f"Цели держались в кадре в среднем {visibility:.1f} сек.")
        if tracks >= 5:
            strengths.append("На записи достаточно объектов, чтобы смотреть движение по экрану.")
        mistakes = []
        if changes and changes >= 20:
            mistakes.append(f"Много смен направления на экране: {int(changes)}. Это пиксели, не метры.")
        rapid = [item for item in events if item.get("type") == "RAPID_MOVEMENT"]
        if rapid:
            mistakes.append(f"Резкое экранное движение в {len(rapid)} фрагментах.")
        multi = [item for item in events if item.get("type") == "MULTIPLE_TARGETS_VISIBLE"]
        if multi:
            mistakes.append("Несколько целей попадали в кадр одновременно — проверь, видел ли ты их все.")
        if not mistakes:
            mistakes.append("Явных срабатываний детектора ошибок мало. Не выдумываю киллы и дамаг.")
        recommendations = [
            "Смотри моменты, где цели появляются и пропадают — там обычно теряется внимание.",
            "Не читай экранную скорость как дистанцию в игре.",
            "Для нормального текста коуча подключи AI API в .env.",
        ]

    report = CoachReport(
        summary=summary,
        strengths=strengths,
        mistakes=mistakes,
        repeated_patterns=[],
        recommendations=recommendations[:3],
        notable_moments=[],
    )
    return {
        "specialists": [],
        "coach": report.model_dump(),
        "critic": CriticResult(approved=True, issues=[]).model_dump(),
        "ai_available": False,
    }
