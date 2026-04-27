"""
Multi-agent system for AI Market Studio.

Sub-agents:
- Data Collector: Fetches raw market data from all sources
- Market Analyst: Analyzes trends, volatility, correlations, signals
- Report Generator: Creates formatted outputs (PDF, dashboard, summary)
- Research Synthesizer: Combines multi-source intelligence
"""

from backend.agents.data_collector import collect_market_data
from backend.agents.market_analyst import analyze_market_trends
from backend.agents.report_generator import generate_report
from backend.agents.research_synthesizer import synthesize_research

__all__ = [
    "collect_market_data",
    "analyze_market_trends",
    "generate_report",
    "synthesize_research",
]
