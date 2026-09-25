import numpy as np

from app.analysis.hud.capt import CaptHudTracker, CaptSample, _feed_pairs, _name_key
from app.agents.local_coach import build_local_coach_report
from app.ai.schemas import PipelinePayload
from app.bot.embeds.analysis import build_analysis_embeds


def test_feed_pairs_names_on_both_sides_of_weapon_icon():
    result = [
        ([[35, 27], [137, 27], [137, 45], [35, 45]], "Hase Faze", 0.84),
        ([[221, 27], [328, 27], [328, 45], [221, 45]], "JoeForbes", 0.87),
        ([[15, 100], [40, 100], [40, 110], [15, 110]], "23", 0.99),
    ]
    assert _feed_pairs(result) == [("Hase Faze", "JoeForbes")]
    assert _name_key("Hase Faze") == _name_key("HaseFaze")


def test_confirmed_capt_kill_and_limited_finish_score():
    tracker = CaptHudTracker("Hase Faze")
    tracker._recognized_hud = True
    tracker.samples = [
        CaptSample(55, 38, 357),
        CaptSample(56, 33, 352),
        CaptSample(57, 24, 343),
    ]
    tracker.feed = [(57, "Hase Faze", "Joe Forbes")]
    summary, events = tracker.finalize()
    assert summary["rounds_observed"] == 14
    assert summary["player_kills"] == 1
    assert summary["finish_score"] == 8.5
    assert events[0].type == "KILL"
    assert events[0].metadata["rounds_in_previous_4s"] == 14


def test_capt_does_not_attribute_other_players_kills():
    tracker = CaptHudTracker("Hase Faze")
    tracker._recognized_hud = True
    tracker.samples = [
        CaptSample(55, 38, 357),
        CaptSample(56, 33, 352),
        CaptSample(57, 24, 343),
    ]
    tracker.feed = [(57, "Other Player", "Joe Forbes")]
    summary, events = tracker.finalize()
    assert summary["player_kills"] == 0
    assert summary["finish_score"] is None
    assert events == []


def test_unknown_player_name_never_gets_personal_score():
    tracker = CaptHudTracker()
    tracker._recognized_hud = True
    tracker.samples = [
        CaptSample(55, 38, 357),
        CaptSample(56, 33, 352),
        CaptSample(57, 24, 343),
    ]
    tracker.feed = [(57, "Hase Faze", "Joe Forbes")]
    summary, events = tracker.finalize()
    assert summary["player_kills"] is None
    assert summary["finish_score"] is None
    assert events[0].type == "KILL_FEED_ENTRY"


def test_feed_visible_at_clip_start_is_baseline_not_new_kill():
    class FakeOCR:
        def __init__(self):
            self.calls = 0

        def __call__(self, _image):
            self.calls += 1
            sequence = [
                [([[], [], [], []], "Majestic", 0.9), ([[], [], [], []], "MCL", 0.9)],
                [([[], [], [], []], "04:25", 0.9)],
                [([[], [], [], []], "38/357", 0.9)],
                [
                    ([[35, 27], [137, 27], [137, 45], [35, 45]], "Old Killer", 0.9),
                    ([[221, 27], [328, 27], [328, 45], [221, 45]], "Old Victim", 0.9),
                ],
                [([[], [], [], []], "33/352", 0.9)],
                [
                    ([[35, 27], [137, 27], [137, 45], [35, 45]], "Hase Faze", 0.9),
                    ([[221, 27], [328, 27], [328, 45], [221, 45]], "Joe Forbes", 0.9),
                ],
            ]
            return sequence[self.calls - 1], None

    tracker = CaptHudTracker("Hase Faze")
    tracker._ocr = FakeOCR()
    frame = np.zeros((1440, 2560, 3), dtype=np.uint8)
    tracker.update(0, frame)
    tracker.update(1, frame)
    assert tracker.feed == [(1, "Hase Faze", "Joe Forbes")]


def test_other_resolution_is_silent():
    tracker = CaptHudTracker("Hase Faze")
    tracker.update(0, np.zeros((32, 32, 3), dtype=np.uint8))
    summary, events = tracker.finalize()
    assert summary["available"] is False
    assert events == []


def test_capt_discord_report_shows_limited_score_only():
    tracker = CaptHudTracker("Hase Faze")
    tracker._recognized_hud = True
    tracker.samples = [
        CaptSample(55, 38, 357),
        CaptSample(56, 33, 352),
        CaptSample(57, 24, 343),
    ]
    tracker.feed = [(57, "Hase Faze", "Joe Forbes")]
    hud, events = tracker.finalize()
    payload = PipelinePayload(
        analysis_id="A1",
        duration=60,
        metadata={"analyzed_frames": 300, "gameplay_analysis_available": False, "hud_analysis": hud},
        events=[event.model_dump() for event in events],
        scores=[
            {"name": "Aim", "value": None, "confidence": 0, "status": "insufficient_data"},
            {"name": "Confirmed Finish", "value": 8.5, "confidence": 0.45, "status": "limited_hud_heuristic"},
        ],
    )
    result = payload.model_dump()
    result.update(build_local_coach_report(payload))
    embeds = build_analysis_embeds("A1", result)
    scores_field = next(field.value for field in embeds[0].fields if field.name == "📊 ОЦЕНКИ")
    assert "8.5/10" in scores_field
    assert "не оценка меткости" in scores_field
    assert "Прицел" not in scores_field
    assert "Joe Forbes" in result["coach"]["strengths"][0]
