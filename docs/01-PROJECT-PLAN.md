# 01 — Project Plan: E-Home Radar (Wireless Motion Detection System)

> Author: Mohamed Salem — Expert AI Engineer & Automation Architect

## 1. Vision
A professional, local-first motion-detection system that uses ambient Wi-Fi radio
signals (device-free sensing) to detect presence and movement in a room, running
entirely on the user's own Linux machine with no cloud and no camera.

## 2. Hardware Reality (verified on target machine)
| Item | Finding | Consequence |
|---|---|---|
| Wi-Fi NIC | `wlo1`, managed, connected to 2.4 GHz ch.6 | No CSI, no monitor mode needed |
| `iw dev wlo1 station dump` | Works without root, ~4 ms/call | Per-sample RSSI at 10–50 Hz |
| Python | 3.12, venv available | Isolated environment |
| Root | Not assumed | System must work unprivileged |

**Decision:** Primary sensor = RSSI (+ bitrate, beacon-signal, retry counters)
sampled from the connected link while a light ICMP/UDP "probe" keeps the link
refreshed. Optional plug-in sensor = ESP32 CSI over serial/UDP (far more sensitive).

## 3. Reference Open-Source Projects (GitHub) and What We Borrow
| Repo | Idea adopted |
|---|---|
| francescopace/espectre | Moving-variance motion score, automatic calibration, threshold + hysteresis, Home-Assistant-style `motion_detected` / `movement_score` entities |
| espressif/esp-csi | CSI packet semantics (I/Q pairs per subcarrier → amplitude) |
| StevenMHernandez/ESP32-CSI-Tool | `CSI_DATA,...` serial line format we parse |
| nexmonster/nexmon_csi | Documented as future hardware path (Broadcom/RPi) |
| WiWave-style dashboards | Multi-link fusion, live spectral view, SQLite event journal |

## 4. Scope
**In scope (v1.0):**
1. Sensor abstraction layer (iw RSSI, ESP32-CSI serial, UDP CSI, simulator).
2. DSP pipeline: Hampel outlier removal → smoothing → sliding variance / MAD →
   adaptive baseline → band-energy (spectral) → fused motion score.
3. Auto-calibration (empty-room baseline learning) and continuous drift adaptation.
4. State machine: `CALIBRATING → IDLE → MOTION → COOLDOWN` with hysteresis.
5. Persistence: SQLite (events + periodic samples) with retention.
6. Service: FastAPI REST + WebSocket + live web dashboard.
7. Alerts: desktop notification (`notify-send`), webhook, MQTT-ready hook.
8. CLI: `run`, `calibrate`, `doctor`, `simulate`, `export`.
9. Tests (pytest), CI-ready, systemd user unit, Docker-free install script.
10. Full documentation set.

**Out of scope:** pose estimation, through-wall imaging, firmware flashing.

## 5. Milestones
| # | Milestone | Deliverable | Exit criteria |
|---|---|---|---|
| M0 | Research & docs | `docs/` complete | Reviewed |
| M1 | Core DSP | `dsp/*` + tests | Synthetic motion detected, false-alarm rate <1/h on noise |
| M2 | Sensors | `sensors/*` | `doctor` reads live RSSI |
| M3 | Engine | state machine, storage | Events persisted |
| M4 | Service + UI | API/WS/dashboard | Live plot works |
| M5 | Ops | systemd, alerts, install | Runs as service |
| M6 | Hardening | tests, docs, GitHub | All green, pushed |

## 6. Non-Functional Requirements
- Latency: detection < 2 s from onset.
- CPU < 3 % on a laptop. Memory < 150 MB.
- Zero root requirement; no external network; localhost-bound by default.
- Graceful degradation: sensor loss → `SENSOR_LOST` status, auto-reconnect.

## 7. Risks
| Risk | Mitigation |
|---|---|
| RSSI is noisy / quantized (1 dB) | Probe traffic, Hampel, multi-feature fusion, adaptive thresholds |
| Own movement near the laptop | Documented placement guide; sensitivity profiles |
| AP changes channel/roams | Detect BSSID change → re-calibrate |
| Wi-Fi power-save lowers sample rate | Probe traffic + `doctor` warns |

## 8. Credits
Designed and built by **Mohamed Salem** — Expert AI Engineer & Automation Architect.
