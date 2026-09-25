from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError


PROFILE_NAME_RE = re.compile(r"^[a-z0-9_-]{2,32}$")


class ProfileError(ValueError):
    pass


class CoachingProfile(BaseModel):
    name: str
    title: str = "Универсальный профиль"
    hud_profiles: list[str] = Field(default_factory=lambda: ["majestic_capt"])
    hud_variants: list[str] = Field(default_factory=list)
    efficient_kill_max_rounds: int = Field(default=10, ge=1, le=100)
    mixed_kill_max_rounds: int = Field(default=24, ge=1, le=150)
    unconverted_warning_rounds: int = Field(default=12, ge=1, le=150)
    recommendations: list[str] = Field(default_factory=list, max_length=10)


def parse_coaching_profile(payload: bytes) -> CoachingProfile:
    if not payload:
        raise ProfileError("Файл профиля пуст.")
    try:
        raw = json.loads(payload.decode("utf-8-sig"))
        profile = CoachingProfile.model_validate(raw)
    except (UnicodeDecodeError, json.JSONDecodeError, ValidationError, TypeError) as exc:
        raise ProfileError(f"Некорректный профиль: {exc}") from exc
    profile.name = profile.name.strip().casefold()
    if not PROFILE_NAME_RE.fullmatch(profile.name):
        raise ProfileError("Имя профиля: только a-z, 0-9, _ и - (2–32 символа).")
    if profile.mixed_kill_max_rounds < profile.efficient_kill_max_rounds:
        raise ProfileError("mixed_kill_max_rounds не может быть меньше efficient_kill_max_rounds.")
    return profile


class CoachingProfileStore:
    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def save(self, profile: CoachingProfile) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        destination = self.directory / f"{profile.name}.json"
        temporary = destination.with_suffix(".json.tmp")
        temporary.write_text(profile.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(destination)
        return destination

    def list(self) -> list[CoachingProfile]:
        if not self.directory.is_dir():
            return []
        profiles: list[CoachingProfile] = []
        for path in sorted(self.directory.glob("*.json")):
            try:
                profiles.append(parse_coaching_profile(path.read_bytes()))
            except (OSError, ProfileError):
                continue
        return profiles

    def match(self, hud: dict) -> CoachingProfile | None:
        hud_profile = str(hud.get("profile") or "")
        hud_variant = str(hud.get("hud_variant") or "")
        for profile in self.list():
            if hud_profile not in profile.hud_profiles:
                continue
            if profile.hud_variants and hud_variant not in profile.hud_variants:
                continue
            return profile
        return None
