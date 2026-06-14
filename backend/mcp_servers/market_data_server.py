from datetime import date as date_type, timedelta
import math
from typing import Optional

from mcp.server.fastmcp import FastMCP


SOURCE_NAME = "mcp-mock-market-data"

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

SUPPORTED_CURRENCIES = [
    "USD",
    "EUR",
    "GBP",
    "JPY",
    "AUD",
    "CAD",
    "CHF",
    "CNY",
    "HKD",
    "SGD",
    "NZD",
]

mcp = FastMCP("ai-mcp-market-data")


def _split_pair(pair: str) -> tuple[str, str]:
    normalized = pair.upper().replace("-", "/")
    if "/" not in normalized and len(normalized) == 6 and normalized.isalpha():
        return normalized[:3], normalized[3:]
    parts = normalized.split("/")
    if len(parts) != 2:
        raise ValueError(f"Invalid currency pair: {pair}")
    return parts[0], parts[1]


def _format_pair(pair: str) -> str:
    base, target = _split_pair(pair)
    return f"{base}/{target}"


def _rate_for(base: str, target: str) -> float:
    if base == target:
        return 1.0
    if base not in SUPPORTED_CURRENCIES or target not in SUPPORTED_CURRENCIES:
        raise ValueError(f"Unsupported currency pair: {base}/{target}")

    usd_base = DEFAULT_RATES.get(f"USD{base}", 1.0) if base != "USD" else 1.0
    usd_target = DEFAULT_RATES.get(f"USD{target}", 1.0) if target != "USD" else 1.0
    return round(usd_target / usd_base, 6)


def _history_delta(pair: str, index: int) -> float:
    seed = sum((position + 1) * ord(char) for position, char in enumerate(pair))
    amplitude = ((seed % 17) + 3) / 10_000
    return round(math.sin(index * 0.45) * amplitude, 6)


@mcp.tool()
def get_fx_spot(pair: str, date: Optional[str] = None) -> dict:
    base, target = _split_pair(pair)
    return {
        "pair": f"{base}/{target}",
        "base": base,
        "target": target,
        "rate": _rate_for(base, target),
        "date": date or date_type.today().isoformat(),
        "source": SOURCE_NAME,
    }


@mcp.tool()
def get_fx_history(pair: str, start_date: str, end_date: str) -> dict:
    formatted_pair = _format_pair(pair)
    base, target = _split_pair(formatted_pair)
    start = date_type.fromisoformat(start_date)
    end = date_type.fromisoformat(end_date)
    if end < start:
        raise ValueError("end_date must be on or after start_date")

    spot = _rate_for(base, target)
    current = start
    index = 0
    rates: dict[str, float] = {}
    while current <= end:
        rates[current.isoformat()] = round(spot + _history_delta(formatted_pair, index), 6)
        current += timedelta(days=1)
        index += 1

    return {
        "pair": formatted_pair,
        "base": base,
        "target": target,
        "rates": rates,
        "source": SOURCE_NAME,
    }


@mcp.tool()
def list_supported_currencies() -> list[str]:
    return SUPPORTED_CURRENCIES


if __name__ == "__main__":
    mcp.run()
