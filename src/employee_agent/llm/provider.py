from __future__ import annotations

import litellm
from browser_use.llm.litellm import ChatLiteLLM

# 기업 SSL 인터셉션 환경에서 self-signed 인증서 우회
litellm.ssl_verify = False


def get_llm(cfg: object) -> ChatLiteLLM:
    """Return a browser-use-native LLM client.

    ChatLiteLLM satisfies browser-use's BaseChatModel Protocol (.provider, .name)
    and accepts api_base for any OpenAI-compatible endpoint.
    """
    return ChatLiteLLM(
        model=cfg.LLM_MODEL,  # type: ignore[attr-defined]
        api_key=cfg.LLM_API_KEY,  # type: ignore[attr-defined]
        api_base=cfg.LLM_BASE_URL,  # type: ignore[attr-defined]
    )
