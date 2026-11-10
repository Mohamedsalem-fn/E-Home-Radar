# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Author: Mohamed Salem (Expert AI Engineer & Automation Architect)
# Focus: AI Engineering | Automation | Agentic Systems
# Copyright (c) 2026. All Rights Reserved.
# -------------------------------------------------------------------------------
import math
import random

import numpy as np
import pytest

from ehome_radar.config import Config, load_config
from ehome_radar.dsp.detector import MotionDetector
from ehome_radar.dsp.filters import Hampel
from ehome_radar.engine import Engine
from ehome_radar.models import Sample, State
from ehome_radar.sensors import SimulatedSensor, parse_csi_line, parse_station_dump
from ehome_radar.storage import Storage

RATE = 20.0


def run(det, seconds, amp=0.0, t0=0.0, seed=1):
    rng = random.Random(seed)
    t = t0
    states = []
    while t < t0 + seconds:
        v = -55 + rng.gauss(0, 0.35)
        if amp:
            v += amp * math.sin(2 * math.pi * 1.3 * t) + rng.gauss(0, amp * 0.3)
        det.update(Sample(t, [float(round(v))]))
        states.append((t, det.state))
        t += 1 / RATE
    return states


def make(profile="medium"):
    cfg = Config()
    cfg.detector.profile = profile
    cfg.detector.calibration_s = 15
    cfg.detector.hold_s = 3
    return MotionDetector(cfg.detector, RATE)


def test_calibration_completes():
    d = make()
    run(d, 25)
    assert d.calibrated and d.state == State.IDLE


def test_no_false_alarm_on_static_noise():
    d = make()
    st = run(d, 600)
    assert all(s != State.MOTION for _, s in st)


def test_motion_detected_with_low_latency():
    d = make()
    run(d, 30)
    st = run(d, 10, amp=4.0, t0=30)
    first = next(t for t, s in st if s == State.MOTION)
    assert first - 30 < 2.5


def test_returns_to_idle_and_logs_event():
    d = make()
    run(d, 30)
    run(d, 8, amp=4.0, t0=30)
    run(d, 15, t0=38)
    assert d.state == State.IDLE
    assert len(d.finished_events) == 1
    assert d.finished_events[0].duration > 3


def test_high_profile_more_sensitive_than_low():
    res = {}
    for p in ("low", "high"):
        d = make(p)
        run(d, 30)
        st = run(d, 10, amp=0.9, t0=30)
        res[p] = sum(1 for _, s in st if s == State.MOTION)
    assert res["high"] >= res["low"]


def test_bssid_change_triggers_recalibration():
    d = make()
    run(d, 30)
    d.update(Sample(31, [-55.0], {"bssid": "aa"}))
    d.update(Sample(31.1, [-55.0], {"bssid": "bb"}))
    assert d.state == State.CALIBRATING


def test_hampel_removes_spike():
    h = Hampel()
    out = [h.update(x) for x in [-55, -55, -56, -55, -20, -55, -55]]
    assert out[4] < -50


def test_csi_vector_scalar_detects_motion():
    d = make()
    rng = np.random.default_rng(3)
    base = rng.uniform(20, 30, 52)
    t = 0.0
    while t < 25:
        d.update(Sample(t, list(base + rng.normal(0, 0.1, 52))))
        t += 1 / RATE
    assert d.calibrated
    while t < 32:
        d.update(Sample(t, list(base + rng.normal(0, 3.0, 52))))
        t += 1 / RATE
    assert d.state in (State.MOTION, State.COOLDOWN)


def test_parse_station_dump():
    txt = "Station f6:fc:49:2c:ab:e8 (on wlo1)\n\tsignal:  \t-54 [-54] dBm\n"
    s = parse_station_dump(txt)
    assert s.values == [-54.0] and s.meta["bssid"] == "f6:fc:49:2c:ab:e8"
    assert parse_station_dump("") is None


def test_parse_csi_line():
    s = parse_csi_line("CSI_DATA,1,aa:bb,-50,11,[3,4,0,0,6,8,1,1]")
    assert s and len(s.values) == 3 and s.values[0] == 5.0
    assert parse_csi_line("garbage") is None
    assert parse_csi_line("CSI_DATA,[1,2,3]") is None


def test_config_validation(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text("detector:\n  profile: high\nsensor:\n  rate_hz: 10\n")
    c = load_config(str(p))
    assert c.detector.profile == "high" and c.sensor.rate_hz == 10.0
    p.write_text("detector:\n  profile: nope\n")
    with pytest.raises(ValueError):
        load_config(str(p))


def test_storage_roundtrip():
    from ehome_radar.models import Event

    st = Storage(":memory:")
    i = st.add_event(Event(100, 110, 88.0))
    ev = st.events()
    assert ev[0]["id"] == i and ev[0]["duration"] == 10.0


def test_engine_end_to_end_with_simulator():
    cfg = Config()
    cfg.detector.calibration_s = 15
    cfg.detector.hold_s = 3
    cfg.alerts.desktop = False
    cfg.storage.path = ":memory:"
    sim = SimulatedSensor(cfg.sensor, realtime=False, start_ts=0.0,
                          bursts=[(30, 36, 4.0)])
    eng = Engine(cfg, sensor=sim)
    for s in sim:
        eng.process(s)
        if s.ts > 60:
            break
    ev = eng.storage.events()
    assert len(ev) == 1 and 30 <= ev[0]["start"] <= 33

