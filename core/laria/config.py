"""Environment-based configuration for LARIA.

Replaces HARIA's Supervisor-options reader: the standalone app is configured
entirely through environment variables (and an optional ``.env`` file loaded by
the deployment, e.g. docker-compose). No assumptions about Home Assistant.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _env_bool(key: str, default: bool = False) -> bool:
    val = os.environ.get(key)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.environ.get(key, str(default)))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class LLMSettings:
    provider: str = field(default_factory=lambda: _env("LLM_PROVIDER", "anthropic"))
    model: str = field(default_factory=lambda: _env("LLM_MODEL", "claude-opus-4-8"))
    max_tokens: int = field(default_factory=lambda: _env_int("LLM_MAX_TOKENS", 4096))
    # Per-provider credentials / endpoints (only the active provider's are required).
    anthropic_api_key: str = field(default_factory=lambda: _env("ANTHROPIC_API_KEY"))
    openai_api_key: str = field(default_factory=lambda: _env("OPENAI_API_KEY"))
    openai_base_url: str = field(default_factory=lambda: _env("OPENAI_BASE_URL", "https://api.openai.com/v1"))
    ollama_base_url: str = field(default_factory=lambda: _env("OLLAMA_BASE_URL", "http://localhost:11434"))


@dataclass(frozen=True)
class MemorySettings:
    """Agent memory configuration. The engine talks only to our MemoryBackend
    wrapper; the concrete backend (phase 1: mem0) is swappable here."""
    backend: str = field(default_factory=lambda: _env("MEMORY_BACKEND", "fake"))
    # Embedder: local-first by default; cloud optional.
    embedder: str = field(default_factory=lambda: _env("MEMORY_EMBEDDER", "fake"))
    embedder_model: str = field(default_factory=lambda: _env("MEMORY_EMBEDDER_MODEL", ""))
    # Where the backend persists (mem0 / future local hybrid store).
    store_path: str = field(default_factory=lambda: _env("MEMORY_STORE_PATH", "./data/memory"))


@dataclass(frozen=True)
class AuthSettings:
    """Authentication config. The JWT secret signs login tokens (set a strong
    random value in production); the admin seed creates the owner on first run."""
    jwt_secret: str = field(default_factory=lambda: _env("LARIA_JWT_SECRET"))
    token_ttl_seconds: int = field(default_factory=lambda: _env_int("LARIA_TOKEN_TTL_SECONDS", 86400))
    admin_user: str = field(default_factory=lambda: _env("LARIA_ADMIN_USER"))
    admin_password: str = field(default_factory=lambda: _env("LARIA_ADMIN_PASSWORD"))


@dataclass(frozen=True)
class HASettings:
    """Optional Home Assistant integration. Disabled by default, the core
    runs fully without it."""
    enabled: bool = field(default_factory=lambda: _env_bool("HA_ENABLED", False))
    url: str = field(default_factory=lambda: _env("HA_URL", "http://homeassistant.local:8123"))
    token: str = field(default_factory=lambda: _env("HA_TOKEN"))
    mqtt_host: str = field(default_factory=lambda: _env("MQTT_HOST"))
    mqtt_port: int = field(default_factory=lambda: _env_int("MQTT_PORT", 1883))
    mqtt_username: str = field(default_factory=lambda: _env("MQTT_USERNAME"))
    mqtt_password: str = field(default_factory=lambda: _env("MQTT_PASSWORD"))
    # HA's MQTT discovery root (must match HA's config; the standard is
    # "homeassistant"). The node id namespaces LARIA's entities so they never
    # collide with another publisher (e.g. HARIA) on the same broker.
    mqtt_discovery_prefix: str = field(default_factory=lambda: _env("MQTT_DISCOVERY_PREFIX", "homeassistant"))
    mqtt_node_id: str = field(default_factory=lambda: _env("MQTT_NODE_ID", "laria"))


@dataclass(frozen=True)
class Settings:
    data_dir: str = field(default_factory=lambda: _env("LARIA_DATA_DIR", "./data"))
    db_path: str = field(default_factory=lambda: _env("LARIA_DB_PATH", "./data/laria.db"))
    log_level: str = field(default_factory=lambda: _env("LARIA_LOG_LEVEL", "info"))
    telegram_token: str = field(default_factory=lambda: _env("TELEGRAM_TOKEN"))
    # One-time bootstrap: an unlinked Telegram chat that sends "/claim <code>"
    # matching this value is linked to the owner account, so the bot is usable
    # without the web UI. Empty (default) disables claiming.
    telegram_claim_code: str = field(default_factory=lambda: _env("LARIA_TELEGRAM_CLAIM_CODE"))
    web_host: str = field(default_factory=lambda: _env("WEB_HOST", "0.0.0.0"))
    web_port: int = field(default_factory=lambda: _env_int("WEB_PORT", 8080))
    # USDA FoodData Central key for nutrition lookups (DEMO_KEY works, rate-limited).
    usda_api_key: str = field(default_factory=lambda: _env("USDA_API_KEY", "DEMO_KEY"))
    llm: LLMSettings = field(default_factory=LLMSettings)
    memory: MemorySettings = field(default_factory=MemorySettings)
    auth: AuthSettings = field(default_factory=AuthSettings)
    ha: HASettings = field(default_factory=HASettings)


_settings: Settings | None = None


def get_settings() -> Settings:
    """Process-wide settings singleton (read once from the environment)."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """Re-read settings from the environment (mainly for tests)."""
    global _settings
    _settings = Settings()
    return _settings
