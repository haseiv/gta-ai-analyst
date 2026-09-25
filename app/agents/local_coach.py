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
    gameplay_available = (payload.metadata or {}).get("gameplay_analysis_available", True)
    hud = (payload.metadata or {}).get("hud_analysis") or {}

    if not gameplay_available:
        if hud.get("available") and hud.get("profile") == "majestic_capt":
            player_kills = hud.get("player_kills")
            kill_text = f"OCR подтвердил минимум {player_kills} твоих убийств по красной рамке ленты."
            summary = (
                f"Боевой ролик Majestic {duration} прочитан ({frames} кадров). По интерфейсу "
                f"замечен расход {hud['rounds_observed']} патронов. {kill_text} "
                "Траекторию прицела и отдельные попадания бот пока не измеряет."
            )
        elif hud.get("available"):
            summary = (
                f"Видео {duration} прочитано ({frames} кадров). По интерфейсу Majestic "
                f"замечен расход {hud['rounds_observed']} патронов и "
                f"{hud['kills_observed']} увеличений счётчика убийств. "
                "Это наблюдения по HUD, а не оценка меткости: попадания и судьбу "
                "конкретного противника бот пока не видит."
            )
        else:
            summary = (
                f"Видео {duration} технически прочитано ({frames} кадров), но игровой разбор отключён: "
                "на сервере нет модели, обученной на GTA/FiveM. "
                "Обычная COCO-модель путала интерфейс и фон с целями, поэтому бот не выдаёт "
                "оценки движения, позиционирования или осведомлённости."
            )
        strengths = []
        mistakes = []
        if hud.get("available") and hud.get("profile") == "majestic_capt":
            rated = hud.get("rated_engagements") or []
            unconverted = hud.get("unconverted_bursts") or []
            if rated:
                best = rated[0]
                strengths.append(
                    f"{format_timestamp(best['timestamp'])}: подтверждено убийство {best['victim']} "
                    f"после расхода примерно {best['rounds_in_previous_4s']} патронов за 4 секунды."
                )
            if unconverted:
                mistakes.extend(
                    f"{format_timestamp(item['timestamp'])}: серия примерно из {item['rounds']} патронов "
                    "без подтверждённого личного килла — кандидат на пересмотр."
                    for item in unconverted[:3]
                )
            recommendations = [
                "Проверь отмеченные серии без килла: это может быть ошибка доводки, смена цели или подавляющий огонь.",
                "Оценка завершения боя предварительная: она учитывает ленту убийств и патроны, но не траекторию прицела.",
            ]
        elif hud.get("available"):
            bursts = sorted(
                (event for event in payload.events if event.get("type") == "BURST_NO_KILL"),
                key=lambda event: event["metadata"]["rounds_observed"],
                reverse=True,
            )
            recommendations = [
                f"Пересмотри {format_timestamp(event['timestamp'])}: "
                f"зафиксирован расход {event['metadata']['rounds_observed']} патронов "
                "без роста счётчика убийств; проверь, удерживал ли ты цель в прицеле."
                for event in bursts[:3]
            ]
            if not recommendations:
                recommendations = ["По одному HUD нельзя оценить доводку прицела; нужен детектор игроков и попаданий."]
        else:
            recommendations = [
                "Установи веса GTA/FiveM YOLO и укажи путь в YOLO_MODEL_PATH.",
                "До установки игровой модели бот может проверить видео только технически.",
            ]
        if spikes and not hud.get("available"):
            recommendations.append(
                f"В записи найдено {int(spikes)} резких изменений изображения; это наблюдение, не оценка игры."
            )
    elif activity is None and tracks == 0:
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
            "Киллы, попадания и укрытия текущие детекторы не измеряют."
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
