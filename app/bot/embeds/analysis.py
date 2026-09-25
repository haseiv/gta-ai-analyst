from __future__ import annotations

import discord

from app.utils.time import format_timestamp

EMBED_LIMIT = 3900

STATUS_RU = {
    "QUEUED": "В очереди",
    "DOWNLOADING": "Скачивание",
    "PROCESSING": "Анализ",
    "AI_ANALYSIS": "ИИ-разбор",
    "COMPLETED": "Готово",
    "FAILED": "Ошибка",
}

SCORE_RU = {
    "Movement": "Движение",
    "Positioning": "Позиционирование",
    "Awareness": "Осведомлённость",
    "Aim": "Прицел",
    "Cover Usage": "Укрытия",
    "Confirmed Finish": "Завершение боя*",
}

EVENT_RU = {
    "RAPID_MOVEMENT": "Резкое изменение изображения",
    "DIRECTION_CHANGE": "Смена направления",
    "MULTIPLE_TARGETS_VISIBLE": "Несколько целей на экране",
    "BURST_NO_KILL": "Расход патронов без роста счётчика убийств (HUD)",
    "KILL": "Подтверждённое убийство",
    "KILL_FEED_ENTRY": "Запись в ленте убийств",
}


def _score_line(scores: list[dict]) -> str:
    lines = []
    for item in scores:
        value = item.get("value")
        status = item.get("status")
        display = "Н/Д" if value is None or status == "insufficient_data" else f"{value}/10"
        name = SCORE_RU.get(str(item.get("name")), str(item.get("name") or "Оценка"))
        lines.append(f"{name:<18} {display}")
    return "```\n" + "\n".join(lines) + "\n```"


def _metric_value(metrics: list[dict], name: str) -> str:
    item = next((metric for metric in metrics if metric.get("name") == name), None)
    if item is None or item.get("value") is None or item.get("status") == "insufficient_data":
        return "Н/Д"
    value = item["value"]
    if name == "average_target_visibility":
        return f"{value:.1f} сек"
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.1f}"


def _error_lines(result: dict) -> list[str]:
    lines: list[str] = []
    for specialist in result.get("specialists") or []:
        for finding in specialist.get("findings") or []:
            if finding.get("status") == "insufficient_data":
                continue
            if finding.get("severity") in {"high", "medium", "warning", "error"}:
                ts = format_timestamp(finding.get("timestamp_start"))
                lines.append(f"{ts} — {finding.get('title') or finding.get('description')}")
    if not lines:
        events = result.get("events") or []
        interesting = [
            event
            for event in events
            if event.get("type") in EVENT_RU
        ]
        interesting.sort(
            key=lambda event: event.get("metadata", {}).get("rounds_observed", 0),
            reverse=True,
        )
        for event in interesting[:6]:
            label = EVENT_RU.get(event.get("type"), event.get("type"))
            if event.get("type") in {"KILL", "KILL_FEED_ENTRY"}:
                meta = event.get("metadata") or {}
                if meta.get("killer") and meta.get("victim"):
                    label += f": {meta['killer']} → {meta['victim']}"
            rounds = event.get("metadata", {}).get("rounds_observed")
            if event.get("type") == "BURST_NO_KILL" and rounds:
                label += f" — {rounds} патронов"
            lines.append(f"{format_timestamp(event.get('timestamp'))} — {label}")
    return lines[:8]


def build_status_embed(analysis_id: str, status: str, progress: float) -> discord.Embed:
    embed = discord.Embed(title=f"🎮 Анализ #{analysis_id}", color=discord.Color.blurple())
    embed.add_field(name="Статус", value=STATUS_RU.get(status, status), inline=True)
    embed.add_field(name="Прогресс", value=f"{int(progress)}%", inline=True)
    embed.set_footer(text="Прогресс примерный, по обработанному времени видео.")
    return embed


def build_failed_embed(analysis_id: str, reason: str) -> discord.Embed:
    embed = discord.Embed(title="❌ АНАЛИЗ НЕ УДАЛСЯ", color=discord.Color.red())
    embed.add_field(name="Анализ", value=f"#{analysis_id}", inline=False)
    embed.add_field(name="Причина", value=reason[:1000], inline=False)
    return embed


def build_analysis_embeds(analysis_id: str, result: dict) -> list[discord.Embed]:
    duration = format_timestamp(result.get("duration"))
    scores = result.get("scores") or []
    metrics = result.get("metrics") or []
    coach = result.get("coach") or {}
    metadata = result.get("metadata") or {}
    gameplay_available = metadata.get("gameplay_analysis_available", True)
    embeds: list[discord.Embed] = []

    main = discord.Embed(title="🎮 РАЗБОР GTA AI", color=discord.Color.green())
    main.add_field(name="Анализ", value=f"#{analysis_id}", inline=True)
    main.add_field(name="Длительность", value=duration, inline=True)
    hud = metadata.get("hud_analysis") or {}
    hud_scores = [score for score in scores if score.get("name") == "Confirmed Finish"]
    if gameplay_available:
        score_display = _score_line(scores)
    elif hud_scores:
        score_display = (
            _score_line(hud_scores)
            + "\n*Предварительная оценка подтверждённых эпизодов по HUD; не оценка меткости или всего капта."
        )
    else:
        score_display = "Недоступны: на сервере нет модели, обученной на GTA/FiveM."
    main.add_field(name="📊 ОЦЕНКИ", value=score_display, inline=False)
    if gameplay_available:
        tracking = (
            f"Целей найдено: {_metric_value(metrics, 'targets_detected')}\n"
            f"Смен направления: {_metric_value(metrics, 'direction_changes')}\n"
            f"Средняя видимость: {_metric_value(metrics, 'average_target_visibility')}"
        )
    else:
        tracking = (
            "Игровой детектор не настроен.\n"
            "Непроверенные цели не показываются."
        )
    main.add_field(name="📈 ТРЕКИНГ", value=tracking, inline=False)
    if hud.get("available"):
        if hud.get("profile") == "majestic_capt":
            main.add_field(
                name="🔫 КАПТ / ИНТЕРФЕЙС",
                value=(
                    f"Патронов израсходовано: {hud['rounds_observed']}\n"
                    f"Прочитано записей ленты: {hud['kill_feed_entries']}\n"
                    f"Твоих киллов по красной рамке: {hud['player_kills']}\n"
                    f"Серий без личного килла: {len(hud.get('unconverted_bursts') or [])}\n"
                    "Прицел и попадания не измерены."
                ),
                inline=False,
            )
        else:
            main.add_field(
                name="🔫 ИНТЕРФЕЙС MAJESTIC",
                value=(
                    f"Патронов израсходовано: {hud['rounds_observed']}\n"
                    f"Прирост убийств: {hud['kills_observed']}\n"
                    f"Серий стрельбы без прироста: {hud['bursts_without_kill']}\n"
                    "Попадания и доводка прицела не измерены."
                ),
                inline=False,
            )
    embeds.append(main)

    errors = _error_lines(result)
    extra = discord.Embed(color=discord.Color.green())
    extra.add_field(
        name="⚠️ НАБЛЮДЕНИЯ",
        value="\n".join(errors)[:EMBED_LIMIT] if errors else "Подтверждённых игровых ошибок нет.",
        inline=False,
    )
    strengths = coach.get("strengths") or []
    extra.add_field(
        name="💪 СИЛЬНЫЕ СТОРОНЫ",
        value="\n".join(f"• {item}" for item in strengths[:5])[:EMBED_LIMIT] or "Недостаточно данных.",
        inline=False,
    )
    summary = coach.get("summary") or ""
    extra.add_field(name="🤖 РАЗБОР", value=(summary or "Нет краткого итога.")[:EMBED_LIMIT], inline=False)
    recs = coach.get("recommendations") or []
    extra.add_field(
        name="💡 РЕКОМЕНДАЦИИ",
        value="\n".join(f"{idx}. {item}" for idx, item in enumerate(recs[:5], start=1))[:EMBED_LIMIT]
        or "Нет рекомендаций.",
        inline=False,
    )
    embeds.append(extra)
    return embeds
