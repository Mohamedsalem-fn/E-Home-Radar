# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Author: Mohamed Salem (Expert AI Engineer & Automation Architect)
# Focus: AI Engineering | Automation | Agentic Systems
# Copyright (c) 2026. All Rights Reserved.
# -------------------------------------------------------------------------------
"""Configuration with validation. Loads YAML and overlays defaults."""
from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Optional

PROFILES = {
    "low": dict(t_on=6.0, t_off=3.0, on_count=6),
    "medium": dict(t_on=4.0, t_off=2.0, on_count=4),
    "high": dict(t_on=2.8, t_off=1.5, on_count=3),
}


@dataclass
class SensorConfig:
    kind: str = "iw"  # iw | csi-serial | csi-udp | sim
    interface: str = ""  # empty = auto-detect
    rate_hz: float = 20.0
    probe: bool = True  # generate light traffic to the gateway
    serial_port: str = "/dev/ttyUSB0"
    serial_baud: int = 921600
    udp_port: int = 5005


@dataclass
class DetectorConfig:
    profile: str = "medium"
    window_s: float = 2.0
    calibration_s: float = 20.0
    hold_s: float = 5.0
    sigma_min: float = 0.05
    drift_tau_s: float = 300.0
    eval_hz: float = 5.0
    w_var: float = 1.0
    w_mad: float = 1.0
    w_diff: float = 1.0
    w_band: float = 0.5


@dataclass
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 8787


@dataclass
class AlertConfig:
    desktop: bool = True
    webhook_url: str = ""
    min_event_s: float = 0.0


@dataclass
class StorageConfig:
    path: str = "~/.local/share/ehome-radar/radar.db"
    retention_days: int = 30
    sample_every_s: float = 1.0


@dataclass
class Config:
    sensor: SensorConfig = field(default_factory=SensorConfig)
    detector: DetectorConfig = field(default_factory=DetectorConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    alerts: AlertConfig = field(default_factory=AlertConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)

    def validate(self) -> "Config":
        if self.detector.profile not in PROFILES:
            raise ValueError(f"profile must be one of {sorted(PROFILES)}")
        if self.sensor.rate_hz <= 0 or self.sensor.rate_hz > 200:
            raise ValueError("sensor.rate_hz must be in (0, 200]")
        if self.detector.window_s < 0.5:
            raise ValueError("detector.window_s must be >= 0.5")
        if self.sensor.kind not in ("iw", "csi-serial", "csi-udp", "sim"):
            raise ValueError("unknown sensor.kind")
        return self


def _apply(obj, data: dict):
    for f in fields(obj):
        if f.name in data:
            cur = getattr(obj, f.name)
            if is_dataclass(cur):
                _apply(cur, data[f.name] or {})
            else:
                setattr(obj, f.name, type(cur)(data[f.name]))


def load_config(path: Optional[str] = None) -> Config:
    cfg = Config()
    if path:
        import yaml

        p = Path(path).expanduser()
        if not p.exists():
            raise FileNotFoundError(p)
        _apply(cfg, yaml.safe_load(p.read_text()) or {})
    return cfg.validate()
