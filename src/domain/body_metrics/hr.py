"""Heart rate derived metrics."""

from __future__ import annotations

from typing import Any, List, Optional, Tuple


def hr_drift_from_splits(splits: List[dict[str, Any]]) -> float:
    """Calculate heart rate drift percentage from distance splits."""
    if not splits:
        return 0.0

    half = len(splits) // 2
    if half == 0:
        return 0.0

    def average_hr(values: List[dict[str, Any]]) -> Optional[float]:
        hrs: List[float] = []
        for split in values:
            hr = split.get("average_heartrate")
            if hr is None:
                continue
            try:
                hr_value = float(hr)
            except (TypeError, ValueError):
                continue
            if hr_value <= 0:
                continue
            hrs.append(hr_value)
        if not hrs:
            return None
        return sum(hrs) / len(hrs)

    first_avg = average_hr(splits[:half])
    second_avg = average_hr(splits[half:])

    if first_avg is None or second_avg is None or first_avg == 0:
        return 0.0

    return (second_avg - first_avg) / first_avg * 100


def estimate_if_tss_from_hr(
    *,
    hr_avg_session: Optional[float],
    hr_max_session: Optional[float],
    dur_s: Optional[float],
    hr_max_athlete: Optional[float],
    hr_rest_athlete: Optional[float] = None,
    kcal: Optional[float] = None,
) -> Optional[Tuple[float, float]]:
    """Estimate IF and TSS from heart-rate data when power metrics are absent."""
    del kcal  # appease linters while keeping signature parity for future use

    if (
        hr_avg_session is None
        or hr_max_session is None
        or dur_s is None
        or dur_s <= 0
        or hr_max_athlete is None
    ):
        return None

    if hr_avg_session <= 0 or hr_max_session <= 0 or hr_max_athlete <= 0:
        return None

    rest_hr = (
        hr_rest_athlete if hr_rest_athlete is not None and hr_rest_athlete > 0 else 66.0
    )

    lthr_guess = 0.90 * hr_max_athlete
    lthr_candidate = min(
        lthr_guess, max(0.85 * hr_max_athlete, 0.98 * hr_max_session)
    )
    if lthr_candidate <= rest_hr + 10:
        lthr = lthr_guess
    else:
        lthr = lthr_candidate

    hr_range = max(1.0, hr_max_athlete - rest_hr)
    thr_range = max(1.0, lthr - rest_hr)

    if hr_avg_session <= rest_hr + 5:
        if_est = 0.30
    else:
        if_base = (hr_avg_session - rest_hr) / thr_range
        supra = max(0.0, hr_max_session - lthr)
        supra_cap = max(1.0, hr_max_athlete - lthr)
        bump = 0.08 * (supra / supra_cap) if supra_cap else 0.0
        if_est = max(0.30, min(1.35, if_base + bump))

    if thr_range <= 1.0 and hr_range <= 1.0:
        if_est = 0.30

    tss = (dur_s / 3600.0) * if_est * 100.0
    return round(if_est, 2), round(tss, 1)
