"""
Shared, distinct result types per subsystem (architecture review, Section 07:
"Shared contract, distinct result types"). Every pipeline's predict() returns
one of these, so the app and submission export code don't need to know each
subsystem's internals.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DoorSegment:
    start_time: str  # native "Y-M-D-H-M-S-ms" or ISO-parseable
    end_time: str
    prediction: str  # "Normal" | "Abnormal resistance"
    confidence: float | None = None


@dataclass
class DoorResult:
    segments: list[DoorSegment] = field(default_factory=list)


@dataclass
class ACVResult:
    file_id: str
    ranked_cars: list[str]  # most- to least-likely faulty, exact header IDs
    scores: dict[str, float] | None = None  # car_id -> raw ranking score


@dataclass
class RailResult:
    file_id: str
    prediction: str  # "Normal" | "Side I" | "Side II"
    side_scores: dict[str, float] | None = None


@dataclass
class SHMResult:
    file_id: str
    damage_estimate: float
    evidence: dict | None = None
