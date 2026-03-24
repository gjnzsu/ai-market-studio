from typing import Optional
from datetime import date as date_type

from .base import MarketDataConnector, RateFetchError, UnsupportedPairError

SOURCE_NAME = "mock"

DEFAULT_RATES: dict[str, float] = {
    "USDEUR": 0.9201,
    "USDGBP": 0.7856,
    "USDJPY": 149.82,
    "USDAUD": 1.5234,
    "USDCAD": 1.3612,
    "USDCHF": 0.8923,
    "USDCNY": 7.2341,
    "USDHKD": 7.8201,
    "USDSGD": 1.3421,
    "USDNZD": 1.6234,
}

SUPPORTED_CURRENCIES = ["USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "CNY", "HKD", "SGD", "NZD"]


class MockConnector(MarketDataConnector):
    """Deterministic mock connector for testing.

    Args:
        overrides: Optional dict of pair keys (e.g. 'USDEUR') to override rates.
        error_pairs: Set of pair strings (e.g. {'EUR/USD'}) that raise RateFetchError.
        unsupported_pairs: Set of pair strings that raise UnsupportedPairError.
    """

    def __init__(
        self,
        overrides: Optional[dict[str, float]] = None,
        error_pairs: Optional[set[str]] = None,
        unsupported_pairs: Optional[set[str]] = None,
    ) -> None:
        self._rates = {**DEFAULT_RATES, **(overrides or {})}
        self._error_pairs: set[str] = {p.upper().replace("/", "") for p in (error_pairs or set())}
        self._unsupported_pairs: set[str] = {p.upper().replace("/", "") for p in (unsupported_pairs or set())}

    def _today(self) -> str:
        return date_type.today().isoformat()

    def _get_rate(self, base: str, target: str) -> float:
        """Look up rate via USD triangulation if needed."""
        if base == target:
            return 1.0
        pair_key = f"{base}{target}"
        if pair_key in self._error_pairs:
            raise RateFetchError(f"Simulated error for {base}/{target}")
        if pair_key in self._unsupported_pairs:
            raise UnsupportedPairError(f"{base}/{target} is not supported (mock)")
        # Direct lookup
        direct_key = f"USD{target}" if base == "USD" else None
        if direct_key and direct_key in self._rates:
            if base == "USD":
                return self._rates[direct_key]
        # Triangulate via USD
        usd_base_key = f"USD{base}"
        usd_target_key = f"USD{target}"
        if usd_base_key not in self._rates and base != "USD":
            raise UnsupportedPairError(f"{base} not in mock rates")
        if usd_target_key not in self._rates and target != "USD":
            raise UnsupportedPairError(f"{target} not in mock rates")
        usd_base = self._rates.get(usd_base_key, 1.0) if base != "USD" else 1.0
        usd_target = self._rates.get(usd_target_key, 1.0) if target != "USD" else 1.0
        return round(usd_target / usd_base, 6)

    async def get_exchange_rate(
        self,
        base: str,
        target: str,
        date: Optional[str] = None,
    ) -> dict:
        base = base.upper()
        target = target.upper()
        rate = self._get_rate(base, target)
        return {
            "base": base,
            "target": target,
            "rate": rate,
            "date": date or self._today(),
            "source": SOURCE_NAME,
        }

    async def get_exchange_rates(
        self,
        base: str,
        targets: list[str],
        date: Optional[str] = None,
    ) -> list[dict]:
        return [await self.get_exchange_rate(base, t, date) for t in targets]

    async def list_supported_currencies(self) -> list[str]:
        return SUPPORTED_CURRENCIES
