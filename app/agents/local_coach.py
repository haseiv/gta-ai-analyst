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
    activity = _metric(payload, "movement_activity")
    spikes = _metric(payload, "screen_motion_spikes") or _metric(payload, "direction_changes")
    stills = _metric(payload, "still_moments")

    if activity is None and tracks == 0:
        summary = (
            f"Ролик {duration} скачан на сервер и прочитан ({frames} кадров), "
            "но движения по кадрам почти нет — запись слишком статичная или битая."
        )
        mistakes = ["По пикселям кадра активность не выделилась."]
        recommendations = ["Пришли более живой фрагмент боя или поездки."]
        strengths: list[str] = []
    else:
        pace = "спокойная"
        if activity and activity >= 12:
            pace = "рваная, камера и картинка часто дёргаются"
        elif activity and activity >= 6:
            pace = "средняя, запись живая"
        summary = (
            f"Откат {duration} скачан на хост и разобран по кадрам ({frames} шт.). "
            f"Экранная активность {pace}. "
            "Это не метры в мире GTA и не прицел — только то, как шевелится картинка. "
            "Стоковый YOLO людей и машины в FiveM почти не видит, поэтому киллы и укрытия не ставлю."
        )
        strengths = []
        if stills and stills >= 8:
            strengths.append("Есть паузы в картинке — похоже, ты иногда стоишь или целишься, а не только бежишь.")
        if tracks:
            strengths.append(f"Детектор всё же поймал {tracks} объектов на экране.")
        mistakes = []
        if spikes and spikes >= 8:
            mistakes.append(
                f"Много резких скачков картинки ({int(spikes)}). "
                "Либо камера крутится слишком активно, либо запись дёрганая."
            )
        if activity and activity >= 16:
            mistakes.append("Картинка почти не успокаивается — оппоненту тебя сложнее читать, себе тоже.")
        if not mistakes:
            mistakes.append("По движению кадра грубых перекосов не видно. Оружие, дамаг и киллы система не видит.")
        recommendations = [
            "На резких скачках картинки пересмотри откат — там обычно теряется контроль камеры.",
            "Для точного разбора людей/машин нужна своя GTA-модель.",
            "Не читай экранную активность как дистанцию в метрах.",
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
