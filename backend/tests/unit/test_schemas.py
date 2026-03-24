import pytest
from pydantic import ValidationError
from backend.models import ChatRequest, ChatResponse, Message


def test_chat_request_valid():
    req = ChatRequest(message="What is EUR/USD?")
    assert req.message == "What is EUR/USD?"
    assert req.history == []


def test_chat_request_with_history():
    req = ChatRequest(
        message="And GBP?",
        history=[{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello"}],
    )
    assert len(req.history) == 2


def test_chat_request_empty_message_rejected():
    with pytest.raises(ValidationError):
        ChatRequest(message="")


def test_chat_request_whitespace_message_rejected():
    with pytest.raises(ValidationError):
        ChatRequest(message="   ")


def test_chat_response_valid():
    resp = ChatResponse(reply="EUR/USD is 1.08", data={"rate": 1.08}, tool_used="get_exchange_rate")
    assert resp.reply == "EUR/USD is 1.08"


def test_chat_response_minimal():
    resp = ChatResponse(reply="Hello")
    assert resp.data is None
    assert resp.tool_used is None
