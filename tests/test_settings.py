"""Testes unitários para RefanSettings (src/core/settings.py).

Primeira cobertura do módulo de configuração centralizada (Fase H4 do
HARDENING_PLAN.md). Valida defaults documentados, helpers de modelo,
limiares de timeout e a exclusão de segredos do snapshot serializado.
"""

import sys

import pytest

if sys.version_info < (3, 10):
    pytest.skip(
        "Código de produção usa sintaxe str | None (requer Python >= 3.10)",
        allow_module_level=True,
    )

from src.core.settings import RefanSettings


@pytest.fixture
def clean_settings(monkeypatch):
    """RefanSettings sem interferência de variáveis de ambiente."""
    for var in ("REFAN_LLM_MODEL", "SUPABASE_URL", "SUPABASE_SERVICE_KEY",
                "REFAN_RUNNER_ID", "REFAN_PROMPT_VERSION"):
        monkeypatch.delenv(var, raising=False)
    return RefanSettings()


class TestDefaults:
    """Defaults documentados na docstring do módulo (Fase 2)."""

    def test_generation_defaults(self, clean_settings):
        assert clean_settings.temperature == 0.1
        assert clean_settings.num_predict == 50000
        assert clean_settings.keep_alive == "5m"
        assert clean_settings.keep_alive_deepseek == "30s"

    def test_retry_and_timeout_defaults(self, clean_settings):
        assert clean_settings.max_retries == 2
        assert clean_settings.timeout_base_s == 200
        assert clean_settings.timeout_large_s == 300

    def test_diff_thresholds(self, clean_settings):
        assert clean_settings.max_diff_chars == 60000
        assert clean_settings.max_diff_chars_file == 100000

    def test_default_model_without_env(self, clean_settings):
        assert clean_settings.llm_model == "mistral"

    def test_model_overridden_by_env(self, monkeypatch):
        monkeypatch.setenv("REFAN_LLM_MODEL", "gemma2:2b")
        assert RefanSettings().llm_model == "gemma2:2b"


class TestModelHelpers:
    @pytest.mark.parametrize("model,expected", [
        ("deepseek-r1:8b", True),
        ("deepseek-r1:1.5b", True),
        ("DeepSeek-R1:8B", True),   # case-insensitive
        ("mistral", False),
        ("gemma2:2b", False),
    ])
    def test_is_deepseek(self, clean_settings, model, expected):
        assert clean_settings.is_deepseek(model) is expected

    def test_is_deepseek_uses_current_model_when_omitted(self, clean_settings):
        clean_settings.llm_model = "deepseek-r1:8b"
        assert clean_settings.is_deepseek() is True

    def test_keep_alive_for_deepseek(self, clean_settings):
        assert clean_settings.get_keep_alive("deepseek-r1:8b") == "30s"

    def test_keep_alive_for_other_models(self, clean_settings):
        assert clean_settings.get_keep_alive("mistral") == "5m"


class TestTimeout:
    def test_small_prompt_uses_base_timeout(self, clean_settings):
        assert clean_settings.get_timeout(50000) == clean_settings.timeout_base_s

    def test_large_prompt_uses_large_timeout(self, clean_settings):
        assert clean_settings.get_timeout(50001) == clean_settings.timeout_large_s

    def test_default_prompt_size_uses_base(self, clean_settings):
        assert clean_settings.get_timeout() == clean_settings.timeout_base_s


class TestSupabaseConfig:
    def test_disabled_without_credentials(self, clean_settings):
        assert clean_settings.supabase_enabled is False

    def test_disabled_with_partial_credentials(self, clean_settings):
        clean_settings.supabase_url = "https://x.supabase.co"
        assert clean_settings.supabase_enabled is False

    def test_enabled_with_full_credentials(self, clean_settings):
        clean_settings.supabase_url = "https://x.supabase.co"
        clean_settings.supabase_service_key = "service-key"
        assert clean_settings.supabase_enabled is True


class TestToDict:
    """O snapshot serializado alimenta config_snapshot das sessões."""

    def test_excludes_service_key(self, clean_settings):
        clean_settings.supabase_service_key = "segredo"
        snapshot = clean_settings.to_dict()
        assert "supabase_service_key" not in snapshot

    def test_includes_reproducibility_fields(self, clean_settings):
        snapshot = clean_settings.to_dict()
        assert snapshot["temperature"] == 0.1
        assert snapshot["llm_model"] == "mistral"
        assert "max_retries" in snapshot
        assert "prompt_version_tag" in snapshot
