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
    ollama_base_url: str = "http://localhost:11434"


def get_settings() -> Settings:
    backend = _env("ADVISOR_LLM", "ollama").lower()
    if backend == "openai":
        return Settings(
            backend="openai",
            chat_model=_env("ADVISOR_OPENAI_MODEL", "gpt-4o-mini"),
            embed_model=_env("ADVISOR_OPENAI_EMBED_MODEL", "text-embedding-3-small"),
        )
    return Settings(
        backend="ollama",
        chat_model=_env("ADVISOR_OLLAMA_MODEL", "qwen3:4b"),
        embed_model=_env("ADVISOR_OLLAMA_EMBED_MODEL", "nomic-embed-text"),
        ollama_base_url=_env("ADVISOR_OLLAMA_BASE_URL", "http://localhost:11434"),
    )


def get_chat_model(**kwargs):
    """Return a LangChain chat model for the configured backend."""
    s = get_settings()
    if s.backend == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=s.chat_model, **kwargs)
    from langchain_ollama import ChatOllama

    return ChatOllama(model=s.chat_model, base_url=s.ollama_base_url, **kwargs)


def get_embeddings(**kwargs):
    """Return a LangChain embeddings model for the configured backend."""
    s = get_settings()
    if s.backend == "openai":
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(model=s.embed_model, **kwargs)
    from langchain_ollama import OllamaEmbeddings

    return OllamaEmbeddings(model=s.embed_model, base_url=s.ollama_base_url, **kwargs)
