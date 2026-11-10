# 04 — Installation, Operations & Tuning

> Author: Mohamed Salem — Expert AI Engineer & Automation Architect

## Install
```bash
./deploy/install.sh            # venv + deps + doctor
./deploy/install.sh --service  # also enable systemd user service
```
## Run
```bash
.venv/bin/ehome-radar doctor        # verify hardware & tooling
.venv/bin/ehome-radar run           # http://127.0.0.1:8787
.venv/bin/ehome-radar run --sim     # demo without hardware
.venv/bin/ehome-radar simulate      # offline algorithm check
.venv/bin/ehome-radar export events > events.csv
```
## First-run procedure
1. Place the laptop where the room is visible to the Wi-Fi link (between you and the AP works best).
2. Start the service and **leave the room still for 20 s** (state `CALIBRATING` → `IDLE`).
3. Walk around: state flips to `MOTION`, desktop notification fires, event stored.
4. Adjust sensitivity (`low|medium|high`) in the dashboard or config.

## REST / WebSocket API
| Endpoint | Method | Description |
|---|---|---|
| `/api/health` | GET | liveness |
| `/api/status` | GET | state, baseline, thresholds, sample lag |
| `/api/latest` | GET | most recent reading |
| `/api/history?seconds=120` | GET | in-memory readings |
| `/api/events?limit=100` | GET | persisted motion events |
| `/api/calibrate` | POST | restart calibration |
| `/api/profile` | POST `{"name":"high"}` | change sensitivity |
| `/ws` | WS | `hello`, `reading` (5 Hz), `event` messages |

## Using ESP32 CSI (optional, far more sensitive)
Flash `espressif/esp-csi` or `StevenMHernandez/ESP32-CSI-Tool` (active STA/AP mode), connect via USB, then:
```yaml
sensor: {kind: csi-serial, serial_port: /dev/ttyUSB0, rate_hz: 50}
```
or stream `CSI_DATA` lines over UDP to port 5005 with `kind: csi-udp`.

## Troubleshooting
| Symptom | Fix |
|---|---|
| `SENSOR_LOST` | `doctor`; check `iw` and that Wi-Fi is connected; auto-retries with backoff |
| False alarms | use `low` profile, move laptop away from fans/pets, recalibrate |
| Missed motion | `high` profile; ensure `probe: true`; consider CSI hardware |
| Port busy | `run --port 8790` |
| Roaming | BSSID change auto-recalibrates |

## Security
Binds to localhost only. To expose on LAN set `server.host`, and put a reverse proxy with auth in front (no built-in auth).


## Radar view
The dashboard is a radar map; see [06-RADAR-LOCALIZATION.md](06-RADAR-LOCALIZATION.md).
Set the AP position in `radar.links[0].tx` (metres from the laptop). Demo: `ehome-radar run --sim`.
