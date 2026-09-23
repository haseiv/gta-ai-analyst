from __future__ import annotations

import discord

from app.utils.time import format_timestamp

EMBED_LIMIT = 3900


def _score_line(scores: list[dict]) -> str:
    lines = []
    for item in scores:
        value = item.get("value")
        status = item.get("status")
        display = "N/A" if value is None or status == "insufficient_data" else f"{value}/10"
        lines.append(f"{item.get('name', 'Score'):<14} {display}")
    return "```\n" + "\n".join(lines) + "\n```"


def _metric_value(metrics: list[dict], name: str) -> str:
    item = next((metric for metric in metrics if metric.get("name") == name), None)
    if item is None or item.get("value") is None or item.get("status") == "insufficient_data":
        return "N/A"
    value = item["value"]
    if name == "average_target_visibility":
        return f"{value:.1f} sec"
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
            if event.get("type") in {"RAPID_MOVEMENT", "DIRECTION_CHANGE", "MULTIPLE_TARGETS_VISIBLE"}
        ]
        for event in interesting[:6]:
            lines.append(f"{format_timestamp(event.get('timestamp'))} — {event.get('type')}")
    return lines[:8]


def build_status_embed(analysis_id: str, status: str, progress: float) -> discord.Embed:
    embed = discord.Embed(title=f"🎮 Analysis #{analysis_id}", color=discord.Color.blurple())
    embed.add_field(name="Status", value=status, inline=True)
    embed.add_field(name="Progress", value=f"{int(progress)}%", inline=True)
    embed.set_footer(text="Progress is approximate by processed video time.")
    return embed


def build_failed_embed(analysis_id: str, reason: str) -> discord.Embed:
    embed = discord.Embed(title="❌ ANALYSIS FAILED", color=discord.Color.red())
    embed.add_field(name="Analysis", value=f"#{analysis_id}", inline=False)
    embed.add_field(name="Причина", value=reason[:1000], inline=False)
    return embed


def build_analysis_embeds(analysis_id: str, result: dict) -> list[discord.Embed]:
    duration = format_timestamp(result.get("duration"))
    scores = result.get("scores") or []
    metrics = result.get("metrics") or []
    coach = result.get("coach") or {}
    embeds: list[discord.Embed] = []

    main = discord.Embed(title="🎮 GTA AI ANALYSIS", color=discord.Color.green())
    main.add_field(name="Analysis", value=f"#{analysis_id}", inline=True)
    main.add_field(name="Duration", value=duration, inline=True)
    main.add_field(name="📊 SCORES", value=_score_line(scores), inline=False)
    tracking = (
        f"Targets detected: {_metric_value(metrics, 'targets_detected')}\n"
        f"Direction changes: {_metric_value(metrics, 'direction_changes')}\n"
        f"Avg visibility: {_metric_value(metrics, 'average_target_visibility')}"
    )
    main.add_field(name="📈 TRACKING", value=tracking, inline=False)
    embeds.append(main)

    errors = _error_lines(result)
    extra = discord.Embed(color=discord.Color.green())
    extra.add_field(
        name="⚠️ ERRORS",
        value="\n".join(errors)[:EMBED_LIMIT] if errors else "No high-confidence errors from current detectors.",
        inline=False,
    )
    strengths = coach.get("strengths") or []
    extra.add_field(
        name="💪 STRENGTHS",
        value="\n".join(f"• {item}" for item in strengths[:5])[:EMBED_LIMIT] or "Not enough evidence.",
        inline=False,
    )
    summary = coach.get("summary") or ""
    if not result.get("ai_available", True):
        summary = "Computer Vision анализ завершён, AI Coach временно недоступен."
    extra.add_field(name="🤖 AI COACH", value=(summary or "No coach summary.")[:EMBED_LIMIT], inline=False)
    recs = coach.get("recommendations") or []
    extra.add_field(
        name="💡 RECOMMENDATIONS",
        value="\n".join(f"{idx}. {item}" for idx, item in enumerate(recs[:5], start=1))[:EMBED_LIMIT]
        or "No recommendations.",
        inline=False,
    )
    embeds.append(extra)
    return embeds
