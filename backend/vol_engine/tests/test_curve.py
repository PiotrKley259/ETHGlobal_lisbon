"""Stage 4 item 1 tests — written before curve.py. The four spec-mandated
assertions (docs/options_desk_summary.md §4) plus shape classification:

1. sigma_for_horizon reproduces the input sigma EXACTLY at each tenor point.
2. Monotonic interpolation between adjacent points.
3. Flat clamping outside [1d, 30d].
4. Variance-time interpolation differs from naive sigma-interpolation on a
   non-flat curve (guards against someone silently simplifying it).
"""
import math

import pytest

from vol_engine.curve import classify_shape, make_curve_points, sigma_for_horizon

RISING = [(1.0, 0.333), (7.0, 0.366), (30.0, 0.526)]   # today's actual shape
FALLING = [(1.0, 0.71), (7.0, 0.62), (30.0, 0.55)]
FLAT = [(1.0, 0.50), (7.0, 0.51), (30.0, 0.50)]


# 1 — exact reproduction at the tenor points
@pytest.mark.parametrize("points", [RISING, FALLING, FLAT])
def test_reproduces_inputs_exactly_at_tenors(points):
    for tenor, sigma in points:
        assert sigma_for_horizon(tenor, points) == pytest.approx(sigma, abs=1e-12)


# 2 — monotone between adjacent points
@pytest.mark.parametrize("points", [RISING, FALLING])
def test_monotonic_between_adjacent_points(points):
    direction = 1 if points[-1][1] > points[0][1] else -1
    for (t0, _), (t1, _) in zip(points, points[1:]):
        grid = [t0 + i * (t1 - t0) / 50 for i in range(51)]
        sigmas = [sigma_for_horizon(t, points) for t in grid]
        diffs = [direction * (b - a) for a, b in zip(sigmas, sigmas[1:])]
        assert all(d >= -1e-12 for d in diffs)


# 3 — flat clamp outside the observed range
def test_flat_clamp_outside_range():
    for points in (RISING, FALLING):
        assert sigma_for_horizon(0.25, points) == points[0][1]
        assert sigma_for_horizon(1.0, points) == points[0][1]
        assert sigma_for_horizon(45.0, points) == points[-1][1]
        assert sigma_for_horizon(365.0, points) == points[-1][1]


# 4 — variance-time is NOT naive sigma-linear interpolation
def test_variance_time_differs_from_naive_sigma_interp():
    t = 4.0  # midpoint-ish of the 1d..7d segment
    for points in (RISING, FALLING):
        (t0, s0), (t1, s1) = points[0], points[1]
        naive = s0 + (s1 - s0) * (t - t0) / (t1 - t0)
        vt = sigma_for_horizon(t, points)
        assert abs(vt - naive) > 1e-4  # materially different on a non-flat curve
    # ...but identical when the curve is exactly flat
    truly_flat = [(1.0, 0.5), (7.0, 0.5), (30.0, 0.5)]
    assert sigma_for_horizon(4.0, truly_flat) == pytest.approx(0.5, abs=1e-12)


def test_interpolation_is_linear_in_variance_time():
    # direct check of the invariant: sigma^2*T is linear between tenors
    points = RISING
    (t0, s0), (t1, s1) = points[0], points[1]
    for w in (0.25, 0.5, 0.75):
        t = t0 + w * (t1 - t0)
        v = sigma_for_horizon(t, points) ** 2 * t
        expected = (s0**2 * t0) + w * (s1**2 * t1 - s0**2 * t0)
        assert v == pytest.approx(expected, rel=1e-12)


def test_shape_classification():
    assert classify_shape(RISING) == "contango"       # long above short
    assert classify_shape(FALLING) == "backwardation"  # short above long
    assert classify_shape(FLAT) == "flat"              # endpoints within 2 pts
    assert classify_shape([(1, 0.50), (7, 0.55), (30, 0.519)]) == "flat"


def test_make_curve_points_requires_valid_inputs():
    with pytest.raises(ValueError):
        sigma_for_horizon(7.0, [(1.0, 0.5)])  # need >= 2 points
    with pytest.raises(ValueError):
        sigma_for_horizon(-1.0, RISING)
    with pytest.raises(ValueError):
        make_curve_points([(7.0, 0.5), (1.0, 0.6)])  # tenors must ascend
    with pytest.raises(ValueError):
        make_curve_points([(1.0, 0.5), (7.0, -0.1)])  # sigma must be > 0
