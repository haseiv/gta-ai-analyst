import numpy as np

from app.analysis.hud.majestic import HudSample, MajesticHudTracker, _parse_ammo, _parse_kills
from app.agents.local_coach import build_local_coach_report
from app.ai.schemas import PipelinePayload
from app.bot.embeds.analysis import build_analysis_embeds


def test_ocr_numbers_require_whole_hud_fields():
    assert _parse_ammo([("32/993", 0.76)]) == (32, 993)
    assert _parse_ammo([("ID: 830", 0.99)]) == (None, None)
    assert _parse_ammo([("32/993", 0.2)]) == (None, None)
    assert _parse_kills([("13", 0.54)]) == 13
    assert _parse_kills([("04:04", 0.99)]) is None


def test_no_kill_burst_is_not_an_aim_claim():
    tracker = MajesticHudTracker()
    tracker._recognized_brand = True
    tracker.samples = [
        HudSample(60.5, 32, 993, 13),
        HudSample(61.5, 23, 984, 13),
        HudSample(62.5, 14, 975, 13),
        HudSample(63.5, 8, 969, 13),
        HudSample(64.5, 32, 945, 13),
    ]
    summary, events = tracker.finalize()
    assert summary["rounds_observed"] == 24
    assert summary["kills_observed"] == 0
    assert summary["bursts_without_kill"] == 1
    assert events[0].type == "BURST_NO_KILL"
    assert "not proof of missed aim" in events[0].metadata["meaning"]


def test_kill_counter_increment_suppresses_no_kill_burst():
    tracker = MajesticHudTracker()
    tracker._recognized_brand = True
    tracker.samples = [
        HudSample(240.0, 29, 99, 52),
        HudSample(241.0, 20, 90, 53),
        HudSample(242.0, 20, 90, 53),
    ]
    summary, events = tracker.finalize()
    assert summary["kills_observed"] == 1
    assert summary["bursts_without_kill"] == 0
    assert [event.type for event in events] == ["KILL"]


def test_reload_separates_earlier_no_kill_burst_from_later_kill():
    tracker = MajesticHudTracker()
    tracker._recognized_brand = True
    tracker.samples = [
        HudSample(60, 35, 900, 13),
        HudSample(61, 27, 892, 13),
        HudSample(62, 18, 883, 13),
        HudSample(63, 8, 873, 13),
        HudSample(64, 37, 844, 13),
        HudSample(65, 29, 836, 13),
        HudSample(66, 20, 827, 14),
    ]
    summary, events = tracker.finalize()
    assert summary["bursts_without_kill"] == 1
    assert any(event.type == "BURST_NO_KILL" and event.timestamp == 61 for event in events)


def test_hud_is_silent_without_brand():
    tracker = MajesticHudTracker()
    tracker.update(0.0, np.zeros((32, 32, 3), dtype=np.uint8))
    summary, events = tracker.finalize()
    assert summary["available"] is False
    assert events == []


def test_report_uses_hud_evidence_without_inventing_aim_score():
    tracker = MajesticHudTracker()
    tracker._recognized_brand = True
    tracker.samples = [
        HudSample(60.5, 32, 993, 13),
        HudSample(61.5, 23, 984, 13),
        HudSample(62.5, 14, 975, 13),
        HudSample(63.5, 8, 969, 13),
    ]
    hud, events = tracker.finalize()
    payload = PipelinePayload(
        analysis_id="A1",
        duration=65,
        metadata={"analyzed_frames": 325, "gameplay_analysis_available": False, "hud_analysis": hud},
        events=[event.model_dump() for event in events],
        scores=[{"name": "Aim", "value": None, "status": "insufficient_data"}],
    )
    result = payload.model_dump()
    result.update(build_local_coach_report(payload))
    assert "24 патронов" in result["coach"]["summary"]
    assert "01:01" in result["coach"]["recommendations"][0]
    embeds = build_analysis_embeds("A1", result)
    assert any(field.name == "🔫 ИНТЕРФЕЙС MAJESTIC" for field in embeds[0].fields)
    assert "Недоступны" in embeds[0].fields[2].value
