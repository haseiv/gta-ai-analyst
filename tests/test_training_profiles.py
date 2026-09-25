import json

from app.agents.local_coach import build_local_coach_report
from app.ai.schemas import PipelinePayload
from app.learning.profiles import CoachingProfileStore, parse_coaching_profile


def test_profile_is_saved_and_matched_by_hud_variant(tmp_path):
    profile = parse_coaching_profile(
        json.dumps(
            {
                "name": "capt",
                "title": "Капты Majestic",
                "hud_profiles": ["majestic_capt"],
                "hud_variants": ["deathmatch_or_other"],
                "efficient_kill_max_rounds": 10,
                "mixed_kill_max_rounds": 24,
                "unconverted_warning_rounds": 12,
                "recommendations": ["Не затягивай открытую дуэль."],
            }
        ).encode()
    )
    store = CoachingProfileStore(tmp_path)
    store.save(profile)

    matched = store.match({"profile": "majestic_capt", "hud_variant": "deathmatch_or_other"})

    assert matched is not None
    assert matched.name == "capt"
    assert store.match({"profile": "majestic_capt", "hud_variant": "mcl"}) is None


def test_capt_profile_applies_universal_round_thresholds():
    profile = parse_coaching_profile(
        json.dumps(
            {
                "name": "capt",
                "title": "Капты Majestic",
                "efficient_kill_max_rounds": 10,
                "mixed_kill_max_rounds": 24,
                "unconverted_warning_rounds": 12,
                "recommendations": ["Сбрасывай длинную дуэль."],
            }
        ).encode()
    )
    payload = PipelinePayload(
        analysis_id="A1",
        duration=60,
        metadata={
            "gameplay_analysis_available": False,
            "analyzed_frames": 30,
            "hud_analysis": {
                "available": True,
                "profile": "majestic_capt",
                "rounds_observed": 60,
                "player_kills": 2,
                "rated_engagements": [
                    {"timestamp": 10, "victim": "Good", "rounds_in_previous_4s": 8},
                    {"timestamp": 20, "victim": "Costly", "rounds_in_previous_4s": 30},
                ],
                "unconverted_bursts": [{"timestamp": 30, "rounds": 15}],
            },
        },
    )

    result = build_local_coach_report(payload, profile)

    assert "Good" in result["coach"]["strengths"][0]
    assert any("30 патронов" in item for item in result["coach"]["mistakes"])
    assert any("15 патронов" in item for item in result["coach"]["mistakes"])
    assert result["coach"]["recommendations"] == ["Сбрасывай длинную дуэль."]
