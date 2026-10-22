"""Calls to other LLMs over their official HTTP APIs.

API keys are read from the environment at call time and are never logged,
returned to the client, or included in error messages.
"""

import json
import logging
import os

import httpx

from .config import Settings

log = logging.getLogger(__name__)


class ProviderError(Exception):
    """A failure that is safe to show to the MCP client."""


class LLMClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.calls_used = 0

    async def complete_json(self, system: str, prompt: str) -> str:
        """Ask the configured model for a JSON reply and return the raw text."""
        s = self.settings
        if self.calls_used >= s.max_calls:
            raise ProviderError(
                f"LLM call limit reached ({s.max_calls}). Raise MUSIC_LLM_MAX_CALLS or restart the server."
            )
        self.calls_used += 1
        log.info("calling %s/%s (call %d/%d)", s.provider, s.model, self.calls_used, s.max_calls)

        try:
            async with httpx.AsyncClient(timeout=s.timeout_s) as http:
                if s.provider == "openai":
                    return await self._openai(http, system, prompt)
                if s.provider == "gemini":
                    return await self._gemini(http, system, prompt)
                if s.provider == "ollama":
                    return await self._ollama(http, system, prompt)
        except httpx.TimeoutException:
            raise ProviderError(f"{s.provider} did not answer within {s.timeout_s:.0f}s") from None
        except httpx.HTTPStatusError as e:
            raise ProviderError(f"{s.provider} returned HTTP {e.response.status_code}") from None
        except httpx.HTTPError as e:
            raise ProviderError(f"could not reach {s.provider}: {type(e).__name__}") from None
        except (KeyError, IndexError, TypeError, json.JSONDecodeError):
            raise ProviderError(f"unexpected response format from {s.provider}") from None
        raise ProviderError(f"provider {s.provider!r} cannot be called over HTTP")

    @staticmethod
    def _key(name: str) -> str:
        key = os.environ.get(name, "").strip()
        if not key:
            raise ProviderError(f"{name} is not set. Add it to the MCP server's env config.")
        return key

    async def _openai(self, http: httpx.AsyncClient, system: str, prompt: str) -> str:
        base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        r = await http.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {self._key('OPENAI_API_KEY')}"},
            json={
                "model": self.settings.model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
                "max_completion_tokens": self.settings.max_tokens,
            },
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    async def _gemini(self, http: httpx.AsyncClient, system: str, prompt: str) -> str:
        r = await http.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.settings.model}:generateContent",
            # Header, not ?key= query param, so the key never ends up in URLs or logs.
            headers={"x-goog-api-key": self._key("GEMINI_API_KEY")},
            json={
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "maxOutputTokens": self.settings.max_tokens,
                },
            },
        )
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]

    async def _ollama(self, http: httpx.AsyncClient, system: str, prompt: str) -> str:
        base = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
        r = await http.post(
            f"{base}/api/chat",
            json={
                "model": self.settings.model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                "format": "json",
                "stream": False,
                "options": {"num_predict": self.settings.max_tokens},
            },
        )
        r.raise_for_status()
        return r.json()["message"]["content"]
