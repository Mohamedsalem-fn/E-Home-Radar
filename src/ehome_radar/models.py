# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Author: Mohamed Salem (Expert AI Engineer & Automation Architect)
# Focus: AI Engineering | Automation | Agentic Systems
# Copyright (c) 2026. All Rights Reserved.
# -------------------------------------------------------------------------------
"""Shared data models."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List


class State(str, Enum):
    CALIBRATING = "CALIBRATING"
    IDLE = "IDLE"
    MOTION = "MOTION"
    COOLDOWN = "COOLDOWN"
    SENSOR_LOST = "SENSOR_LOST"


@dataclass
class Sample:
    """One raw sensor observation. ``values`` holds 1 (RSSI) or N (CSI) numbers."""

    ts: float
    values: List[float]
    meta: Dict[str, str] = field(default_factory=dict)  # e.g. bssid, channel


@dataclass
class Reading:
    """Engine output after DSP + state machine."""

    ts: float
    raw: float
    filtered: float
    activity: float
    score: float  # 0..100
    z: float
    state: State
    calibrated: bool

    def to_dict(self) -> dict:
        return {
            "ts": self.ts,
            "raw": round(self.raw, 3),
            "filtered": round(self.filtered, 3),
            "activity": round(self.activity, 4),
            "score": round(self.score, 2),
            "z": round(self.z, 3),
            "state": self.state.value,
            "calibrated": self.calibrated,
        }


@dataclass
class Event:
    start: float
    end: float
    peak_score: float
    id: int = 0

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)
