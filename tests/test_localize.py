# -*- coding: utf-8 -*-
# Author: Mohamed Salem (Expert AI Engineer & Automation Architect) | (c) 2026
import math

from ehome_radar.localize import Localizer

LINKS = [
    {"id": "A", "tx": [-3.5, 3.5], "rx": [3.5, 3.5]},
    {"id": "B", "tx": [-3.5, -3.5], "rx": [3.5, -3.5]},
    {"id": "C", "tx": [-3.5, 3.5], "rx": [-3.5, -3.5]},
    {"id": "D", "tx": [3.5, 3.5], "rx": [3.5, -3.5]},
    {"id": "E", "tx": [-3.5, 3.5], "rx": [3.5, -3.5]},
    {"id": "F", "tx": [3.5, 3.5], "rx": [-3.5, -3.5]},
]


def z_for(p, l):
    tx, rx = l["tx"], l["rx"]
    L = math.dist(tx, rx)
    ex = math.dist(p, tx) + math.dist(p, rx) - L
    return 10.0 * math.exp(-(ex ** 2) / (2 * 0.6 ** 2))


def locate(p, links=LINKS):
    loc = Localizer(links)
    for _ in range(12):
        for l in links:
            loc.set_z(l["id"], z_for(p, l))
        out = loc.step()
    return out["estimate"]


def test_localisation_accuracy_multilink():
    errs = []
    for p in [(1.0, 1.0), (-2.0, 0.5), (0.0, -2.5), (2.2, -1.2), (-1.5, 2.0)]:
        e = locate(p)
        assert e is not None
        errs.append(math.dist(p, (e["x"], e["y"])))
    assert sum(errs) / len(errs) < 0.8, errs


def test_no_estimate_when_quiet():
    loc = Localizer(LINKS)
    assert loc.step()["estimate"] is None


def test_single_link_low_confidence():
    e = locate((1.0, 0.0), [{"id": "A", "tx": [3, 0], "rx": [0, 0]}])
    assert e is not None and e["confidence"] <= 0.25 and e["links"] == 1
