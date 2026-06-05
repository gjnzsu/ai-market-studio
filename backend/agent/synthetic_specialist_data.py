from datetime import date
from typing import Any


SOURCE_SYNTHETIC = "synthetic"

_FORWARD_POINT_CURVES: dict[str, tuple[float, float, float]] = {
    "EUR/USD": (-8.0, -28.0, -62.0),
    "GBP/USD": (-5.0, -18.0, -40.0),
    "USD/JPY": (12.0, 42.0, 88.0),
    "USD/CHF": (7.0, 24.0, 50.0),
}

_ATM_VOL_CURVES: dict[str, tuple[float, float, float]] = {
    "EUR/USD": (6.8, 7.2, 7.6),
    "GBP/USD": (7.4, 7.9, 8.3),
    "USD/JPY": (8.6, 9.1, 9.7),
    "USD/CHF": (6.2, 6.6, 7.1),
}

_TENORS = ("1M", "3M", "6M")


def _normalize_pair(pair: str) -> str:
    return pair.upper().replace("-", "/")


def _as_of(as_of: str | None) -> str:
    return as_of or date.today().isoformat()


def _fallback_forward_points(pair: str) -> tuple[float, float, float]:
    seed = sum(ord(char) for char in pair)
    sign = -1.0 if seed % 2 == 0 else 1.0
    one_month = sign * float(4 + seed % 9)
    return (one_month, round(one_month * 3.2, 1), round(one_month * 7.1, 1))


def _fallback_atm_vols(pair: str) -> tuple[float, float, float]:
    seed = sum(ord(char) for char in pair)
    base = 5.8 + (seed % 16) / 10
    return (round(base, 1), round(base + 0.4, 1), round(base + 0.8, 1))


def get_synthetic_forward_curve(
    pair: str,
    spot_rate: float,
    as_of: str | None = None,
) -> dict[str, Any]:
    normalized_pair = _normalize_pair(pair)
    points = _FORWARD_POINT_CURVES.get(
        normalized_pair, _fallback_forward_points(normalized_pair)
    )
    tenors = [
        {
            "tenor": tenor,
            "forward_rate": round(spot_rate + forward_points / 10_000, 4),
            "forward_points": forward_points,
        }
        for tenor, forward_points in zip(_TENORS, points)
    ]
    return {
        "pair": normalized_pair,
        "source": SOURCE_SYNTHETIC,
        "as_of": _as_of(as_of),
        "tenors": tenors,
    }


def get_synthetic_implied_volatility(
    pair: str,
    as_of: str | None = None,
) -> dict[str, Any]:
    normalized_pair = _normalize_pair(pair)
    vols = _ATM_VOL_CURVES.get(normalized_pair, _fallback_atm_vols(normalized_pair))
    tenors = [
        {"tenor": tenor, "atm_vol": atm_vol}
        for tenor, atm_vol in zip(_TENORS, vols)
    ]
    return {
        "pair": normalized_pair,
        "source": SOURCE_SYNTHETIC,
        "as_of": _as_of(as_of),
        "tenors": tenors,
    }


def _rate_value(item: dict[str, Any]) -> float | None:
    value = item.get("value")
    if value is None:
        value = item.get("latest_value")
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _rate_differential_proxy(fred_rates: list[dict[str, Any]]) -> float:
    values = [
        value
        for value in (_rate_value(item) for item in fred_rates)
        if value is not None
    ]
    if len(values) >= 2:
        return round(values[-1] - values[0], 2)
    if len(values) == 1:
        return round(values[0], 2)
    return 0.0


def build_fx_carry_metrics(
    pair: str,
    spot_rate: float,
    fred_rates: list[dict[str, Any]],
    forward_curve: dict[str, Any],
    implied_volatility: dict[str, Any],
) -> dict[str, Any]:
    normalized_pair = _normalize_pair(pair)
    rate_differential = _rate_differential_proxy(fred_rates)
    six_month_points = float(forward_curve["tenors"][-1]["forward_points"])
    three_month_vol = float(implied_volatility["tenors"][1]["atm_vol"])
    carry_to_vol = round(abs(rate_differential) / three_month_vol, 2)
    premium_discount = (
        "synthetic forward premium"
        if six_month_points > 0
        else "synthetic forward discount"
        if six_month_points < 0
        else "synthetic forward flat"
    )
    profile = "positive but modest" if carry_to_vol < 0.25 else "elevated"

    return {
        "pair": normalized_pair,
        "source": SOURCE_SYNTHETIC,
        "rate_differential_proxy": rate_differential,
        "forward_premium_discount": premium_discount,
        "six_month_forward_points": six_month_points,
        "carry_to_vol": carry_to_vol,
        "interpretation": (
            f"Research-only demo metric: {profile} synthetic carry profile."
        ),
    }
