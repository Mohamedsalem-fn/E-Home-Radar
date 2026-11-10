# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Author: Mohamed Salem (Expert AI Engineer & Automation Architect)
# Focus: AI Engineering | Automation | Agentic Systems
# Copyright (c) 2026. All Rights Reserved.
# -------------------------------------------------------------------------------
"""Command line interface."""
from __future__ import annotations

import argparse
import csv
import logging
import shutil
import sys
import time

from . import __version__
from .config import load_config
from .sensors import detect_interface, default_gateway, parse_station_dump
import subprocess


def cmd_doctor(cfg, a) -> int:
    ok = True

    def line(name, good, detail=""):
        nonlocal ok
        ok &= bool(good)
        print(f"[{'OK' if good else 'FAIL'}] {name} {detail}")

    iface = cfg.sensor.interface or detect_interface()
    line("iw installed", shutil.which("iw"))
    line("wifi interface", iface, f"({iface})")
    gw = default_gateway()
    line("default gateway", gw, f"({gw})")
    line("ping installed", shutil.which("ping"))
    if iface:
        t0, n, vals = time.time(), 0, []
        while time.time() - t0 < 3:
            out = subprocess.run(["iw", "dev", iface, "station", "dump"], capture_output=True, text=True).stdout
            s = parse_station_dump(out)
            if s:
                n += 1
                vals.append(s.values[0])
            time.sleep(0.05)
        line("RSSI readable (no root)", n > 0, f"{n / 3:.1f} Hz, last={vals[-1] if vals else 'n/a'} dBm")
    print("notify-send:", "available" if shutil.which("notify-send") else "missing (desktop alerts disabled)")
    return 0 if ok else 1


def cmd_run(cfg, a) -> int:
    import uvicorn

    from .engine import Engine
    from .server import create_app

    if a.sim:
        cfg.sensor.kind = "sim"
    if a.profile:
        cfg.detector.profile = a.profile
    if a.port:
        cfg.server.port = a.port
    if cfg.sensor.kind == "sim" and len(cfg.radar.links) < 2:
        cfg.radar.links = [
            {"id": "A", "tx": [-3.5, 3.5], "rx": [3.5, 3.5]},
            {"id": "B", "tx": [-3.5, -3.5], "rx": [3.5, -3.5]},
            {"id": "C", "tx": [-3.5, 3.5], "rx": [-3.5, -3.5]},
            {"id": "D", "tx": [3.5, 3.5], "rx": [3.5, -3.5]},
            {"id": "E", "tx": [-3.5, 3.5], "rx": [3.5, -3.5]},
            {"id": "F", "tx": [3.5, 3.5], "rx": [-3.5, -3.5]},
        ]
    cfg.validate()
    sensor = None
    if cfg.sensor.kind == "sim":
        from .sensors import SimulatedSensor

        sensor = SimulatedSensor(cfg.sensor, links=cfg.radar.links)
    eng = Engine(cfg, sensor=sensor)
    print(f"E-Home Radar {__version__} → http://{cfg.server.host}:{cfg.server.port}  (sensor={cfg.sensor.kind})")
    uvicorn.run(create_app(eng), host=cfg.server.host, port=cfg.server.port, log_level="warning")
    return 0


def cmd_simulate(cfg, a) -> int:
    """Run the pipeline offline on simulated data (fast, no hardware) and print events."""
    from .dsp.detector import MotionDetector
    from .sensors import SimulatedSensor

    cfg.sensor.kind = "sim"
    sensor = SimulatedSensor(cfg.sensor, realtime=False, start_ts=1000.0)
    det = MotionDetector(cfg.detector, cfg.sensor.rate_hz)
    for s in sensor:
        det.update(s)
        if s.ts - 1000.0 > a.seconds:
            break
    print(f"{len(det.finished_events)} events in {a.seconds}s simulated")
    for e in det.finished_events:
        print(f"  t={e.start - 1000:6.1f}s  dur={e.duration:5.1f}s  peak={e.peak_score:5.1f}")
    return 0


def cmd_export(cfg, a) -> int:
    from .storage import Storage

    st = Storage(cfg.storage.path, cfg.storage.retention_days)
    w = csv.writer(sys.stdout)
    if a.what == "events":
        w.writerow(["id", "start", "end", "duration", "peak"])
        for e in st.events(limit=100000):
            w.writerow([e["id"], e["start"], e["end"], e["duration"], e["peak"]])
    else:
        w.writerow(["ts", "raw", "score", "state"])
        for r in st.samples(since=time.time() - a.hours * 3600, limit=10**7):
            w.writerow([r["ts"], r["raw"], r["score"], r["state"]])
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser("ehome-radar", description="Wi-Fi based motion detection")
    p.add_argument("-c", "--config", help="YAML config path")
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("--version", action="version", version=__version__)
    sp = p.add_subparsers(dest="cmd", required=True)
    r = sp.add_parser("run", help="start service + dashboard")
    r.add_argument("--sim", action="store_true", help="use simulated sensor")
    r.add_argument("--profile", choices=["low", "medium", "high"])
    r.add_argument("--port", type=int)
    sp.add_parser("doctor", help="check environment and hardware")
    s = sp.add_parser("simulate", help="offline simulation")
    s.add_argument("--seconds", type=int, default=200)
    e = sp.add_parser("export", help="export CSV to stdout")
    e.add_argument("what", choices=["events", "samples"])
    e.add_argument("--hours", type=float, default=24)
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        cfg = load_config(a.config)
    except Exception as ex:
        print(f"config error: {ex}", file=sys.stderr)
        return 2
    return {"run": cmd_run, "doctor": cmd_doctor, "simulate": cmd_simulate, "export": cmd_export}[a.cmd](cfg, a)


if __name__ == "__main__":
    sys.exit(main())

