"""Multi-provider LLM client with fallback chain."""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Optional

import requests

logger = logging.getLogger("futuredecoded.llm")

GITHUB_MODELS_DEFAULT_MODEL = "openai/gpt-4o-mini"
GITHUB_MODELS_DEFAULT_BASE_URL = "https://models.github.ai"


def _strip_json_fences(text: str) -> str:
    return re.sub(r"```(?:json)?\s*|\s*```", "", text).strip()


class ProviderClient:
    """Gemini → Groq → GitHub Models → OpenRouter → OpenAI → Ollama."""

    def __init__(
        self,
        gemini_key: str = "",
        groq_key: str = "",
        github_models_token: str = "",
        github_models_model: str = GITHUB_MODELS_DEFAULT_MODEL,
        github_models_base_url: str = GITHUB_MODELS_DEFAULT_BASE_URL,
        openrouter_key: str = "",
        openai_key: str = "",
        ollama_url: str = "http://localhost:11434",
    ):
        self.gemini_key = gemini_key
        self.groq_key = groq_key
        self.github_models_token = github_models_token
        self.github_models_model = github_models_model
        self.github_models_base_url = github_models_base_url.rstrip("/")
        self.openrouter_key = openrouter_key
        self.openai_key = openai_key
        self.ollama_url = ollama_url.rstrip("/")
        self._disabled_providers: set[str] = set()
        self._providers = self._build_chain()

    def _is_rate_limit_error(self, exc: Exception) -> bool:
        message = str(exc).lower()
        return "429" in message or "rate limit" in message or "resource_exhausted" in message or "quota" in message

    def _disable_provider(self, provider: str, exc: Exception) -> None:
        if self._is_rate_limit_error(exc):
            self._disabled_providers.add(provider)
            logger.warning("Provider disabled for this run due to quota: %s", provider)

    def _resolve_github_models_token(self) -> str:
        return (
            self.github_models_token
            or os.environ.get("GITHUB_MODELS_TOKEN", "")
            or os.environ.get("GITHUB_TOKEN", "")
        )

    def _build_chain(self) -> list[str]:
        custom_order = os.environ.get("LLM_PROVIDER_ORDER", "").strip()
        if custom_order:
            return [provider.strip() for provider in custom_order.split(",") if provider.strip()]

        chain: list[str] = []
        if os.environ.get("GITHUB_ACTIONS") == "true" and self._resolve_github_models_token():
            chain.append("github_models")
        if self.gemini_key:
            chain.append("gemini")
        if self.groq_key:
            chain.append("groq")
        if self._resolve_github_models_token() and "github_models" not in chain:
            chain.append("github_models")
        if self.openrouter_key:
            chain.append("openrouter")
        if self.openai_key:
            chain.append("openai")
        if os.environ.get("GITHUB_ACTIONS") != "true":
            chain.append("ollama")
        return chain

    def call(self, prompt: str, max_tokens: int = 4096) -> str:
        errors: list[str] = []
        for provider in self._providers:
            if provider in self._disabled_providers:
                continue
            try:
                logger.info("LLM attempt: provider=%s", provider)
                response = self._dispatch(provider, prompt, max_tokens)
                logger.info("LLM success: provider=%s", provider)
                return response
            except Exception as exc:
                self._disable_provider(provider, exc)
                errors.append(f"{provider}: {exc}")
                logger.warning("LLM provider %s failed: %s", provider, str(exc)[:200])
        raise RuntimeError("All LLM providers failed: " + "; ".join(errors[:4]))

    def call_json(self, prompt: str) -> dict[str, Any]:
        json_prompt = (
            prompt + "\n\nRespond ONLY with valid JSON. No markdown fences."
        )
        raw = self.call(json_prompt)
        cleaned = _strip_json_fences(raw)
        return json.loads(cleaned)

    def _dispatch(self, provider: str, prompt: str, max_tokens: int) -> str:
        if provider == "gemini":
            return self._call_gemini(prompt)
        if provider == "groq":
            return self._call_groq(prompt, max_tokens)
        if provider == "github_models":
            return self._call_github_models(prompt, max_tokens)
        if provider == "openrouter":
            return self._call_openrouter(prompt, max_tokens)
        if provider == "openai":
            return self._call_openai(prompt, max_tokens)
        return self._call_ollama(prompt)

    def _call_gemini(self, prompt: str) -> str:
        import google.genai as genai
        client = genai.Client(api_key=self.gemini_key)
        resp = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
        )
        return resp.text

    def _call_groq(self, prompt: str, max_tokens: int) -> str:
        from groq import Groq
        client = Groq(api_key=self.groq_key)
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content

    def _call_github_models(self, prompt: str, max_tokens: int) -> str:
        token = self._resolve_github_models_token()
        if not token:
            raise RuntimeError("GitHub Models token not configured")

        payload: dict[str, Any] = {
            "model": self.github_models_model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
        }
        if "respond only with valid json" in prompt.lower():
            payload["response_format"] = {"type": "json_object"}

        resp = requests.post(
            f"{self.github_models_base_url}/inference/chat/completions",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=90,
        )
        if resp.status_code >= 400:
            logger.warning("GitHub Models error %s: %s", resp.status_code, resp.text[:300])
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    def _call_openrouter(self, prompt: str, max_tokens: int) -> str:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.openrouter_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "google/gemini-2.0-flash-001",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
            },
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    def _call_openai(self, prompt: str, max_tokens: int) -> str:
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.openai_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
            },
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    def _call_ollama(self, prompt: str) -> str:
        resp = requests.post(
            f"{self.ollama_url}/api/generate",
            json={"model": "llama3.2", "prompt": prompt, "stream": False},
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["response"]


_client: Optional[ProviderClient] = None


def get_llm_client() -> ProviderClient:
    global _client
    if _client is None:
        from futuredecoded.config.settings import get_settings
        settings = get_settings()
        _client = ProviderClient(
            gemini_key=settings.gemini_api_key,
            groq_key=settings.groq_api_key,
            github_models_token=settings.github_models_token,
            github_models_model=settings.github_models_model,
            github_models_base_url=settings.github_models_base_url,
            openrouter_key=settings.openrouter_api_key,
            openai_key=settings.openai_api_key,
            ollama_url=settings.ollama_base_url,
        )
    return _client
