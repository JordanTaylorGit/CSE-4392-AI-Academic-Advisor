"""LLM + embeddings backend configuration.

Backend is selected by the ADVISOR_LLM env var ("ollama" default, or "openai").
Both backends expose the same LangChain interfaces, so the rest of the code
never branches on the provider.
"""

import os
from dataclasses import dataclass


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


@dataclass(frozen=True)
class Settings:
    backend: str
    chat_model: str
    embed_model: str
    router_model: str | None = None
    ollama_base_url: str = "http://localhost:11434"


def get_settings() -> Settings:
    backend = _env("ADVISOR_LLM", "ollama").lower()
    if backend == "openai":
        model = _env("ADVISOR_OPENAI_MODEL", "gpt-4o-mini")
        return Settings(
            backend="openai",
            chat_model=model,
            embed_model=_env("ADVISOR_OPENAI_EMBED_MODEL", "text-embedding-3-small"),
            router_model=_env("ADVISOR_ROUTER_MODEL", model),
        )
    return Settings(
        backend="ollama",
        chat_model=_env("ADVISOR_OLLAMA_MODEL", "qwen3:4b"),
        embed_model=_env("ADVISOR_OLLAMA_EMBED_MODEL", "nomic-embed-text"),
        # Intent routing is a trivial 7-label classification — a tiny model is
        # far more responsive on CPU-bound laptops than the main chat model.
        router_model=_env("ADVISOR_ROUTER_MODEL", "qwen3:0.6b"),
        ollama_base_url=_env("ADVISOR_OLLAMA_BASE_URL", "http://localhost:11434"),
    )


def get_chat_model(**kwargs):
    """Return a LangChain chat model for the configured backend."""
    s = get_settings()
    if s.backend == "openai":
        from langchain_openai import ChatOpenAI

        # 'reasoning=False' is the Ollama think-block toggle; not valid on
        # ChatOpenAI, so drop it when callers pass it through generically.
        if kwargs.get("reasoning") is False:
            kwargs.pop("reasoning")
        return ChatOpenAI(model=s.chat_model, **kwargs)
    from langchain_ollama import ChatOllama

    # qwen3-class models default to a ~40k context; llama-server then tries to
    # allocate a ~19GB KV cache and OOMs on typical laptops. Cap it.
    kwargs.setdefault("num_ctx", int(_env("ADVISOR_OLLAMA_NUM_CTX", "4096")))
    return ChatOllama(model=s.chat_model, base_url=s.ollama_base_url, **kwargs)


def get_router_model(**kwargs):
    """Return a small, fast model for intent classification.

    Defaults to ADVISOR_ROUTER_MODEL (qwen3:0.6b on Ollama, the chat model on
    OpenAI). Routing latency is user-visible on every message, so it gets its
    own model rather than sharing the slower high-quality one.
    """
    s = get_settings()
    kwargs.setdefault("temperature", 0)
    kwargs.setdefault("reasoning", False)
    if s.backend == "openai":
        if kwargs.get("reasoning") is False:
            kwargs.pop("reasoning")
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=s.router_model or s.chat_model, **kwargs)
    from langchain_ollama import ChatOllama

    kwargs.setdefault("num_ctx", int(_env("ADVISOR_OLLAMA_NUM_CTX", "4096")))
    return ChatOllama(
        model=s.router_model or s.chat_model,
        base_url=s.ollama_base_url,
        **kwargs,
    )


def get_embeddings(**kwargs):
    """Return a LangChain embeddings model for the configured backend."""
    s = get_settings()
    if s.backend == "openai":
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(model=s.embed_model, **kwargs)
    from langchain_ollama import OllamaEmbeddings

    return OllamaEmbeddings(model=s.embed_model, base_url=s.ollama_base_url, **kwargs)
