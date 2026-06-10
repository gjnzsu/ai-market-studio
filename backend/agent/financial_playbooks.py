from dataclasses import dataclass


@dataclass(frozen=True)
class PlaybookIdentity:
    id: str
    display_name: str
    intent_triggers: tuple[str, ...]


@dataclass(frozen=True)
class SourceContract:
    required_sources: tuple[str, ...]
    optional_sources: tuple[str, ...]
    gap_sources: tuple[str, ...] = ()


@dataclass(frozen=True)
class OutputContract:
    output_sections: tuple[str, ...]


@dataclass(frozen=True)
class RuntimeProfile:
    profile_ids: tuple[str, ...]
    synthetic_sources: tuple[str, ...] = ()
    research_only: bool = True


@dataclass(frozen=True)
class FinancialAnalysisPlaybook:
    identity: PlaybookIdentity
    source_contract: SourceContract
    output_contract: OutputContract
    runtime_profile: RuntimeProfile
    rule_ids: tuple[str, ...]

    @property
    def id(self) -> str:
        return self.identity.id

    @property
    def display_name(self) -> str:
        return self.identity.display_name

    @property
    def intent_triggers(self) -> tuple[str, ...]:
        return self.identity.intent_triggers

    @property
    def required_sources(self) -> tuple[str, ...]:
        return self.source_contract.required_sources

    @property
    def optional_sources(self) -> tuple[str, ...]:
        return self.source_contract.optional_sources

    @property
    def output_sections(self) -> tuple[str, ...]:
        return self.output_contract.output_sections

    @property
    def data_gap_sources(self) -> tuple[str, ...]:
        return self.source_contract.gap_sources

    @property
    def research_only(self) -> bool:
        return self.runtime_profile.research_only


def _playbook(
    *,
    id: str,
    display_name: str,
    intent_triggers: tuple[str, ...],
    required_sources: tuple[str, ...],
    optional_sources: tuple[str, ...],
    output_sections: tuple[str, ...],
    data_gap_sources: tuple[str, ...] = (),
    profile_ids: tuple[str, ...] = ("research_only",),
    synthetic_sources: tuple[str, ...] = (),
    rule_ids: tuple[str, ...] = (
        "source_grounding",
        "data_gap_reporting",
        "no_execution_advice",
    ),
) -> FinancialAnalysisPlaybook:
    return FinancialAnalysisPlaybook(
        identity=PlaybookIdentity(
            id=id,
            display_name=display_name,
            intent_triggers=intent_triggers,
        ),
        source_contract=SourceContract(
            required_sources=required_sources,
            optional_sources=optional_sources,
            gap_sources=data_gap_sources,
        ),
        output_contract=OutputContract(output_sections=output_sections),
        runtime_profile=RuntimeProfile(
            profile_ids=profile_ids,
            synthetic_sources=synthetic_sources,
        ),
        rule_ids=rule_ids,
    )


_PLAYBOOKS: tuple[FinancialAnalysisPlaybook, ...] = (
    _playbook(
        id="general",
        display_name="General Market Briefing",
        intent_triggers=("briefing", "overview", "explain", "insight", "synthesis"),
        required_sources=("rates",),
        optional_sources=("news", "fred", "research"),
        output_sections=("market_context", "analysis", "briefing", "warnings"),
    ),
    _playbook(
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
        profile_ids=("research_only", "demo_synthetic_fx"),
        synthetic_sources=("forward_curve", "implied_volatility"),
        rule_ids=(
            "source_grounding",
            "data_gap_reporting",
            "synthetic_source_disclosure",
            "no_execution_advice",
        ),
    ),
    _playbook(
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
    _playbook(
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
    _playbook(
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


def has_runtime_profile(
    playbook: FinancialAnalysisPlaybook,
    profile_id: str,
) -> bool:
    return profile_id in playbook.runtime_profile.profile_ids


def synthetic_sources_for_playbook(playbook: FinancialAnalysisPlaybook) -> list[str]:
    if not has_runtime_profile(playbook, "demo_synthetic_fx"):
        return []
    return list(playbook.runtime_profile.synthetic_sources)


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
