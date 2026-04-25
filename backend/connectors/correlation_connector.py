"""Correlation connector for analyzing FX movements against economic indicators.

Orchestrates data fetching from MarketDataConnector and FREDConnector to compute
directional alignment between FX rate changes and economic indicator changes.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
from statistics import mean

from backend.connectors.base import ConnectorError, MarketDataConnector
from backend.connectors.fred_connector import FREDConnector, FREDConnectorError

logger = logging.getLogger(__name__)


class CorrelationConnector:
    """Analyzes correlation between FX movements and economic indicators.

    Uses existing MarketDataConnector for FX rates and FREDConnector for
    economic indicators. Calculates directional alignment (percentage of days
    where both series moved in the same direction) and generates narrative
    trend summaries.
    """

    def __init__(
        self,
        market_connector: MarketDataConnector,
        fred_connector: Optional[FREDConnector] = None,
    ):
        """Initialize correlation connector.

        Args:
            market_connector: Connector for FX rate data
            fred_connector: Connector for FRED economic data (creates new if None)
        """
        self.market_connector = market_connector
        self.fred_connector = fred_connector or FREDConnector()

    async def analyze_correlation(
        self,
        pair: str,
        indicators: list[str],
        days: int = 90,
    ) -> dict:
        """Analyze correlation between FX pair and economic indicators.

        Args:
            pair: Currency pair in format "BASE/TARGET" (e.g., "EUR/USD")
            indicators: List of FRED series IDs (e.g., ["DFF", "DGS10"])
            days: Lookback period in days (default: 90, min: 30, max: 365)

        Returns:
            Dictionary with correlation analysis results:
            {
                "pair": "EUR/USD",
                "indicators": [{"series_id": "DFF", "name": "...", ...}],
                "period": {"start_date": "...", "end_date": "...", "days": 90},
                "fx_summary": {"start_rate": 1.08, "end_rate": 1.05, "change_pct": -2.78},
                "directional_alignment": 78.5,
                "trend_summary": "..."
            }

        Raises:
            ConnectorError: If insufficient data or API failures
        """
        # Validate inputs
        if days < 30:
            raise ConnectorError("Minimum lookback period is 30 days")
        if days > 365:
            raise ConnectorError("Maximum lookback period is 365 days")
        if not indicators:
            raise ConnectorError("At least one indicator is required")

        # Parse currency pair
        try:
            base, target = pair.split("/")
        except ValueError:
            raise ConnectorError(f"Invalid pair format: {pair}. Expected 'BASE/TARGET'")

        # Calculate date range
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)

        # Fetch FX historical data
        fx_data = await self._fetch_fx_series(
            base=base,
            target=target,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
        )

        # Fetch indicator data for all indicators
        indicator_results = []
        for series_id in indicators:
            try:
                indicator_data = await self._fetch_indicator_series(
                    series_id=series_id,
                    start_date=start_date.isoformat(),
                    end_date=end_date.isoformat(),
                )
                indicator_results.append(indicator_data)
            except FREDConnectorError as e:
                logger.warning(f"Failed to fetch indicator {series_id}: {e}")
                # Continue with other indicators

        if not indicator_results:
            raise ConnectorError("Failed to fetch any indicator data")

        # Calculate directional alignment for each indicator
        alignments = []
        for indicator_data in indicator_results:
            alignment = self._calculate_directional_alignment(
                fx_data=fx_data,
                indicator_data=indicator_data,
            )
            alignments.append(alignment)

        # Calculate average alignment across all indicators
        avg_alignment = mean([a["alignment_pct"] for a in alignments])

        # Generate trend summary
        trend_summary = self._generate_trend_summary(
            pair=pair,
            fx_data=fx_data,
            indicator_results=indicator_results,
            alignments=alignments,
        )

        # Build response
        return {
            "pair": pair,
            "indicators": [
                {
                    "series_id": ind["series_id"],
                    "name": ind["series_name"],
                    "start_value": ind["observations"][0]["value"],
                    "end_value": ind["observations"][-1]["value"],
                    "change": ind["observations"][-1]["value"] - ind["observations"][0]["value"],
                    "alignment_pct": align["alignment_pct"],
                }
                for ind, align in zip(indicator_results, alignments)
            ],
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "days": days,
            },
            "fx_summary": {
                "start_rate": fx_data["rates"][0]["rate"],
                "end_rate": fx_data["rates"][-1]["rate"],
                "change_pct": (
                    (fx_data["rates"][-1]["rate"] - fx_data["rates"][0]["rate"])
                    / fx_data["rates"][0]["rate"]
                    * 100
                ),
            },
            "directional_alignment": round(avg_alignment, 2),
            "trend_summary": trend_summary,
        }

    async def _fetch_fx_series(
        self,
        base: str,
        target: str,
        start_date: str,
        end_date: str,
    ) -> dict:
        """Fetch FX historical rates and normalize to list format.

        Returns:
            {
                "base": "EUR",
                "target": "USD",
                "rates": [{"date": "2024-01-25", "rate": 1.08}, ...]
            }
        """
        try:
            raw_data = await self.market_connector.get_historical_rates(
                base=base,
                targets=[target],
                start_date=start_date,
                end_date=end_date,
            )

            # Convert dict format to list format
            rates = [
                {"date": date, "rate": rates_dict[target]}
                for date, rates_dict in sorted(raw_data.items())
            ]

            if len(rates) < 30:
                raise ConnectorError(
                    f"Insufficient FX data: got {len(rates)} days, need at least 30"
                )

            return {
                "base": base,
                "target": target,
                "rates": rates,
            }

        except Exception as e:
            logger.error(f"Failed to fetch FX data for {base}/{target}: {e}")
            raise ConnectorError(f"Failed to fetch FX data: {str(e)}") from e

    async def _fetch_indicator_series(
        self,
        series_id: str,
        start_date: str,
        end_date: str,
    ) -> dict:
        """Fetch FRED indicator historical data.

        Returns:
            {
                "series_id": "DFF",
                "series_name": "Effective Federal Funds Rate",
                "observations": [{"date": "2024-01-25", "value": 5.33}, ...]
            }
        """
        try:
            data = await self.fred_connector.get_historical_rates(
                series_id=series_id,
                start_date=start_date,
                end_date=end_date,
            )

            if len(data.observations) < 30:
                raise FREDConnectorError(
                    f"Insufficient indicator data: got {len(data.observations)} observations"
                )

            return {
                "series_id": data.series_id,
                "series_name": data.series_name,
                "observations": [
                    {"date": obs.date, "value": obs.value}
                    for obs in data.observations
                ],
            }

        except FREDConnectorError as e:
            logger.error(f"Failed to fetch FRED data for {series_id}: {e}")
            raise

    def _calculate_directional_alignment(
        self,
        fx_data: dict,
        indicator_data: dict,
    ) -> dict:
        """Calculate directional alignment between FX and indicator changes.

        Directional alignment = percentage of days where both series moved
        in the same direction (both up or both down).

        Returns:
            {
                "alignment_pct": 78.5,
                "same_direction_days": 71,
                "total_days": 90,
            }
        """
        # Build date-indexed dictionaries
        fx_by_date = {r["date"]: r["rate"] for r in fx_data["rates"]}
        ind_by_date = {o["date"]: o["value"] for o in indicator_data["observations"]}

        # Find common dates
        common_dates = sorted(set(fx_by_date.keys()) & set(ind_by_date.keys()))

        if len(common_dates) < 2:
            return {
                "alignment_pct": 0.0,
                "same_direction_days": 0,
                "total_days": 0,
            }

        # Calculate day-over-day changes
        same_direction_count = 0
        total_comparisons = 0

        for i in range(1, len(common_dates)):
            prev_date = common_dates[i - 1]
            curr_date = common_dates[i]

            fx_change = fx_by_date[curr_date] - fx_by_date[prev_date]
            ind_change = ind_by_date[curr_date] - ind_by_date[prev_date]

            # Check if both moved in same direction (both positive or both negative)
            # Ignore days where either series didn't change
            if fx_change != 0 and ind_change != 0:
                if (fx_change > 0 and ind_change > 0) or (fx_change < 0 and ind_change < 0):
                    same_direction_count += 1
                total_comparisons += 1

        alignment_pct = (
            (same_direction_count / total_comparisons * 100)
            if total_comparisons > 0
            else 0.0
        )

        return {
            "alignment_pct": alignment_pct,
            "same_direction_days": same_direction_count,
            "total_days": total_comparisons,
        }

    def _generate_trend_summary(
        self,
        pair: str,
        fx_data: dict,
        indicator_results: list[dict],
        alignments: list[dict],
    ) -> str:
        """Generate narrative summary of correlation trends.

        Returns:
            Human-readable summary string describing the correlation.
        """
        # FX trend
        start_rate = fx_data["rates"][0]["rate"]
        end_rate = fx_data["rates"][-1]["rate"]
        fx_change_pct = (end_rate - start_rate) / start_rate * 100
        fx_direction = "increased" if fx_change_pct > 0 else "declined"

        # Build summary for each indicator
        summaries = []
        for ind, align in zip(indicator_results, alignments):
            start_val = ind["observations"][0]["value"]
            end_val = ind["observations"][-1]["value"]
            ind_change = end_val - start_val
            ind_direction = "rose" if ind_change > 0 else "fell"

            alignment_strength = (
                "strong" if align["alignment_pct"] > 70
                else "moderate" if align["alignment_pct"] > 50
                else "weak"
            )

            summaries.append(
                f"{ind['series_name']} {ind_direction} from {start_val:.2f}% to {end_val:.2f}% "
                f"({ind_change:+.2f} bps), showing {alignment_strength} "
                f"{align['alignment_pct']:.1f}% directional alignment"
            )

        # Combine into final summary
        summary = (
            f"{pair} {fx_direction} {abs(fx_change_pct):.2f}% "
            f"(from {start_rate:.4f} to {end_rate:.4f}). "
        )
        summary += " ".join(summaries) + "."

        return summary
