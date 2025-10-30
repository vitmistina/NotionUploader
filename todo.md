# Todo

You will help me process gym workouts saved in notion database which are missing TSS and IF and Type.
To see structure of the workout look in src\models\workout.py

- [ ] Implement HR-based IF & TSS estimator (power-free) for gym/workouts missing metrics.

  **Inputs**
  - `hr_avg` (bpm), `hr_max_session` (bpm), `dur_s` (sec), `kcal` (kcal; optional),
    `hr_max` (bpm), `hr_rest` (bpm; fallback 66).

  **Steps**
  1) Compute LTHR (threshold HR) estimate:
     - `lthr_guess = 0.90 * hr_max`
     - `lthr = min(lthr_guess, max(0.85 * hr_max, 0.98 * hr_max_session))`

  2) Ranges (guard zeros):
     - `hr_range  = max(1, hr_max - hr_rest)`
     - `thr_range = max(1, lthr   - hr_rest)`

  3) Base IF from HRR relative to threshold:
     - `if_base = (hr_avg - hr_rest) / thr_range`

  4) Anaerobic spikiness bump (optional, small):
     - `supra     = max(0, hr_max_session - lthr)`
     - `supra_cap = max(1, hr_max - lthr)`
     - `bump      = 0.08 * (supra / supra_cap)`  # ≤ +0.08 at all-out
     - `if_est    = clamp(if_base + bump, 0.30, 1.35)`

  5) Edge cases:
     - If `hr_avg <= hr_rest + 5`: `if_est = 0.30`
     - If `lthr <= hr_rest + 10`: recompute `lthr = 0.90 * hr_max` and redo Step 3–4.

  6) TSS (hrTSS analogue):
     - `tss = (dur_s / 3600) * if_est * 100`

  7) Return `(round(if_est, 2), round(tss, 1))`.

  **Rationale**
  - Uses HR Reserve relative to threshold to proxy metabolic strain.
  - Small spikiness bump mitigates HR lag undercounting for brief hard efforts.
  - Caps prevent inflation in short mixed gym sessions.

- [ ] New helper method wires this estimator into old entries and future uploads.
- [ ] New endpoint: trigger fill-by-Notion-ID for workouts missing IF/TSS/Type.
