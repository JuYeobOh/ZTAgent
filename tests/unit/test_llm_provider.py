from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from browser_use.llm.litellm import ChatLiteLLM
from employee_agent.llm.provider import get_llm


def make_cfg(
    model: str = "gpt-4o",
    api_key: str = "test-key",
    base_url: str = "https://api.openai.com/v1",
) -> MagicMock:
    cfg = MagicMock()
    cfg.LLM_MODEL = model
    cfg.LLM_API_KEY = api_key
    cfg.LLM_BASE_URL = base_url
    return cfg


# ---------------------------------------------------------------------------
# 1. get_llm returns ChatLiteLLM instance
# ---------------------------------------------------------------------------
def test_get_llm_returns_chatlitellm():
    cfg = make_cfg()
    llm = get_llm(cfg)
    assert isinstance(llm, ChatLiteLLM)


# ---------------------------------------------------------------------------
# 2. ChatLiteLLM satisfies browser-use BaseChatModel Protocol
# ---------------------------------------------------------------------------
def test_get_llm_satisfies_browser_use_protocol():
    cfg = make_cfg(model="gpt-4o-mini")
    llm = get_llm(cfg)
    assert hasattr(llm, "provider"), "ChatLiteLLM must have .provider (Protocol requirement)"
    assert hasattr(llm, "name"), "ChatLiteLLM must have .name (Protocol requirement)"
    assert llm.name == "gpt-4o-mini"


# ---------------------------------------------------------------------------
# 3. api_base is forwarded to ChatLiteLLM
# ---------------------------------------------------------------------------
def test_get_llm_passes_api_base():
    custom_base = "https://custom-llm.internal/v1"
    cfg = make_cfg(base_url=custom_base)
    llm = get_llm(cfg)
    # ChatLiteLLM stores api_base on the instance
    assert llm.api_base == custom_base
