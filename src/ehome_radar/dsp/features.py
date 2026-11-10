# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Author: Mohamed Salem (Expert AI Engineer & Automation Architect)
# Focus: AI Engineering | Automation | Agentic Systems
# Copyright (c) 2026. All Rights Reserved.
# -------------------------------------------------------------------------------
"""Window feature extraction."""
from __future__ import annotations

from typing import Dict

import numpy as np


def window_features(x: np.ndarray, fs: float) -> Dict[str, float]:
    """Compute variance, MAD, diff-energy and 0.3-5 Hz band energy of a window."""
    if len(x) < 4:
        return dict(var=0.0, mad=0.0, diff=0.0, band=0.0)
    var = float(np.var(x))
    med = float(np.median(x))
    mad = 1.4826 * float(np.median(np.abs(x - med)))
    diff = float(np.mean(np.abs(np.diff(x))))
    xc = (x - x.mean()) * np.hanning(len(x))
    spec = np.abs(np.fft.rfft(xc)) ** 2 / len(x)
    freqs = np.fft.rfftfreq(len(x), d=1.0 / fs)
    m = (freqs >= 0.3) & (freqs <= min(5.0, fs / 2))
    band = float(spec[m].sum()) if m.any() else 0.0
    return dict(var=var, mad=mad, diff=diff, band=band)


def combine(f: Dict[str, float], w_var: float, w_mad: float, w_diff: float, w_band: float) -> float:
    return (
        w_var * f["var"] ** 0.5
        + w_mad * f["mad"]
        + w_diff * f["diff"]
        + w_band * f["band"] ** 0.5
    )

