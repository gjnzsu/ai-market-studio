from backend.agent.financial_playbooks import (
    get_playbook,
    list_playbooks,
    select_playbook,
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
