from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AgentFinding(BaseModel):
    category: str
    title: str
    description: str
    timestamp_start: float | None = None
    timestamp_end: float | None = None
    severity: str = "info"
    confidence: float = 0.0
    evidence: list[str] = Field(default_factory=list)
    recommendation: str = ""
    status: str = "ok"


class AgentResult(BaseModel):
    category: str
    status: str = "ok"
    findings: list[AgentFinding] = Field(default_factory=list)
    notes: str = ""


class CoachReport(BaseModel):
    summary: str = ""
    strengths: list[str] = Field(default_factory=list)
    mistakes: list[str] = Field(default_factory=list)
    repeated_patterns: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    notable_moments: list[str] = Field(default_factory=list)


class CriticResult(BaseModel):
    approved: bool = True
    issues: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    suggested_corrections: list[str] = Field(default_factory=list)


class PipelinePayload(BaseModel):
    analysis_id: str
    duration: float
    metadata: dict[str, Any] = Field(default_factory=dict)
    metrics: list[dict[str, Any]] = Field(default_factory=list)
    scores: list[dict[str, Any]] = Field(default_factory=list)
    events: list[dict[str, Any]] = Field(default_factory=list)
    tracks: list[dict[str, Any]] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
