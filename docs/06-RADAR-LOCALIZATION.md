# 06 — Radar View & Motion Localisation

> Author: Mohamed Salem — Expert AI Engineer & Automation Architect

## What the radar shows
A top-down room map (metres) with range rings, a rotating sweep, the sensing links
(blue = quiet, red = disturbed), a live **heat map** of where motion is, a target
marker with uncertainty radius and confidence, and a short movement trail.

## Honest accuracy model
Position comes from **links** (transmitter→receiver pairs). A person disturbs a link
only when standing near the straight line between its endpoints (an ellipse ≈ 0.6 m wide).

| Links | What you get |
|---|---|
| 1 (laptop ↔ router; default) | Motion **zone** along that link, no bearing; confidence capped at 25 % |
| 3+ spread around the room | Position estimate; mean error ≈ 0.6 m in noise-free simulation |
| 6 (ESP32 mesh, CSI) | Best case; accuracy depends on real RF conditions |

A single-NIC laptop cannot produce a true direction. For real "where" accuracy add
ESP32 nodes and describe their coordinates in `config.yaml`.

## Algorithm (`localize.py`)
1. Each link has its own detector (calibration, hysteresis); `z` = link motion z-score.
2. For each grid cell p: expected response `w_i(p)=exp(-(d(p,tx)+d(p,rx)-L)²/2σ²)`.
3. Observed `o_i = z_i/max z` (quiet links = 0). Cell likelihood = exp(−Σ(o_i−w_i)²/…).
   Quiet links count as evidence, removing the centre bias of simple summation.
4. Temporal smoothing, weighted centroid of cells ≥ 70 % of peak → (x, y, radius, confidence).

## Configuration
```yaml
radar:
  bounds: [-5, 5, -5, 5]          # metres
  links:
    - {id: main, tx: [3.0, 0.0], rx: [0.0, 0.0]}   # AP at 3 m east of the laptop
```
Multi-link feeds: a sensor tags each sample with `meta["link"]=<id>`
(the simulator and ESP32 nodes do; `run --sim` demos 6 links).

## API
`GET /api/radar` and WebSocket `radar` messages (5 Hz): `grid`, `estimate`, `links`, `bounds`.
