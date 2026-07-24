"""Realized-vol term structure (Stage 4 item 1).

The three tenor estimates (24h/7d/30d) define a curve, not three independent
readings. sigma_for_horizon(T) is the single source of sigma for ALL pricing
(api.price_option/price_strategy call it, never pick a bar directly).

Interpolation is linear in VARIANCE-TIME (sigma^2 * T) — variance is what's
additive across time — converted back to sigma at the end. Outside the
observed [1d, 30d] range we clamp flat: extrapolating a realized curve is not
defensible, and the honest choice is to say so.

Shape (contango: long tenor above short; backwardation: reverse; flat when
endpoints are within 2 vol pts) is a first-class output — the agent mentions
it when it materially affects a quote.
"""
from __future__ import annotations

FLAT_THRESHOLD = 0.02  # endpoints within 2 vol pts -> flat

Point = tuple[float, float]  # (tenor_days, sigma_annual)


def make_curve_points(points: list[Point]) -> list[Point]:
    """Validate and normalize (tenor, sigma) points: ascending tenors, sigma>0."""
    if len(points) < 2:
        raise ValueError(f"curve needs >= 2 points, got {len(points)}")
    tenors = [t for t, _ in points]
    if tenors != sorted(tenors) or len(set(tenors)) != len(tenors):
        raise ValueError(f"tenors must be strictly ascending, got {tenors}")
    if any(t <= 0 or s <= 0 for t, s in points):
        raise ValueError(f"tenors and sigmas must be > 0, got {points}")
    return [(float(t), float(s)) for t, s in points]


def sigma_for_horizon(T_days: float, points: list[Point]) -> float:
    """Sigma for an arbitrary horizon from the fitted curve.

    Linear in variance-time between adjacent tenor points; flat clamp
    outside the observed range. Exactly reproduces sigma_i at T_i.
    """
    if T_days <= 0:
        raise ValueError(f"T_days must be > 0, got {T_days}")
    pts = make_curve_points(points)

    if T_days <= pts[0][0]:
        return pts[0][1]
    if T_days >= pts[-1][0]:
        return pts[-1][1]

    for (t0, s0), (t1, s1) in zip(pts, pts[1:]):
        if t0 <= T_days <= t1:
            v0, v1 = s0 * s0 * t0, s1 * s1 * t1
            w = (T_days - t0) / (t1 - t0)
            variance_time = v0 + w * (v1 - v0)
            return (variance_time / T_days) ** 0.5
    raise AssertionError("unreachable")  # pragma: no cover


def classify_shape(points: list[Point]) -> str:
    """contango | backwardation | flat, judged on the curve's endpoints."""
    pts = make_curve_points(points)
    spread = pts[-1][1] - pts[0][1]
    if abs(spread) < FLAT_THRESHOLD:
        return "flat"
    return "contango" if spread > 0 else "backwardation"
