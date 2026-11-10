# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Author: Mohamed Salem (Expert AI Engineer & Automation Architect)
# Focus: AI Engineering | Automation | Agentic Systems
# Copyright (c) 2026. All Rights Reserved.
# -------------------------------------------------------------------------------
"""Multi-link motion localisation (RF-tomography style heat map).

Each link (tx -> rx) is disturbed when a person stands near the straight line
between its endpoints (first Fresnel-zone-like ellipse). For every grid cell the
weight of a link is ``exp(-(d(p,tx)+d(p,rx)-L)^2 / (2*w^2))``; cells are scored by
the sum of link motion z-scores times those weights.

Accuracy is bounded by link geometry: one link only localises *to its ellipse*
(no bearing); three or more well-spread links give position estimates.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional

import numpy as np


class Localizer:
    def __init__(self, links: List[dict], bounds=(-5.0, 5.0, -5.0, 5.0), n: int = 40,
                 width: float = 0.6, smooth: float = 0.6, min_z: float = 2.0):
        self.links = {l["id"]: l for l in links}
        x0, x1, y0, y1 = bounds
        self.bounds, self.n, self.min_z, self.smooth = bounds, n, min_z, smooth
        xs, ys = np.linspace(x0, x1, n), np.linspace(y0, y1, n)
        self.X, self.Y = np.meshgrid(xs, ys)
        self.weights: Dict[str, np.ndarray] = {}
        for lid, l in self.links.items():
            tx, rx = np.array(l["tx"], float), np.array(l["rx"], float)
            L = float(np.linalg.norm(tx - rx))
            d = np.hypot(self.X - tx[0], self.Y - tx[1]) + np.hypot(self.X - rx[0], self.Y - rx[1])
            self.weights[lid] = np.exp(-((d - L) ** 2) / (2 * width ** 2))
        self.z: Dict[str, float] = {k: 0.0 for k in self.links}
        self.heat = np.zeros((n, n))

    def set_z(self, link_id: str, z: float) -> None:
        if link_id in self.z:
            self.z[link_id] = max(0.0, min(12.0, z))

    def step(self) -> dict:
        zmax = max(self.z.values())
        active = sum(1 for z in self.z.values() if z >= self.min_z)
        raw = np.zeros_like(self.heat)
        if zmax >= self.min_z:
            # least-squares match of observed (normalised) link disturbance to the
            # expected ellipse response; quiet links count as evidence too, which
            # removes the bias towards the room centre where many ellipses cross
            err = np.zeros_like(self.heat)
            for lid, z in self.z.items():
                o = z / zmax if z >= self.min_z else 0.0
                err += (o - self.weights[lid]) ** 2
            raw = zmax * np.exp(-err / (2 * 0.35 ** 2 * max(1, len(self.z)) / 2))
        self.heat = self.smooth * self.heat + (1 - self.smooth) * raw
        peak = float(self.heat.max()) if zmax >= self.min_z or self.heat.max() > 0.5 else 0.0
        est: Optional[dict] = None
        if peak > 0.5 and active:
            # weighted centroid of the top cells = sub-cell accuracy
            mask = self.heat >= 0.7 * peak
            w = self.heat[mask]
            x = float((self.X[mask] * w).sum() / w.sum())
            y = float((self.Y[mask] * w).sum() / w.sum())
            spread = math.sqrt(float((((self.X[mask] - x) ** 2 + (self.Y[mask] - y) ** 2) * w).sum() / w.sum()))
            # one link => line-only ambiguity; confidence rises with links & crossing
            conf = min(1.0, 0.25 + 0.25 * (active - 1)) * (1.0 / (1.0 + spread / 2.0))
            est = {"x": round(x, 2), "y": round(y, 2), "radius": round(max(0.4, spread), 2),
                   "confidence": round(conf, 2), "links": active}
        norm = max(peak, 4.0)
        grid = np.round(self.heat / norm, 2)
        return {"grid": grid.tolist(), "estimate": est, "bounds": list(self.bounds), "n": self.n}

    def geometry(self) -> List[dict]:
        return [{"id": k, "tx": v["tx"], "rx": v["rx"], "z": round(self.z[k], 2)} for k, v in self.links.items()]
