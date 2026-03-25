from abc import ABC, abstractmethod
from typing import Optional


class ConnectorError(Exception):
    """Base exception for all connector-layer errors."""


class RateFetchError(ConnectorError):
    """Raised when a rate cannot be fetched (HTTP error, timeout, parse failure)."""


class UnsupportedPairError(ConnectorError):
    """Raised when the requested currency pair is not supported by the source."""


class StaleDataError(ConnectorError):
    """Raised when the returned data is older than the acceptable threshold."""


class MarketDataConnector(ABC):
    """Abstract interface for FX market data sources.

    All implementations must be async. Methods return data normalised
    to the canonical FX rate dict. The agent layer depends only on this
    interface, never on a concrete implementation.
    """

    @abstractmethod
    async def get_exchange_rate(
        self,
        base: str,
        target: str,
        date: Optional[str] = None,
    ) -> dict:
        """Fetch the exchange rate for a currency pair.

        Args:
            base: Base currency code (e.g. "USD").
            target: Target currency code (e.g. "EUR").
            date: Optional date string (YYYY-MM-DD) for historical rates.
                  If None, returns the latest available rate.

        Returns:
            dict with keys:
                base (str), target (str), rate (float),
                date (str, YYYY-MM-DD), source (str)

        Raises:
            RateFetchError: On HTTP errors, timeouts, or parse failures.
            UnsupportedPairError: If the pair is not available.
        """

    @abstractmethod
    async def get_exchange_rates(
        self,
        base: str,
        targets: list[str],
        date: Optional[str] = None,
    ) -> list[dict]:
        """Fetch exchange rates for multiple target currencies.

        Args:
            base: Base currency code.
            targets: List of target currency codes.
            date: Optional date string (YYYY-MM-DD).

        Returns:
            List of rate dicts (same schema as get_exchange_rate).

        Raises:
            RateFetchError: On HTTP errors, timeouts, or parse failures.
        """

    @abstractmethod
    async def list_supported_currencies(self) -> list[str]:
        """Return a list of supported ISO 4217 currency codes."""

    @abstractmethod
    async def get_historical_rates(
        self,
        base: str,
        targets: list[str],
        start_date: str,
        end_date: str,
    ) -> dict[str, dict[str, float]]:
        """
        Return daily closing rates for each target currency.

        Returns:
            {
                "2025-01-01": {"EUR": 0.92, "GBP": 0.79},
                "2025-01-02": {"EUR": 0.921, "GBP": 0.791},
                ...
            }
        Raises:
            RateFetchError: on network / API failure.
            UnsupportedPairError: if base or any target is unsupported.
        """
