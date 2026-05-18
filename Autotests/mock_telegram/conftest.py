"""Pytest fixtures for the Telegram mock test suite.

Two session-scoped resources:

- `llm` — `LlmMockController` on tcp:9765 (reused from `Autotests/mock/`).
  The agent's Test provider connects to it for deterministic answers.
- `tg`  — `MockTelegramServer` on tcp:9766. The agent's Telegram adapter is
  pointed at it via `TG_API_BASE=http://172.17.0.1:9766`. Tests inject
  inbound user messages and pop the agent's outbound replies.

An `autouse` session fixture sends `auth <secret>` once as the test user,
so subsequent injects pass the adapter's first-user auth gate.
"""
import os
import sys
import time

import pytest

# Reuse the LLM mock harness from Autotests/mock/ without duplicating its code.
_MOCK_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "mock"))
if _MOCK_DIR not in sys.path:
    sys.path.insert(0, _MOCK_DIR)

# Allow this directory to import its own siblings (server.py, helpers.py).
_SELF_DIR = os.path.dirname(__file__)
if _SELF_DIR not in sys.path:
    sys.path.insert(0, _SELF_DIR)

from llm import LlmMockController  # noqa: E402
from rpc import PORT_DEFAULT as LLM_PORT_DEFAULT  # noqa: E402

from server import MockTelegramServer, PORT_DEFAULT as TG_PORT_DEFAULT  # noqa: E402


AUTH_SECRET = os.environ.get("OMEGACLAW_AUTH_SECRET") or "0000"
TG_TOKEN = os.environ.get("MOCK_TG_TOKEN") or "DUMMYTESTTOKEN"


@pytest.fixture(scope="session")
def llm():
    controller = LlmMockController(("0.0.0.0", LLM_PORT_DEFAULT))
    try:
        yield controller
    finally:
        controller.stop(5)


@pytest.fixture(scope="session")
def tg():
    server = MockTelegramServer(("0.0.0.0", TG_PORT_DEFAULT), expected_token=TG_TOKEN)
    server.start()
    try:
        yield server
    finally:
        server.stop(5)


@pytest.fixture(scope="session", autouse=True)
def _tg_authenticate(tg):
    """Bind the test user as the authenticated owner of the agent's TG channel.

    The adapter's first-user auth gate accepts the first sender of
    `auth <secret>`; later senders are ignored. Doing this once per session
    is enough — all later injects use the same user_id/chat_id.
    """
    # The agent may take a moment after container start to poll getUpdates.
    # Inject auth and wait briefly for the confirmation reply, but do not
    # fail the session if it never arrives (the per-test prompts will surface
    # any real auth failure).
    tg.inject_user_message(f"auth {AUTH_SECRET}")
    print(f"[conftest] sent auth secret to mock TG; waiting for agent confirmation", flush=True)
    # If the agent was already authenticated from a previous pytest run against
    # the same container, the adapter silently ignores the second auth — no
    # reply is sent. A short window is enough; tests will surface a real auth
    # failure on their own prompts anyway.
    chat_id, text = tg.pop_agent_reply(timeout=15)
    if text is None:
        print("[conftest] no agent reply to auth (likely already authenticated "
              "from a prior run); proceeding", flush=True)
    else:
        print(f"[conftest] agent confirmed auth: chat={chat_id} text={text!r}", flush=True)
    # Soak any extra greetings.
    extras = tg.drain_agent_replies(max_wait=3)
    if extras:
        print(f"[conftest] drained {len(extras)} extra agent replies post-auth", flush=True)
    yield
