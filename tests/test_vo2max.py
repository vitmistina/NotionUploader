from typing import Dict, Any
from src.domain.body_metrics.vo2 import vo2max_minutes


def make_split(
    moving_time: float,
    avg_hr: float,
    max_hr: float
) -> Dict[str, Any]:
    """Helper to create a split dictionary."""
    return {
        "moving_time": moving_time,
        "average_heartrate": avg_hr,
        "max_heartrate": max_hr,
    }


def test_vo2max_empty_splits():
    """Test with empty splits list."""
    assert vo2max_minutes([], 180.0) == 0.0


def test_vo2max_no_max_hr():
    """Test with None max_hr."""
    splits = [make_split(60, 170, 180)]
    assert vo2max_minutes(splits, None) == 0.0


def test_vo2max_invalid_max_hr():
    """Test with invalid (negative or zero) max_hr."""
    splits = [make_split(60, 170, 180)]
    assert vo2max_minutes(splits, 0.0) == 0.0
    assert vo2max_minutes(splits, -180.0) == 0.0


def test_vo2max_single_split_sustained():
    """Test with a single split that has high sustained HR."""
    max_hr = 190
    splits = [make_split(120, 175, 180)]  # 92% avg HR, 95% max HR
    # Should register significant VO2max time due to high average HR
    result = vo2max_minutes(splits, max_hr)
    assert 1.0 < result < 2.0  # Expect ~1-2 minutes of the 2-minute split


def test_vo2max_single_split_peak_only():
    """Test with a single split that has low average but high peak HR."""
    max_hr = 190
    splits = [make_split(30, 160, 180)]  # 84% avg HR, 95% max HR
    # Should register some but limited VO2max time due to HR lag on short effort
    result = vo2max_minutes(splits, max_hr)
    assert 0 < result < 0.3  # Some credit but less than 0.3 minutes


def test_vo2max_multiple_splits():
    """Test with multiple splits with varying intensities."""
    max_hr = 190
    splits = [
        make_split(120, 175, 180),  # High intensity
        make_split(120, 140, 145),  # Recovery
        make_split(120, 172, 178),  # High intensity
    ]
    result = vo2max_minutes(splits, max_hr)
    # Should register significant time from the two high-intensity splits
    # Expect ~2-3 minutes total from the two high-intensity splits
    assert 2.0 < result < 3.0


def test_vo2max_threshold_adjustment():
    """Test effect of adjusting the VO2max threshold."""
    max_hr = 190
    splits = [make_split(120, 170, 175)]  # ~89.5% avg HR

    # With higher threshold (0.90), should register less time
    result_higher = vo2max_minutes(splits, max_hr, vo2_threshold_fraction_of_hrmax=0.90)
    
    # With lower threshold (0.85), should register more time
    result_lower = vo2max_minutes(splits, max_hr, vo2_threshold_fraction_of_hrmax=0.85)
    
    assert result_lower > result_higher


def test_vo2max_kinetics_effect():
    """Test effect of HR kinetics on short vs long efforts."""
    max_hr = 190
    short_split = [make_split(30, 170, 180)]  # Short effort
    long_split = [make_split(120, 170, 180)]  # Long effort
    
    # Short effort should get less credit per second than long effort
    short_result = vo2max_minutes(short_split, max_hr)
    long_result = vo2max_minutes(long_split, max_hr)
    
    assert (short_result / 0.5) < (long_result / 2.0)


def test_vo2max_peak_influence():
    """Test effect of peak_influence_cap parameter."""
    max_hr = 190
    splits = [make_split(60, 160, 180)]  # Low avg, high peak

    # With no peak influence (0.0)
    result_no_peak = vo2max_minutes(splits, max_hr, peak_influence_cap=0.0)
    
    # With maximum peak influence (1.0)
    result_max_peak = vo2max_minutes(splits, max_hr, peak_influence_cap=1.0)
    
    assert result_no_peak < result_max_peak
    assert result_max_peak > 0  # Should get some credit with max peak influence


def test_vo2max_invalid_splits():
    """Test handling of splits with invalid data."""
    max_hr = 190
    splits = [
        make_split(0, 170, 180),  # Zero duration
        make_split(-60, 170, 180),  # Negative duration
        make_split(60, 0, 180),  # Zero average HR
        make_split(60, 170, 0),  # Zero max HR
        make_split(60, -170, 180),  # Negative average HR
        make_split(60, 170, -180),  # Negative max HR
    ]
    # Should handle invalid data gracefully
    result = vo2max_minutes(splits, max_hr)
    assert result == 0.0


def test_vo2max_missing_heart_rate_data():
    """Splits without heart-rate data should produce zero VO2 time."""
    max_hr = 190
    splits = [
        {"moving_time": 60, "average_heartrate": None, "max_heartrate": 180},
        {"moving_time": 60, "average_heartrate": 175, "max_heartrate": None},
    ]

    result = vo2max_minutes(splits, max_hr)

    assert result == 0.0
