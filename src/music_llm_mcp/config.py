"""Settings come only from environment variables, never from code or tool arguments."""

import os
from dataclasses import dataclass
from pathlib import Path

PROVIDERS = ("mock", "openai", "gemini", "ollama")

DEFAULT_MODELS = {
    "mock": "mock",
    "openai": "gpt-4.1-mini",
    "gemini": "gemini-2.5-flash",
    "ollama": "llama3.2",
}


@dataclass(frozen=True)
class Settings:
    provider: str
    model: str
    output_dir: Path
    timeout_s: float
    max_tokens: int
    max_calls: int  # LLM calls allowed per server process (cost guard)


def _number(name: str, default: float, lo: float, hi: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = float(raw)
    except ValueError:
        raise ValueError(f"{name} must be a number, got {raw!r}") from None
    if not lo <= value <= hi:
        raise ValueError(f"{name} must be between {lo} and {hi}, got {value}")
    return value


def load_settings() -> Settings:
    provider = os.environ.get("MUSIC_LLM_PROVIDER", "mock").strip().lower()
    if provider not in PROVIDERS:
        raise ValueError(f"MUSIC_LLM_PROVIDER must be one of {PROVIDERS}, got {provider!r}")

    output_dir = Path(
        os.environ.get("MUSIC_LLM_OUTPUT_DIR") or Path.home() / "music-llm-output"
    ).expanduser().resolve()

    return Settings(
        provider=provider,
        model=os.environ.get("MUSIC_LLM_MODEL") or DEFAULT_MODELS[provider],
        output_dir=output_dir,
        timeout_s=_number("MUSIC_LLM_TIMEOUT", 60, 1, 600),
        max_tokens=int(_number("MUSIC_LLM_MAX_TOKENS", 2000, 100, 16000)),
        max_calls=int(_number("MUSIC_LLM_MAX_CALLS", 50, 1, 10000)),
    )
