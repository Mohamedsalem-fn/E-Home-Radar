# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Author: Mohamed Salem (Expert AI Engineer & Automation Architect)
# Focus: AI Engineering | Automation | Agentic Systems
# Copyright (c) 2026. All Rights Reserved.
# -------------------------------------------------------------------------------
"""Motion detector: adaptive baseline + hysteresis state machine."""
from __future__ import annotations

import math
from collections import deque
from typing import List, Optional

import numpy as np

from ..config import PROFILES, DetectorConfig
from ..models import Event, Reading, Sample, State
from .features import combine, window_features
from .filters import EMA, Hampel, MAD_SCALE


def to_scalar(values: List[float], ref: Optional[np.ndarray]) -> tuple:
    """Reduce a sample vector to a scalar. Returns (scalar, new_ref).

    1 element (RSSI): the value itself.
    N elements (CSI): mean absolute deviation from a rolling per-subcarrier mean.
    """
    v = np.asarray(values, dtype=float)
    if v.size == 1:
        return float(v[0]), ref
    if ref is None or ref.size != v.size:
        ref = v.copy()
    scalar = float(np.mean(np.abs(v - ref)))
    ref = 0.98 * ref + 0.02 * v
    return scalar, ref


class MotionDetector:
    def __init__(self, cfg: DetectorConfig, rate_hz: float):
        self.cfg = cfg
        self.fs = rate_hz
        p = PROFILES[cfg.profile]
        self.t_on, self.t_off, self.on_count = p["t_on"], p["t_off"], p["on_count"]
        self.hampel = Hampel()
        self.ema = EMA()
        self.win: deque = deque(maxlen=max(8, int(cfg.window_s * rate_hz)))
        self.ref: Optional[np.ndarray] = None
        self.state = State.CALIBRATING
        self.calib: List[float] = []
        self.mu = 0.0
        self.sigma = cfg.sigma_min
        self.calibrated = False
        self._calib_start: Optional[float] = None
        self._last_eval = -1e9
        self._above = 0
        self._last_motion = 0.0
        self._event_start = 0.0
        self._peak = 0.0
        self._last: Optional[Reading] = None
        self.finished_events: List[Event] = []
        self.meta_key: Optional[str] = None

    # ----------------------------------------------------------------- control
    def recalibrate(self) -> None:
        self.state = State.CALIBRATING
        self.calibrated = False
        self.calib.clear()
        self._calib_start = None
        self._above = 0

    def set_profile(self, name: str) -> None:
        p = PROFILES[name]
        self.cfg.profile = name
        self.t_on, self.t_off, self.on_count = p["t_on"], p["t_off"], p["on_count"]

    # ------------------------------------------------------------------ update
    def update(self, s: Sample) -> Optional[Reading]:
        """Feed one sample; returns a Reading at the evaluation rate, else None."""
        key = s.meta.get("bssid", "") + s.meta.get("channel", "")
        if key and self.meta_key and key != self.meta_key:
            self.recalibrate()
        if key:
            self.meta_key = key

        raw, self.ref = to_scalar(s.values, self.ref)
        filt = self.ema.update(self.hampel.update(raw))
        self.win.append(filt)

        if s.ts - self._last_eval < 1.0 / self.cfg.eval_hz:
            return None
        if len(self.win) < self.win.maxlen // 2:
            return None
        self._last_eval = s.ts

        c = self.cfg
        f = window_features(np.fromiter(self.win, dtype=float), self.fs)
        # log-domain: activity is right-skewed, log makes noise ~symmetric
        act = math.log(combine(f, c.w_var, c.w_mad, c.w_diff, c.w_band) + 0.05)

        z = 0.0
        if self.state == State.CALIBRATING:
            if self._calib_start is None:
                self._calib_start = s.ts
            self.calib.append(act)
            if s.ts - self._calib_start >= c.calibration_s and len(self.calib) >= 10:
                a = np.asarray(self.calib)
                self.mu = float(np.median(a))
                mad_sigma = MAD_SCALE * float(np.median(np.abs(a - self.mu)))
                # activity is right-skewed: also honour the 95th percentile tail
                tail_sigma = (float(np.percentile(a, 95)) - self.mu) / 1.645
                self.sigma = max(mad_sigma, tail_sigma, c.sigma_min)
                self.calibrated = True
                self.state = State.IDLE
        else:
            z = (act - self.mu) / self.sigma
            self._step_state(s.ts, z)
            if self.state == State.IDLE:  # slow drift adaptation, only when quiet
                alpha = min(1.0, (1.0 / c.eval_hz) / c.drift_tau_s)
                self.mu += alpha * (act - self.mu)
                dev = abs(act - self.mu)
                self.sigma = max(c.sigma_min, self.sigma + alpha * (dev - self.sigma))

        score = 100.0 / (1.0 + math.exp(-(z - self.t_on) / 1.5)) if self.calibrated else 0.0
        self._last = Reading(s.ts, raw, filt, act, score, z, self.state, self.calibrated)
        return self._last

    def _step_state(self, ts: float, z: float) -> None:
        if self.state == State.IDLE:
            self._above = self._above + 1 if z > self.t_on else 0
            if self._above >= self.on_count:
                self.state = State.MOTION
                self._event_start = ts
                self._last_motion = ts
                self._peak = z
                self._above = 0
        elif self.state == State.MOTION:
            self._peak = max(self._peak, z)
            if z >= self.t_off:
                self._last_motion = ts
            else:
                self.state = State.COOLDOWN
        elif self.state == State.COOLDOWN:
            if z > self.t_on:
                self.state = State.MOTION
                self._last_motion = ts
                self._peak = max(self._peak, z)
            elif ts - self._last_motion >= self.cfg.hold_s:
                self.state = State.IDLE
                peak_score = 100.0 / (1.0 + math.exp(-(self._peak - self.t_on) / 1.5))
                self.finished_events.append(Event(self._event_start, self._last_motion, peak_score))
