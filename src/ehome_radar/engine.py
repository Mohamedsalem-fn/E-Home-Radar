# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Author: Mohamed Salem (Expert AI Engineer & Automation Architect)
# Focus: AI Engineering | Automation | Agentic Systems
# Copyright (c) 2026. All Rights Reserved.
# -------------------------------------------------------------------------------
"""Engine: sensor thread -> DSP -> state machine -> storage/alerts/subscribers."""
from __future__ import annotations

import logging
import threading
import time
from collections import deque
from typing import Callable, Deque, List, Optional

from .alerts import Alerts
from .config import Config
from .dsp.detector import MotionDetector
from .localize import Localizer
from .models import Reading, State
from .sensors import Sensor, make_sensor
from .storage import Storage

log = logging.getLogger("ehome.engine")


class Engine:
    def __init__(self, cfg: Config, sensor: Optional[Sensor] = None, storage: Optional[Storage] = None,
                 alerts: Optional[Alerts] = None):
        self.cfg = cfg
        self.sensor = sensor
        self.storage = storage or Storage(cfg.storage.path, cfg.storage.retention_days)
        self.alerts = alerts or Alerts(cfg.alerts)
        self.detector = MotionDetector(cfg.detector, cfg.sensor.rate_hz)  # primary link
        self.detectors = {}
        for l in cfg.radar.links:
            self.detectors[l["id"]] = self.detector if not self.detectors else MotionDetector(cfg.detector, cfg.sensor.rate_hz)
        self.localizer = Localizer(cfg.radar.links, tuple(cfg.radar.bounds))
        self.radar_state: dict = {}
        self._last_radar = 0.0
        self.history: Deque[dict] = deque(maxlen=1200)  # ~4 min @ 5 Hz
        self.latest: Optional[Reading] = None
        self.last_sample_ts = 0.0
        self.sample_count = 0
        self.subscribers: List[Callable[[dict], None]] = []
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._last_persist = 0.0
        self._last_state = State.CALIBRATING
        self._last_purge = time.time()

    # --------------------------------------------------------------- lifecycle
    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._run, name="engine", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self.sensor:
            self.sensor.close()
        if self._thread:
            self._thread.join(timeout=3)

    def _run(self) -> None:
        backoff = 1.0
        while self._running:
            try:
                if self.sensor is None:
                    self.sensor = make_sensor(self.cfg.sensor)
                for s in self.sensor:
                    if not self._running:
                        break
                    backoff = 1.0
                    self.process(s)
                if self._running:
                    raise RuntimeError("sensor stream ended")
            except Exception as e:
                log.error("sensor error: %s (retry in %.0fs)", e, backoff)
                self.detector.state = State.SENSOR_LOST
                self.sensor = None
                time.sleep(backoff)
                backoff = min(30.0, backoff * 2)
                self.detector.recalibrate()

    # ----------------------------------------------------------------- process
    def process(self, sample) -> Optional[Reading]:
        self.sample_count += 1
        self.last_sample_ts = sample.ts
        lid = sample.meta.get("link", next(iter(self.detectors)))
        det = self.detectors.get(lid)
        if det is None:
            return None
        r = det.update(sample)
        if r is not None:
            moving = r.calibrated and r.state.value in ("MOTION", "COOLDOWN")
            self.localizer.set_z(lid, r.z if moving else 0.0)
        if sample.ts - self._last_radar >= 0.2:
            self._last_radar = sample.ts
            self.radar_state = {**self.localizer.step(), "links": self.localizer.geometry(), "ts": sample.ts}
            self.publish({"type": "radar", **self.radar_state})
        if det is not self.detector:
            return r
        for ev in self.detector.finished_events:
            ev.id = self.storage.add_event(ev)
            log.info("event %d: %.1fs peak %.0f", ev.id, ev.duration, ev.peak_score)
            self.publish({"type": "event", "event": dict(start=ev.start, end=ev.end, peak=ev.peak_score)})
        self.detector.finished_events.clear()
        if r is None:
            return None
        self.latest = r
        d = r.to_dict()
        self.history.append(d)
        if r.state == State.MOTION and self._last_state != State.MOTION:
            self.alerts.fire("MOTION", d)
            log.info("MOTION detected (score %.0f)", r.score)
        self._last_state = r.state
        if r.ts - self._last_persist >= self.cfg.storage.sample_every_s:
            self._last_persist = r.ts
            self.storage.add_sample(r)
        if time.time() - self._last_purge > 3600:
            self._last_purge = time.time()
            self.storage.purge()
        self.publish({"type": "reading", **d})
        return r

    def recalibrate_all(self) -> None:
        for d in self.detectors.values():
            d.recalibrate()

    def set_profile_all(self, name: str) -> None:
        for d in self.detectors.values():
            d.set_profile(name)

    def publish(self, msg: dict) -> None:
        for fn in list(self.subscribers):
            try:
                fn(msg)
            except Exception:
                pass

    def status(self) -> dict:
        d = self.detector
        lag = time.time() - self.last_sample_ts if self.last_sample_ts else None
        return {
            "state": d.state.value,
            "calibrated": d.calibrated,
            "profile": d.cfg.profile,
            "sensor": getattr(self.sensor, "name", "none"),
            "samples": self.sample_count,
            "baseline": {"mu": round(d.mu, 4), "sigma": round(d.sigma, 4)},
            "thresholds": {"on": d.t_on, "off": d.t_off},
            "sample_lag_s": None if lag is None else round(lag, 2),
        }

