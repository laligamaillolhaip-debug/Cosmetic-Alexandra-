import sys
from types import SimpleNamespace

import httpx
import pytest

from app.services import ai
from app.services.ai import AIUnavailable


class FakeResponse:
    def __init__(self, payload=None, status_code=200, error=None):
        self.payload = payload
        self.status_code = status_code
        self.error = error
        self.text = "response body"

    def json(self):
        if self.error:
            raise self.error
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "request failed",
                request=httpx.Request("POST", "http://localhost"),
                response=httpx.Response(self.status_code),
            )


def install_http_client(monkeypatch, response=None, post_error=None, get_response=None):
    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def post(self, *_args, **_kwargs):
            if post_error:
                raise post_error
            return response

        def get(self, *_args, **_kwargs):
            return get_response

    monkeypatch.setattr(ai.httpx, "Client", FakeClient)


def test_local_complete_returns_user_message_and_strips_reasoning(monkeypatch):
    install_http_client(monkeypatch, response=FakeResponse({"output": [
        {"type": "reasoning", "content": "hidden"},
        {"type": "message", "content": "<think>internal</think>Useful response"},
    ]}))

    assert ai._local_complete("system", "prompt") == "Useful response"


def test_local_complete_rejects_empty_or_reasoning_only_response(monkeypatch):
    install_http_client(monkeypatch, response=FakeResponse({"output": [
        {"type": "reasoning", "content": "internal"},
    ]}))

    with pytest.raises(AIUnavailable, match="пустой ответ"):
        ai._local_complete("system", "prompt")


def test_local_complete_converts_invalid_json_to_ai_unavailable(monkeypatch):
    install_http_client(
        monkeypatch,
        response=FakeResponse(error=ValueError("invalid json")),
    )

    with pytest.raises(AIUnavailable):
        ai._local_complete("system", "prompt")


def test_local_complete_converts_network_failure_to_ai_unavailable(monkeypatch):
    install_http_client(monkeypatch, post_error=httpx.ConnectError("offline"))

    with pytest.raises(AIUnavailable, match="Локальная модель не отвечает"):
        ai._local_complete("system", "prompt")


def test_anthropic_provider_without_key_does_not_make_a_request(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(AIUnavailable, match="Не задан ANTHROPIC_API_KEY"):
        ai._anthropic_complete("system", "prompt")


def test_anthropic_complete_extracts_text_without_network(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    class FakeAnthropic:
        def __init__(self, api_key):
            assert api_key == "test-key"
            self.messages = self

        def create(self, **_kwargs):
            return SimpleNamespace(content=[
                SimpleNamespace(type="thinking", text="hidden"),
                SimpleNamespace(type="text", text="Answer"),
            ])

    monkeypatch.setitem(sys.modules, "anthropic", SimpleNamespace(
        Anthropic=FakeAnthropic,
        APIError=RuntimeError,
    ))

    assert ai._anthropic_complete("system", "prompt") == "Answer"


def test_anthropic_complete_converts_provider_error(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    class FakeApiError(Exception):
        pass

    class FakeAnthropic:
        def __init__(self, **_kwargs):
            self.messages = self

        def create(self, **_kwargs):
            raise FakeApiError("provider unavailable")

    monkeypatch.setitem(sys.modules, "anthropic", SimpleNamespace(
        Anthropic=FakeAnthropic,
        APIError=FakeApiError,
    ))

    with pytest.raises(AIUnavailable, match="Claude временно недоступен"):
        ai._anthropic_complete("system", "prompt")


@pytest.mark.parametrize(("payload", "error", "finish_reason", "expected"), [
    ({"choices": [{"message": {"content": '{"plan": true}'}, "finish_reason": "stop"}]},
     None, None, '{"plan": true}'),
    (None, ValueError("invalid json"), None, None),
    ({"choices": []}, None, None, None),
    ({"choices": [{"message": {"content": "{}"}, "finish_reason": "length"}]},
     None, "length", None),
    ({"choices": [{"message": {"content": ""}, "finish_reason": "stop"}]},
     None, None, None),
])
def test_complete_structured_response_cases(monkeypatch, payload, error, finish_reason, expected):
    monkeypatch.setattr(ai, "PROVIDER", "local")
    response_payload = payload
    response_error = error
    if finish_reason:
        response_payload = {"choices": [{
            "message": {"content": "{}"},
            "finish_reason": finish_reason,
        }]}
    install_http_client(
        monkeypatch,
        response=FakeResponse(payload=response_payload, error=response_error),
    )

    if expected is not None:
        assert ai.complete_structured("prompt", {"type": "object"}, "system") == expected
    else:
        with pytest.raises(AIUnavailable):
            ai.complete_structured("prompt", {"type": "object"}, "system")


def test_complete_structured_rejects_reasoning_only_response(monkeypatch):
    monkeypatch.setattr(ai, "PROVIDER", "local")
    install_http_client(monkeypatch, response=FakeResponse({
        "choices": [{
            "message": {"content": "<think>internal reasoning</think>"},
            "finish_reason": "stop",
        }]
    }))

    with pytest.raises(AIUnavailable):
        ai.complete_structured("prompt", {"type": "object"}, "system")


def test_status_anthropic_reports_key_without_network(monkeypatch):
    monkeypatch.setattr(ai, "PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    assert ai.status()["ok"] is True


def test_status_local_checks_loaded_model(monkeypatch):
    monkeypatch.setattr(ai, "PROVIDER", "local")
    monkeypatch.setattr(ai, "LOCAL_MODEL", "local-model")
    install_http_client(monkeypatch, get_response=FakeResponse({
        "models": [{"key": "other-model"}, {"key": "local-model"}],
    }))

    status = ai.status()

    assert status["ok"] is True
    assert status["loaded_models"] == ["other-model", "local-model"]
