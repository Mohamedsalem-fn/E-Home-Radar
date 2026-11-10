# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Author: Mohamed Salem (Expert AI Engineer & Automation Architect)
# Focus: AI Engineering | Automation | Agentic Systems
# Copyright (c) 2026. All Rights Reserved.
# -------------------------------------------------------------------------------
"""Streaming filters."""
from __future__ import annotations

from collections import deque

import numpy as np

MAD_SCALE = 1.4826


class Hampel:
    """Replace outliers (> k * scaled MAD from window median) with the median."""

    def __init__(self, window: int = 7, k: float = 3.0, floor: float = 0.5):
        self.buf: deque = deque(maxlen=window)
        self.k = k
        self.floor = floor

    def update(self, x: float) -> float:
        self.buf.append(x)
        if len(self.buf) < 3:
            return x
        arr = np.fromiter(self.buf, dtype=float)
        med = float(np.median(arr))
        mad = MAD_SCALE * float(np.median(np.abs(arr - med)))
        mad = max(mad, self.floor)  # quantised data often has MAD == 0
        if abs(x - med) > self.k * mad:
            return med
        return x


class EMA:
    def __init__(self, alpha: float = 0.3):
        self.alpha = alpha
        self.v = None

    def update(self, x: float) -> float:
        self.v = x if self.v is None else self.alpha * x + (1 - self.alpha) * self.v
        return self.v

    def reset(self) -> None:
        self.v = None
