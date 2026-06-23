import laria.config as config


def test_defaults(monkeypatch):
    for k in ("LLM_PROVIDER", "LLM_MODEL", "HA_ENABLED", "LARIA_DB_PATH"):
        monkeypatch.delenv(k, raising=False)
    s = config.reload_settings()
    assert s.llm.provider == "anthropic"
    assert s.llm.model == "claude-opus-4-8"
    assert s.ha.enabled is False
    assert s.db_path.endswith("laria.db")


def test_env_override(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("LLM_MAX_TOKENS", "2048")
    monkeypatch.setenv("HA_ENABLED", "true")
    monkeypatch.setenv("MQTT_PORT", "8883")
    s = config.reload_settings()
    assert s.llm.provider == "ollama"
    assert s.llm.max_tokens == 2048
    assert s.ha.enabled is True
    assert s.ha.mqtt_port == 8883
