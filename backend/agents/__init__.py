"""
Multi-agent system for AI Market Studio.

Sub-agents:
- Data Collector: Fetches raw market data from all sources
- Market Analyst: Analyzes trends, volatility, correlations, signals
- Report Generator: Creates formatted outputs (PDF, dashboard, summary)
- Research Synthesizer: Combines multi-source intelligence
"""

from backend.agents.data_collector import collect_market_data

__all__ = [
    "collect_market_data",
]
