"""Chat boundary in ui/services.ask (Person E): backend replies are normalized,
leaked reasoning is hidden, and backend errors never reach the UI as tracebacks."""

import pytest

from advisor import tracing
from ui import services as svc


@pytest.fixture(autouse=True)
def scratch_log(tmp_path, monkeypatch):
    monkeypatch.setattr(tracing, "TRACE_LOG", tmp_path / "t.jsonl")
    monkeypatch.setattr(tracing, "LOGS_DIR", tmp_path)


def reply_with(monkeypatch, fn):
    monkeypatch.setattr(svc.orchestrator, "handle_message", fn)
    return svc.ask("s1", "hello", [], None, use_preview=False)


def test_plain_string_reply(monkeypatch):
    reply, source = reply_with(monkeypatch, lambda *a: "Hi there")
    assert reply == {"text": "Hi there", "cards": []} and source == "live"


def test_reasoning_is_hidden_even_without_opening_tag(monkeypatch):
    reply, _ = reply_with(monkeypatch, lambda *a: "Okay, the user said hi.\n</think>\n\nHi!")
    assert reply["text"] == "Hi!"
    reply, _ = reply_with(monkeypatch, lambda *a: {"text": "<think>x</think>Done", "cards": []})
    assert reply["text"] == "Done"


def test_backend_error_becomes_a_reply(monkeypatch):
    def boom(*a):
        raise ValueError("An explicit term is required")
    reply, _ = reply_with(monkeypatch, boom)
    assert "An explicit term is required" in reply["text"]
    assert any('"event": "error"' in line for line in tracing.TRACE_LOG.read_text().splitlines())


def test_stub_backend_is_not_ready(monkeypatch):
    def stub(*a):
        raise NotImplementedError("TODO Kyle")
    with pytest.raises(svc.NotReady):
        reply_with(monkeypatch, stub)
