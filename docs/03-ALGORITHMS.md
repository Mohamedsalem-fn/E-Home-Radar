# 03 — Signal Processing & Detection Algorithms

> Author: Mohamed Salem — Expert AI Engineer & Automation Architect

## Physics
A person moving changes multipath propagation, which perturbs received signal
strength (and, with CSI, per-subcarrier amplitude/phase). A static room yields a
stable signal with low short-term variance; motion raises variance and
mid-frequency energy (0.3–5 Hz for body motion, 0.1–0.5 Hz for breathing).

## Pipeline (per sample, rate ≈ 10–50 Hz)
1. **Hampel filter** (window 7, k = 3·1.4826·MAD): removes spikes from scan/roam glitches.
2. **EMA** (α = 0.3): light smoothing; preserves motion transients.
3. **Features over sliding window W (default 2 s):**
   - `var`: variance of filtered signal
   - `mad`: median absolute deviation (robust)
   - `diff`: mean |x[t] − x[t−1]| (jitter energy)
   - `band`: spectral energy in 0.3–5 Hz via FFT (Hann window)
4. **Raw activity** `a = log(w1·√var + w2·mad + w3·diff + w4·√band + 0.05)` (weights in config).
   The log domain is deliberate: raw activity on quantised RSSI is heavily right-skewed
   (z up to 6.7 on pure noise); in log domain noise is ~symmetric. Measured: **0 false alarms
   in 6 h of simulated static noise** (6 seeds, 1 h each) versus 1–54 ticks/30 min linear.
5. **Adaptive baseline**: during calibration (default 20 s) collect `a`; set
   `μ` = median, `σ` = max(1.4826·MAD, (P95−μ)/1.645, σ_min). Afterward, when state is IDLE, update
   baseline slowly (EWMA, τ ≈ 5 min) so thermal/AP drift is absorbed.
6. **Motion score** `z = (a − μ) / max(σ, σ_min)`; mapped to 0–100 for display.
7. **State machine with hysteresis:**
   - `IDLE → MOTION` when `z > T_on` for ≥ `on_count` consecutive evaluations
   - `MOTION → COOLDOWN` when `z < T_off` (T_off < T_on)
   - `COOLDOWN → IDLE` after `hold_s` without re-trigger (default 5 s)
   - Re-trigger in cooldown returns to MOTION (same event, extended).
8. **Re-calibration triggers:** BSSID/channel change, sensor gap > 30 s.

## Sensitivity profiles
| Profile | T_on | T_off | on_count |
|---|---|---|---|
| low | 6.0 | 3.0 | 6 |
| medium | 4.0 | 2.0 | 4 |
| high | 2.8 | 1.5 | 3 |

## CSI path
`CSI_DATA` lines contain interleaved (imag, real) int8 pairs. Amplitude per
subcarrier = √(re²+im²); null subcarriers (guard bands) are dropped; the vector
is reduced to the mean absolute deviation across subcarriers from a rolling
per-subcarrier mean, giving a scalar far more sensitive than RSSI.

## Validation strategy
- Unit tests with synthetic static noise (no false alarm) and injected bursts (detected).
- Latency test: onset → MOTION within 2 s.
- `simulate` command for demos without hardware.
