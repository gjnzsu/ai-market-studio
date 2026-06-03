from dataclasses import dataclass


@dataclass(frozen=True)
class FinancialAnalysisPlaybook:
    id: str
    display_name: str
    intent_triggers: tuple[str, ...]
    required_sources: tuple[str, ...]
    optional_sources: tuple[str, ...]
    output_sections: tuple[str, ...]
    data_gap_sources: tuple[str, ...] = ()
    research_only: bool = True


_PLAYBOOKS: tuple[FinancialAnalysisPlaybook, ...] = (
    FinancialAnalysisPlaybook(
        id="general",
        display_name="General Market Briefing",
        intent_triggers=("briefing", "overview", "explain", "insight", "synthesis"),
        required_sources=("rates",),
        optional_sources=("news", "fred", "research"),
        output_sections=("market_context", "analysis", "briefing", "warnings"),
    ),
    FinancialAnalysisPlaybook(
        id="fx_carry",
        display_name="FX Carry Trade Analysis",
        intent_triggers=(
            "carry",
            "carry trade",
            "rate differential",
            "carry-to-vol",
            "forward points",
            "forward curve",
        ),
        required_sources=("rates", "fred"),
        optional_sources=(
            "news",
            "research",
            "forward_curve",
            "implied_volatility",
        ),
        output_sections=(
            "carry_profile",
            "risk_assessment",
            "data_gaps",
            "research_view",
        ),
        data_gap_sources=("forward_curve", "implied_volatility"),
    ),
    FinancialAnalysisPlaybook(
        id="macro_rates",
        display_name="Macro-Rates Monitor",
        intent_triggers=(
            "macro rates",
            "rates monitor",
            "yield curve",
            "policy rate",
            "financial conditions",
            "fed",
            "treasury",
        ),
        required_sources=("rates", "fred"),
        optional_sources=("news", "research", "breakevens", "swap_curve"),
        output_sections=(
            "macro_rates_summary",
            "yield_curve_snapshot",
            "fx_implication",
            "data_gaps",
        ),
        data_gap_sources=("breakevens", "swap_curve"),
    ),
    FinancialAnalysisPlaybook(
        id="morning_note",
        display_name="FX Morning Note",
        intent_triggers=(
            "morning note",
            "morning meeting",
            "overnight",
            "desk note",
            "daily note",
            "morning call",
        ),
        required_sources=("rates", "news"),
        optional_sources=("fred", "research", "catalyst_calendar"),
        output_sections=(
            "top_call",
            "overnight_developments",
            "key_events_today",
            "research_ideas",
        ),
        data_gap_sources=("catalyst_calendar",),
    ),
    FinancialAnalysisPlaybook(
        id="catalyst_calendar",
        display_name="FX and Macro Catalyst Calendar",
        intent_triggers=(
            "catalyst",
            "calendar",
            "upcoming events",
            "event tracker",
            "fomc",
            "cpi",
            "payrolls",
            "central bank",
        ),
        required_sources=("news",),
        optional_sources=("fred", "research", "economic_calendar"),
        output_sections=(
            "watch_universe",
            "event_calendar",
            "weekly_preview",
            "fx_relevance",
        ),
        data_gap_sources=("economic_calendar",),
    ),
)

_PLAYBOOK_BY_ID = {playbook.id: playbook for playbook in _PLAYBOOKS}


def list_playbooks() -> list[FinancialAnalysisPlaybook]:
    return list(_PLAYBOOKS)


def get_playbook(playbook_id: str | None) -> FinancialAnalysisPlaybook:
    if playbook_id and playbook_id in _PLAYBOOK_BY_ID:
        return _PLAYBOOK_BY_ID[playbook_id]
    return _PLAYBOOK_BY_ID["general"]


def select_playbook(
    explicit: str | None = None,
    focus: str | None = None,
) -> FinancialAnalysisPlaybook:
    if explicit:
        return get_playbook(explicit)

    normalized_focus = (focus or "").lower()
    for playbook in _PLAYBOOKS:
        if playbook.id == "general":
            continue
        if any(trigger in normalized_focus for trigger in playbook.intent_triggers):
            return playbook
    return _PLAYBOOK_BY_ID["general"]
