from __future__ import annotations

from cognithor.config import load_config


class TestEnvOverrides:
    """Verify that COGNITHOR_* and legacy JARVIS_* env vars override config."""

    def test_language_override(self, monkeypatch, tmp_path):
        monkeypatch.setenv("COGNITHOR_LANGUAGE", "en")
        cfg = load_config(tmp_path / "empty.yaml")
        assert cfg.language == "en"

    def test_ollama_base_url(self, monkeypatch, tmp_path):
        monkeypatch.setenv("COGNITHOR_OLLAMA_BASE_URL", "http://remote:11434")
        cfg = load_config(tmp_path / "empty.yaml")
        assert cfg.ollama.base_url == "http://remote:11434"

    def test_ollama_timeout(self, monkeypatch, tmp_path):
        monkeypatch.setenv("COGNITHOR_OLLAMA_TIMEOUT_SECONDS", "600")
        cfg = load_config(tmp_path / "empty.yaml")
        assert cfg.ollama.timeout_seconds == 600

    def test_planner_max_iterations(self, monkeypatch, tmp_path):
        monkeypatch.setenv("COGNITHOR_PLANNER_MAX_ITERATIONS", "50")
        cfg = load_config(tmp_path / "empty.yaml")
        assert cfg.planner.max_iterations == 50

    def test_models_planner_name(self, monkeypatch, tmp_path):
        monkeypatch.setenv("COGNITHOR_MODELS_PLANNER", "llama3:70b")
        cfg = load_config(tmp_path / "empty.yaml")
        assert cfg.models.planner.name == "llama3:70b"

    def test_llm_backend_type(self, monkeypatch, tmp_path):
        monkeypatch.setenv("COGNITHOR_LLM_BACKEND_TYPE", "anthropic")
        cfg = load_config(tmp_path / "empty.yaml")
        assert cfg.llm_backend_type == "anthropic"

    def test_owner_name(self, monkeypatch, tmp_path):
        monkeypatch.setenv("COGNITHOR_OWNER_NAME", "TestUser")
        cfg = load_config(tmp_path / "empty.yaml")
        assert cfg.owner_name == "TestUser"

    def test_env_overrides_yaml(self, monkeypatch, tmp_path):
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("language: de\n", encoding="utf-8")
        monkeypatch.setenv("COGNITHOR_LANGUAGE", "zh")
        cfg = load_config(yaml_file)
        assert cfg.language == "zh"

    def test_bool_override_false(self, monkeypatch, tmp_path):
        monkeypatch.setenv("COGNITHOR_CHANNELS_CLI_ENABLED", "false")
        cfg = load_config(tmp_path / "empty.yaml")
        assert cfg.channels.cli_enabled is False

    def test_legacy_jarvis_prefix(self, monkeypatch, tmp_path):
        monkeypatch.setenv("JARVIS_LANGUAGE", "en")
        cfg = load_config(tmp_path / "empty.yaml")
        assert cfg.language == "en"

    def test_cognithor_prefix_wins_over_jarvis(self, monkeypatch, tmp_path):
        monkeypatch.setenv("JARVIS_LANGUAGE", "en")
        monkeypatch.setenv("COGNITHOR_LANGUAGE", "zh")
        cfg = load_config(tmp_path / "empty.yaml")
        assert cfg.language == "zh"


class TestBackendAutoDetection:
    """Verify that explicit llm_backend_type is respected (#105)."""

    def test_explicit_ollama_not_overridden_by_api_key(self, tmp_path):
        """User sets llm_backend_type: ollama + has openai_api_key → stays ollama."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(
            "llm_backend_type: ollama\nopenai_api_key: sk-test-key\n",
            encoding="utf-8",
        )
        cfg = load_config(yaml_file)
        assert cfg.llm_backend_type == "ollama"

    def test_explicit_ollama_not_overridden_by_anthropic_key(self, tmp_path):
        """User sets llm_backend_type: ollama + has anthropic_api_key → stays ollama."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(
            "llm_backend_type: ollama\nanthropic_api_key: sk-ant-test\n",
            encoding="utf-8",
        )
        cfg = load_config(yaml_file)
        assert cfg.llm_backend_type == "ollama"

    def test_default_ollama_auto_detects_openai(self, tmp_path):
        """No explicit backend + openai_api_key → auto-detects to openai."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(
            "openai_api_key: sk-test-key\n",
            encoding="utf-8",
        )
        cfg = load_config(yaml_file)
        assert cfg.llm_backend_type == "openai"

    def test_default_ollama_auto_detects_anthropic(self, tmp_path):
        """No explicit backend + anthropic_api_key → auto-detects to anthropic."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(
            "anthropic_api_key: sk-ant-test\n",
            encoding="utf-8",
        )
        cfg = load_config(yaml_file)
        assert cfg.llm_backend_type == "anthropic"

    def test_explicit_ollama_via_env_not_overridden(self, monkeypatch, tmp_path):
        """Backend set via env var is also considered explicit."""
        monkeypatch.setenv("COGNITHOR_LLM_BACKEND_TYPE", "ollama")
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(
            "openai_api_key: sk-test-key\n",
            encoding="utf-8",
        )
        cfg = load_config(yaml_file)
        assert cfg.llm_backend_type == "ollama"

    def test_no_api_keys_stays_ollama(self, tmp_path):
        """No API keys, no explicit backend → stays ollama (default)."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("language: de\n", encoding="utf-8")
        cfg = load_config(yaml_file)
        assert cfg.llm_backend_type == "ollama"

    def test_explicit_openai_backend_respected(self, tmp_path):
        """User explicitly sets llm_backend_type: openai → stays openai."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(
            "llm_backend_type: openai\nopenai_api_key: sk-test-key-long-enough\n",
            encoding="utf-8",
        )
        cfg = load_config(yaml_file)
        assert cfg.llm_backend_type == "openai"
