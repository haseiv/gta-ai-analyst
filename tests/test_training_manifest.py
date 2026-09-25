import json

import pytest

from app.learning.manifest import ManifestError, parse_training_manifest


def test_parse_jsonl_training_manifest():
    payload = b"\n".join(
        [
            json.dumps(
                {
                    "source": "clip.mp4",
                    "start": 10,
                    "end": 18,
                    "category": "Aim",
                    "human_analysis": "Good tracking",
                    "recommendation": "Keep it smooth",
                }
            ).encode(),
            json.dumps(
                {
                    "source": "clip.mp4",
                    "start": 20,
                    "end": 30,
                    "category": "Positioning",
                    "human_analysis": "Stayed exposed too long",
                }
            ).encode(),
        ]
    )

    items = parse_training_manifest(payload)

    assert len(items) == 2
    assert items[0].category == "Aim"
    assert items[1].recommendation == ""


def test_manifest_rejects_invalid_timestamp_range():
    payload = json.dumps(
        [{"start": 30, "end": 10, "human_analysis": "Invalid range"}]
    ).encode()

    with pytest.raises(ManifestError, match="end"):
        parse_training_manifest(payload)


def test_manifest_limits_batch_size():
    payload = json.dumps(
        [{"human_analysis": f"Review {index}"} for index in range(3)]
    ).encode()

    with pytest.raises(ManifestError, match="не более 2"):
        parse_training_manifest(payload, limit=2)
