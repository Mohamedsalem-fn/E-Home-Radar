# 05 — Testing & Validation Report

> Author: Mohamed Salem — Expert AI Engineer & Automation Architect

| Area | Test | Result |
|---|---|---|
| Calibration | completes → IDLE | pass |
| False alarms | 10 min static noise, no MOTION; 6 × 1 h sweep: 0 | pass |
| Latency | motion onset → MOTION < 2.5 s (measured ~1 s at amp 4 dB) | pass |
| Event logging | burst → exactly one event, stored | pass |
| Sensitivity | high ≥ low on weak signals | pass |
| Roaming | BSSID change → CALIBRATING | pass |
| Hampel | spike removed on quantised data | pass |
| CSI | vector path detects variance burst; parser edge cases | pass |
| Config | YAML load + invalid profile rejected | pass |
| Storage | event round-trip | pass |
| API | endpoints, profile validation, WebSocket hello | pass |
| End-to-end | simulator → engine → SQLite | pass |
| Live | `doctor`: RSSI ≈ 19 Hz unprivileged on `wlo1`; service serves API | pass |

Run: `.venv/bin/pytest -q`

## Sensitivity table (simulated, onset-to-detect seconds)
| Amplitude | low | medium | high |
|---|---|---|---|
| 0.8 dB | – | 5.5 | 1.4 |
| 1.5 dB | – | 1.6 | 1.0 |
| 4.0 dB | 2.0 | 1.0 | 0.8 |

