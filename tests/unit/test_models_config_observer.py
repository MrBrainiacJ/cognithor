"""Tests for ModelsConfig.observer slot."""

from __future__ import annotations

from cognithor.config import JarvisConfig, ModelsConfig
from cognithor.models import ModelConfig


class TestModelsConfigObserver:
    def test_observer_default_is_qwen3_32b(self):
        cfg = ModelsConfig()
        assert isinstance(cfg.observer, ModelConfig)
        assert cfg.observer.name == "qwen3:32b"

    def test_observer_overrideable(self):
        cfg = ModelsConfig(observer=ModelConfig(name="qwen3:8b"))
        assert cfg.observer.name == "qwen3:8b"

    def test_observer_in_default_ollama_names_mapping(self):
        from cognithor.config import _OLLAMA_DEFAULT_MODEL_NAMES
        assert "observer" in _OLLAMA_DEFAULT_MODEL_NAMES
        assert _OLLAMA_DEFAULT_MODEL_NAMES["observer"] == "qwen3:32b"

    def test_available_via_jarvis_config(self):
        cfg = JarvisConfig()
        assert cfg.models.observer.name == "qwen3:32b"
