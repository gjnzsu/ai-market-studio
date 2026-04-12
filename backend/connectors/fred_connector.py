"""FRED (Federal Reserve Economic Data) connector for interest rate queries.

Provides async methods to fetch current and historical interest rates from the
Federal Reserve's public API. Used by the FX market analysis agent to get
interest rate context for currency pair analysis.
"""

import logging
from typing import Optional
import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

FRED_API_KEY = "49902bd505135a5970742c278a2584a7"
FRED_BASE_URL = "https://api.stlouisfed.org/fred"

COMMON_SERIES = {
    "DFF": "Effective Federal Funds Rate (daily)",
    "FEDFUNDS": "Effective Federal Funds Rate (monthly)",
    "T10Y2Y": "10-Year minus 2-Year Treasury Spread",
    "T10Y3M": "10-Year minus 3-Month Treasury Spread",
    "DGS10": "10-Year Treasury Constant Maturity Rate",
    "DGS2": "2-Year Treasury Constant Maturity Rate",
    "DGS5": "5-Year Treasury Constant Maturity Rate",
    "DTB3": "3-Month Treasury Bill Rate",
    "MORTGAGE30US": "30-Year Fixed Rate Mortgage Average"
}


class InterestRateData(BaseModel):
    """Interest rate observation from FRED."""
    series_id: str = Field(description="FRED series ID")
    series_name: str = Field(description="Human-readable series name")
    date: str = Field(description="Date (YYYY-MM-DD)")
    value: float = Field(description="Interest rate value in percent")
    unit: str = Field(default="percent", description="Unit of measurement")
    source: str = Field(default="FRED", description="Data source")


class HistoricalObservation(BaseModel):
    """Single historical observation."""
    date: str = Field(description="Date (YYYY-MM-DD)")
    value: float = Field(description="Interest rate value in percent")


class HistoricalRatesData(BaseModel):
    """Historical interest rate data for a date range."""
    series_id: str
    series_name: str
    start_date: str
    end_date: str
    observations: list[HistoricalObservation]
    count: int = Field(description="Number of observations")
    source: str = Field(default="FRED")


class FREDConnectorError(Exception):
    """Base exception for FRED connector errors."""


class FREDConnector:
    """Async connector for FRED interest rate API.

    Fetches current and historical interest rates for various economic indicators
    including federal funds rate, treasury spreads, and mortgage rates.
    """

    def __init__(self, api_key: str = FRED_API_KEY, timeout: float = 10.0):
        self.api_key = api_key
        self.timeout = timeout
        self.base_url = FRED_BASE_URL

    async def get_current_rate(
        self,
        series_id: str,
        date: Optional[str] = None,
    ) -> InterestRateData:
        """Get current or specific date interest rate.

        Args:
            series_id: FRED series ID (e.g., DFF, T10Y2Y, DGS10)
            date: Optional specific date (YYYY-MM-DD). If None, returns latest.

        Returns:
            InterestRateData with rate value and metadata.

        Raises:
            FREDConnectorError: On network error, API error, or data unavailable.
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                params = {
                    "series_id": series_id,
                    "api_key": self.api_key,
                    "file_type": "json"
                }
                if date:
                    params["start_date"] = date
                    params["end_date"] = date

                response = await client.get(
                    f"{self.base_url}/series/observations",
                    params=params
                )
                response.raise_for_status()
                data = response.json()

                # Find latest observation with valid value
                observations = data.get("observations", [])
                if not observations:
                    raise FREDConnectorError(f"No data available for series {series_id}")

                # Filter out missing values (marked with ".")
                valid_obs = [o for o in observations if o["value"] != "."]
                if not valid_obs:
                    raise FREDConnectorError(f"No valid values for series {series_id}")

                latest = valid_obs[-1]
                return InterestRateData(
                    series_id=series_id,
                    series_name=COMMON_SERIES.get(series_id, series_id),
                    date=latest["date"],
                    value=float(latest["value"]),
                    unit="percent",
                    source="FRED (Federal Reserve Economic Data)"
                )

        except httpx.TimeoutException as e:
            logger.error(f"FRED API timeout for {series_id}: {e}")
            raise FREDConnectorError(f"Timeout fetching {series_id}") from e
        except httpx.HTTPError as e:
            logger.error(f"FRED API error for {series_id}: {e}")
            raise FREDConnectorError(f"HTTP error fetching {series_id}") from e
        except Exception as e:
            logger.error(f"Unexpected error fetching {series_id}: {e}")
            raise FREDConnectorError(f"Error fetching {series_id}: {str(e)}") from e

    async def get_historical_rates(
        self,
        series_id: str,
        start_date: str,
        end_date: str,
    ) -> HistoricalRatesData:
        """Get historical interest rate data for a date range.

        Args:
            series_id: FRED series ID
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            HistoricalRatesData with list of observations.

        Raises:
            FREDConnectorError: On network error, API error, or data unavailable.
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                params = {
                    "series_id": series_id,
                    "start_date": start_date,
                    "end_date": end_date,
                    "api_key": self.api_key,
                    "file_type": "json"
                }
                response = await client.get(
                    f"{self.base_url}/series/observations",
                    params=params
                )
                response.raise_for_status()
                data = response.json()

                # Filter out missing values
                observations = [
                    HistoricalObservation(
                        date=obs["date"],
                        value=float(obs["value"])
                    )
                    for obs in data.get("observations", [])
                    if obs["value"] != "."
                ]

                if not observations:
                    raise FREDConnectorError(
                        f"No data available for {series_id} between {start_date} and {end_date}"
                    )

                return HistoricalRatesData(
                    series_id=series_id,
                    series_name=COMMON_SERIES.get(series_id, series_id),
                    start_date=start_date,
                    end_date=end_date,
                    observations=observations,
                    count=len(observations),
                    source="FRED"
                )

        except httpx.TimeoutException as e:
            logger.error(f"FRED API timeout for {series_id}: {e}")
            raise FREDConnectorError(f"Timeout fetching {series_id}") from e
        except httpx.HTTPError as e:
            logger.error(f"FRED API error for {series_id}: {e}")
            raise FREDConnectorError(f"HTTP error fetching {series_id}") from e
        except Exception as e:
            logger.error(f"Unexpected error fetching historical rates: {e}")
            raise FREDConnectorError(f"Error fetching {series_id}: {str(e)}") from e

    async def list_fred_series(self) -> dict[str, str]:
        """List commonly used FRED interest rate series.

        Returns:
            Dictionary mapping series ID to description.
        """
        return COMMON_SERIES
