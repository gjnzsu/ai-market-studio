import httpx
from typing import Optional
from datetime import date as date_type

from .base import MarketDataConnector, RateFetchError, UnsupportedPairError

BASE_URL = "https://api.exchangerate.host"
SOURCE_NAME = "exchangerate.host"

# Free tier locks base currency to USD.
# For non-USD base pairs we triangulate: base→USD→target.
FREE_TIER_BASE = "USD"


class ExchangeRateHostConnector(MarketDataConnector):
    """Connector for the exchangerate.host free API.

    Free tier notes:
    - Requires EXCHANGERATE_API_KEY.
    - Base currency is locked to USD on the free tier.
    - Non-USD base pairs are computed via USD triangulation.
    - Quota: ~100 requests/month. Use MockConnector in tests.
    """

    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise RateFetchError("EXCHANGERATE_API_KEY is not set.")
        self._api_key = api_key
        self._client = httpx.AsyncClient(timeout=10.0)

    async def _fetch_usd_rates(self, currencies: list[str], date: Optional[str]) -> dict:
        """Fetch rates with USD as base from exchangerate.host."""
        params: dict = {
            "access_key": self._api_key,
            "currencies": ",".join(currencies),
            "source": FREE_TIER_BASE,
        }
        endpoint = "/historical" if date else "/live"
        if date:
            params["date"] = date
        try:
            resp = await self._client.get(f"{BASE_URL}{endpoint}", params=params)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise RateFetchError(f"HTTP {e.response.status_code} from exchangerate.host") from e
        except httpx.RequestError as e:
            raise RateFetchError(f"Network error: {e}") from e

        data = resp.json()
        if not data.get("success"):
            raise RateFetchError(f"API error: {data.get('error', {}).get('info', 'unknown')}")
        return data.get("quotes", {})

    def _today(self) -> str:
        return date_type.today().isoformat()

    async def get_exchange_rate(
        self,
        base: str,
        target: str,
        date: Optional[str] = None,
    ) -> dict:
        base = base.upper()
        target = target.upper()
        rate_date = date or self._today()

        if base == FREE_TIER_BASE:
            quotes = await self._fetch_usd_rates([target], date)
            key = f"{FREE_TIER_BASE}{target}"
            if key not in quotes:
                raise UnsupportedPairError(f"{base}/{target} not available.")
            return {"base": base, "target": target, "rate": quotes[key], "date": rate_date, "source": SOURCE_NAME}

        # Triangulate: base→USD and USD→target
        quotes = await self._fetch_usd_rates([base, target], date)
        usd_base_key = f"{FREE_TIER_BASE}{base}"
        usd_target_key = f"{FREE_TIER_BASE}{target}"
        if usd_base_key not in quotes:
            raise UnsupportedPairError(f"{base} not available via triangulation.")
        if usd_target_key not in quotes:
            raise UnsupportedPairError(f"{target} not available via triangulation.")
        rate = quotes[usd_target_key] / quotes[usd_base_key]
        return {"base": base, "target": target, "rate": round(rate, 6), "date": rate_date, "source": SOURCE_NAME}

    async def get_exchange_rates(
        self,
        base: str,
        targets: list[str],
        date: Optional[str] = None,
    ) -> list[dict]:
        # Fetch all needed currencies in a single API call to avoid rate limiting.
        # For non-USD base we also need the base currency for triangulation.
        currencies_needed = list(set(targets) | ({base} if base != FREE_TIER_BASE else set()))
        quotes = await self._fetch_usd_rates(currencies_needed, date)
        rate_date = date or self._today()

        results = []
        for target in targets:
            if base == target:
                results.append({"base": base, "target": target, "rate": 1.0, "date": rate_date, "source": SOURCE_NAME})
                continue
            if base == FREE_TIER_BASE:
                key = f"{FREE_TIER_BASE}{target}"
                if key not in quotes:
                    raise UnsupportedPairError(f"{target} not available.")
                results.append({"base": base, "target": target, "rate": round(quotes[key], 6), "date": rate_date, "source": SOURCE_NAME})
            else:
                usd_base_key = f"{FREE_TIER_BASE}{base}"
                usd_target_key = f"{FREE_TIER_BASE}{target}"
                if usd_base_key not in quotes:
                    raise UnsupportedPairError(f"{base} not available via triangulation.")
                if usd_target_key not in quotes:
                    raise UnsupportedPairError(f"{target} not available via triangulation.")
                rate = quotes[usd_target_key] / quotes[usd_base_key]
                results.append({"base": base, "target": target, "rate": round(rate, 6), "date": rate_date, "source": SOURCE_NAME})
        return results

    async def get_historical_rates(
        self,
        base: str,
        targets: list[str],
        start_date: str,
        end_date: str,
    ) -> dict[str, dict[str, float]]:
        """
        Fetch daily closing rates via sequential /historical calls.

        IMPORTANT: /timeseries is not available on the free tier.
        Makes one API call per day in [start_date, end_date].
        Caller must enforce max 7 days to stay within 100 req/month.
        """
        from datetime import date as _date, timedelta
        base = base.upper()
        symbols = ",".join(t.upper() for t in targets)
        start = _date.fromisoformat(start_date)
        end = _date.fromisoformat(end_date)
        result: dict[str, dict[str, float]] = {}
        current = start
        while current <= end:
            params = {
                "access_key": self._api_key,
                "base": base,
                "symbols": symbols,
                "date": current.isoformat(),
            }
            try:
                resp = await self._client.get(f"{BASE_URL}/historical", params=params)
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise RateFetchError(f"HTTP {e.response.status_code} from exchangerate.host historical") from e
            except httpx.RequestError as e:
                raise RateFetchError(f"Network error: {e}") from e
            body = resp.json()
            if not body.get("success") or "rates" not in body:
                raise RateFetchError(f"historical API error for {current}: {body.get('error')}")
            result[current.isoformat()] = body["rates"]
            current += timedelta(days=1)
        return result

    async def list_supported_currencies(self) -> list[str]:
        try:
            resp = await self._client.get(
                f"{BASE_URL}/list",
                params={"access_key": self._api_key},
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get("success"):
                raise RateFetchError("Could not fetch currency list.")
            return list(data.get("currencies", {}).keys())
        except httpx.RequestError as e:
            raise RateFetchError(f"Network error: {e}") from e
