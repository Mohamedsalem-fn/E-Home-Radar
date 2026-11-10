# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Author: Mohamed Salem (Expert AI Engineer & Automation Architect)
# Focus: AI Engineering | Automation | Agentic Systems
# Copyright (c) 2026. All Rights Reserved.
# -------------------------------------------------------------------------------
"""Sensor implementations: iw RSSI, ESP32 CSI (serial/UDP), simulator."""
from __future__ import annotations

import math
import random
import re
import socket
import subprocess
import threading
import time
from typing import Callable, Iterator, List, Optional

from ..config import SensorConfig
from ..models import Sample


class Sensor:
    """Base: iterate to receive Samples. ``close()`` stops it."""

    name = "base"

    def __iter__(self) -> Iterator[Sample]:  # pragma: no cover - interface
        raise NotImplementedError

    def close(self) -> None:
        self._stop = True

    _stop = False


# ---------------------------------------------------------------- helper utils
def detect_interface() -> str:
    try:
        out = subprocess.run(["iw", "dev"], capture_output=True, text=True, timeout=3).stdout
        m = re.search(r"Interface\s+(\S+)", out)
        if m:
            return m.group(1)
    except Exception:
        pass
    return ""


def default_gateway() -> str:
    try:
        out = subprocess.run(["ip", "route"], capture_output=True, text=True, timeout=3).stdout
        m = re.search(r"default via (\S+)", out)
        return m.group(1) if m else ""
    except Exception:
        return ""


_SIG = re.compile(r"signal:\s+(-?\d+)")
_BSS = re.compile(r"Station\s+([0-9a-f:]{17})", re.I)


def parse_station_dump(text: str) -> Optional[Sample]:
    """Parse ``iw dev X station dump`` output (first station) into a Sample."""
    m = _SIG.search(text)
    if not m:
        return None
    meta = {}
    b = _BSS.search(text)
    if b:
        meta["bssid"] = b.group(1).lower()
    return Sample(time.time(), [float(m.group(1))], meta)


# --------------------------------------------------------------------- Prober
class Prober(threading.Thread):
    """Sends light UDP/ICMP traffic to the gateway so signal stats keep refreshing."""

    def __init__(self, host: str, rate_hz: float):
        super().__init__(daemon=True)
        self.host, self.rate, self.stop_flag = host, rate_hz, False

    def run(self) -> None:
        if not self.host:
            return
        try:
            proc = subprocess.Popen(
                ["ping", "-i", f"{max(0.2, 1.0 / self.rate):.2f}", "-q", self.host],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            return
        while not self.stop_flag:
            time.sleep(0.5)
        proc.terminate()


# ------------------------------------------------------------------- IwSensor
class IwSensor(Sensor):
    name = "iw"

    def __init__(self, cfg: SensorConfig):
        self.iface = cfg.interface or detect_interface()
        if not self.iface:
            raise RuntimeError("no Wi-Fi interface found (is iw installed?)")
        self.period = 1.0 / cfg.rate_hz
        self.prober = Prober(default_gateway(), min(cfg.rate_hz, 10)) if cfg.probe else None
        if self.prober:
            self.prober.start()

    def __iter__(self) -> Iterator[Sample]:
        nxt = time.time()
        while not self._stop:
            try:
                out = subprocess.run(
                    ["iw", "dev", self.iface, "station", "dump"],
                    capture_output=True, text=True, timeout=2,
                ).stdout
                s = parse_station_dump(out)
                if s:
                    yield s
            except Exception:
                pass
            nxt += self.period
            time.sleep(max(0.0, nxt - time.time()))

    def close(self) -> None:
        super().close()
        if self.prober:
            self.prober.stop_flag = True


# ------------------------------------------------------------------------ CSI
_CSI = re.compile(r"CSI_DATA,.*?\[([^\]]*)\]")


def parse_csi_line(line: str) -> Optional[Sample]:
    """Parse ESP32-CSI-Tool / esp-csi ``CSI_DATA`` lines containing ``[im,re,...]``."""
    m = _CSI.search(line)
    if not m:
        return None
    try:
        nums = [int(x) for x in m.group(1).replace(",", " ").split()]
    except ValueError:
        return None
    if len(nums) < 8 or len(nums) % 2:
        return None
    amps = [math.hypot(nums[i], nums[i + 1]) for i in range(0, len(nums), 2)]
    amps = [a for a in amps if a > 0]  # drop null subcarriers
    return Sample(time.time(), amps) if amps else None


class CsiSerialSensor(Sensor):
    name = "csi-serial"

    def __init__(self, cfg: SensorConfig):
        import serial  # lazy

        self.ser = serial.Serial(cfg.serial_port, cfg.serial_baud, timeout=1)

    def __iter__(self) -> Iterator[Sample]:
        while not self._stop:
            line = self.ser.readline().decode("utf-8", "ignore")
            s = parse_csi_line(line)
            if s:
                yield s

    def close(self) -> None:
        super().close()
        self.ser.close()


class CsiUdpSensor(Sensor):
    name = "csi-udp"

    def __init__(self, cfg: SensorConfig):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("0.0.0.0", cfg.udp_port))
        self.sock.settimeout(1.0)

    def __iter__(self) -> Iterator[Sample]:
        while not self._stop:
            try:
                data, _ = self.sock.recvfrom(4096)
            except socket.timeout:
                continue
            s = parse_csi_line(data.decode("utf-8", "ignore"))
            if s:
                yield s

    def close(self) -> None:
        super().close()
        self.sock.close()


# ------------------------------------------------------------------ Simulator
class SimulatedSensor(Sensor):
    """Synthetic RSSI with scripted motion bursts. Deterministic with seed."""

    name = "sim"

    def __init__(self, cfg: SensorConfig, seed: int = 7, realtime: bool = True,
                 bursts: Optional[List[tuple]] = None, start_ts: Optional[float] = None,
                 links: Optional[List[dict]] = None):
        self.links = links or []
        self.rate = cfg.rate_hz
        self.rng = random.Random(seed)
        self.realtime = realtime
        # (start_s, end_s, amplitude_db) relative to start; default: periodic bursts
        self.bursts = bursts if bursts is not None else [(30 + 40 * i, 36 + 40 * i, 4.0) for i in range(100)]
        self.t0 = start_ts if start_ts is not None else time.time()

    def __iter__(self) -> Iterator[Sample]:
        i = 0
        while not self._stop:
            t = i / self.rate
            if len(self.links) > 1:
                yield from self._multi(t)
                i += 1
                if self.realtime:
                    time.sleep(1.0 / self.rate)
                continue
            v = -55.0 + self.rng.gauss(0, 0.35)
            for a, b, amp in self.bursts:
                if a <= t < b:
                    v += amp * math.sin(2 * math.pi * 1.3 * t) * self.rng.uniform(0.5, 1.2)
                    v += self.rng.gauss(0, amp * 0.3)
            v = round(v)  # RSSI is quantised to 1 dB
            yield Sample(self.t0 + t, [float(v)], {"bssid": "sim", "channel": "6"})
            i += 1
            if self.realtime:
                time.sleep(1.0 / self.rate)


def _sim_person(t: float):
    # scripted walker: loops an ellipse for 12 s every 30 s, otherwise absent
    ph = t % 30.0
    if ph > 12.0 or t < 25.0:
        return None
    a = 2 * math.pi * ph / 12.0
    return 2.2 * math.cos(a), 1.6 * math.sin(a) + 0.5


def _multi(self, t):
    p = _sim_person(t)
    for l in self.links:
        v = -55.0 + self.rng.gauss(0, 0.35)
        if p:
            tx, rx = l["tx"], l["rx"]
            L = math.hypot(tx[0] - rx[0], tx[1] - rx[1])
            ex = math.hypot(p[0] - tx[0], p[1] - tx[1]) + math.hypot(p[0] - rx[0], p[1] - rx[1]) - L
            amp = 4.0 * math.exp(-(ex ** 2) / (2 * 0.6 ** 2))
            v += amp * math.sin(2 * math.pi * 1.3 * t) * self.rng.uniform(0.6, 1.2) + self.rng.gauss(0, amp * 0.3)
        yield Sample(self.t0 + t, [float(round(v))], {"bssid": l["id"], "channel": "6", "link": l["id"]})


SimulatedSensor._multi = _multi


def make_sensor(cfg: SensorConfig) -> Sensor:
    return {
        "iw": IwSensor,
        "csi-serial": CsiSerialSensor,
        "csi-udp": CsiUdpSensor,
        "sim": SimulatedSensor,
    }[cfg.kind](cfg)

