from backend.attribution import (
    attribution_headers,
    business_metric_labels,
    classify_use_case,
    ensure_request_id,
)
from backend.models import ChatClientContext


def test_ensure_request_id_preserves_client_value():
    context = ChatClientContext(requestId="req-123")
    assert ensure_request_id(context) == "req-123"


def test_ensure_request_id_generates_value_when_absent():
    assert ensure_request_id(None)


def test_classifies_market_context_as_fx_data_query():
    use_case, feature = classify_use_case(
        message="What is EUR/USD?",
        tool_used="collect_market_context",
        data={"type": "market_context"},
        context=None,
    )
    assert use_case == "fx-data-query"
    assert feature == "query-result-generation"


def test_classifies_market_briefing_as_advisory_report():
    use_case, feature = classify_use_case(
        message="Give me a market insight on EUR/USD",
        tool_used="generate_market_briefing",
        data={"type": "market_briefing"},
        context=None,
    )
    assert use_case == "fx-advisory-report"
    assert feature == "advisory-report-generation"


def test_classifies_dashboard_intent_from_message():
    use_case, feature = classify_use_case(
        message="Show EUR/USD trend last 5 days",
        tool_used="collect_market_context",
        data={"type": "market_context"},
        context=None,
    )
    assert use_case == "chat-dashboard-generation"
    assert feature == "dashboard-generation"


def test_explicit_client_context_overrides_fallback_classification():
    context = ChatClientContext(
        useCase="fx-advisory-report",
        feature="advisory-report-generation",
    )
    use_case, feature = classify_use_case(
        message="Show EUR/USD trend",
        tool_used="collect_market_context",
        data={"type": "market_context"},
        context=context,
    )
    assert use_case == "fx-advisory-report"
    assert feature == "advisory-report-generation"


def test_gateway_headers_include_request_and_low_cardinality_context():
    context = ChatClientContext(projectId="fx-market-insight", teamId="markets")
    headers = attribution_headers(
        context=context,
        request_id="req-123",
        use_case="fx-data-query",
        feature="query-result-generation",
    )
    assert headers["X-Request-ID"] == "req-123"
    assert headers["X-Consumer-Service"] == "ai-market-studio"
    assert headers["X-AI-Project-ID"] == "fx-market-insight"
    assert headers["X-AI-Team-ID"] == "markets"


def test_business_metric_labels_exclude_user_session_and_conversation_ids():
    context = ChatClientContext(
        userId="u-123",
        sessionId="s-123",
        conversationId="c-123",
    )
    labels = business_metric_labels(
        context=context,
        use_case="fx-data-query",
        feature="query-result-generation",
        tool_used="collect_market_context",
        status="success",
    )
    assert "user_id" not in labels
    assert "session_id" not in labels
    assert "conversation_id" not in labels
    assert labels["use_case"] == "fx-data-query"
