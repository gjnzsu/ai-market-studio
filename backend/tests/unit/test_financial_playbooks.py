from backend.agent.financial_playbooks import (
    get_playbook,
    has_runtime_profile,
    list_playbooks,
    select_playbook,
    synthetic_sources_for_playbook,
)


def test_playbook_registry_includes_initial_playbooks():
    playbooks = list_playbooks()
    ids = [playbook.id for playbook in playbooks]

    assert ids == [
        "general",
        "fx_carry",
        "macro_rates",
        "morning_note",
        "catalyst_calendar",
    ]

    for playbook in playbooks:
        assert playbook.display_name
        assert playbook.intent_triggers
        assert playbook.required_sources
        assert playbook.output_sections


def test_playbook_definitions_expose_runtime_primitives():
    playbook = get_playbook("fx_carry")

    assert playbook.identity.id == "fx_carry"
    assert playbook.source_contract.required_sources == ("rates", "fred")
    assert "forward_curve" in playbook.source_contract.gap_sources
    assert playbook.output_contract.output_sections == playbook.output_sections
    assert "research_only" in playbook.runtime_profile.profile_ids
    assert "source_grounding" in playbook.rule_ids
    assert "synthetic_source_disclosure" in playbook.rule_ids


def test_fx_carry_declares_synthetic_specialist_profile():
    playbook = get_playbook("fx_carry")

    assert has_runtime_profile(playbook, "demo_synthetic_fx")
    assert playbook.runtime_profile.synthetic_sources == (
        "forward_curve",
        "implied_volatility",
    )


def test_non_fx_playbooks_do_not_declare_synthetic_specialist_profile():
    playbook = get_playbook("macro_rates")

    assert not has_runtime_profile(playbook, "demo_synthetic_fx")
    assert playbook.runtime_profile.synthetic_sources == ()


def test_runtime_layer_returns_synthetic_sources_only_for_profiled_playbooks():
    assert synthetic_sources_for_playbook(get_playbook("fx_carry")) == [
        "forward_curve",
        "implied_volatility",
    ]
    assert synthetic_sources_for_playbook(get_playbook("macro_rates")) == []


def test_get_playbook_returns_explicit_supported_playbook():
    playbook = get_playbook("fx_carry")

    assert playbook.id == "fx_carry"
    assert "rates" in playbook.required_sources
    assert "fred" in playbook.required_sources
    assert "forward_curve" in playbook.optional_sources
    assert "implied_volatility" in playbook.optional_sources


def test_select_playbook_uses_explicit_identifier():
    playbook = select_playbook(explicit="macro_rates", focus="morning note")

    assert playbook.id == "macro_rates"


def test_select_playbook_infers_from_focus_text():
    assert select_playbook(focus="Evaluate EUR/USD carry to vol").id == "fx_carry"
    assert select_playbook(focus="Give me a macro rates monitor").id == "macro_rates"
    assert select_playbook(focus="Draft the FX morning note").id == "morning_note"
    assert (
        select_playbook(focus="Build a catalyst calendar for FOMC and CPI").id
        == "catalyst_calendar"
    )


def test_select_playbook_falls_back_to_general():
    playbook = select_playbook(focus="Explain what is happening in EUR/USD")

    assert playbook.id == "general"
