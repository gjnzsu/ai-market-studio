from backend.agent.synthetic_specialist_data import (
    build_fx_carry_metrics,
    get_synthetic_forward_curve,
    get_synthetic_implied_volatility,
)


def test_synthetic_forward_curve_is_deterministic_for_supported_pair():
    first = get_synthetic_forward_curve("EUR/USD", spot_rate=1.08, as_of="2026-06-05")
    second = get_synthetic_forward_curve("EUR/USD", spot_rate=1.08, as_of="2026-06-05")

    assert first == second
    assert first["pair"] == "EUR/USD"
    assert first["source"] == "synthetic"
    assert first["as_of"] == "2026-06-05"
    assert first["tenors"] == [
        {"tenor": "1M", "forward_rate": 1.0792, "forward_points": -8.0},
        {"tenor": "3M", "forward_rate": 1.0772, "forward_points": -28.0},
        {"tenor": "6M", "forward_rate": 1.0738, "forward_points": -62.0},
    ]


def test_synthetic_implied_volatility_is_deterministic_for_supported_pair():
    first = get_synthetic_implied_volatility("EUR/USD", as_of="2026-06-05")
    second = get_synthetic_implied_volatility("EUR/USD", as_of="2026-06-05")

    assert first == second
    assert first["pair"] == "EUR/USD"
    assert first["source"] == "synthetic"
    assert first["as_of"] == "2026-06-05"
    assert first["tenors"] == [
        {"tenor": "1M", "atm_vol": 6.8},
        {"tenor": "3M", "atm_vol": 7.2},
        {"tenor": "6M", "atm_vol": 7.6},
    ]


def test_fx_carry_metrics_are_deterministic_and_research_oriented():
    forward_curve = get_synthetic_forward_curve(
        "EUR/USD", spot_rate=1.08, as_of="2026-06-05"
    )
    implied_volatility = get_synthetic_implied_volatility(
        "EUR/USD", as_of="2026-06-05"
    )
    metrics = build_fx_carry_metrics(
        pair="EUR/USD",
        spot_rate=1.08,
        fred_rates=[
            {"series_id": "DFF", "value": 3.62},
            {"series_id": "DGS10", "value": 4.47},
        ],
        forward_curve=forward_curve,
        implied_volatility=implied_volatility,
    )

    assert metrics == {
        "pair": "EUR/USD",
        "source": "synthetic",
        "rate_differential_proxy": 0.85,
        "forward_premium_discount": "synthetic forward discount",
        "six_month_forward_points": -62.0,
        "carry_to_vol": 0.12,
        "interpretation": "Research-only demo metric: positive but modest synthetic carry profile.",
    }
    text = str(metrics).lower()
    assert "research-only" in text
    assert "demo" in text
    assert "execute trade" not in text
    assert "place order" not in text
