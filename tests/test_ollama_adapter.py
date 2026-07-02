"""Testes de regressão para OllamaAdapter.complete().

Cobrem o defeito corrigido na Fase H0 do HARDENING_PLAN.md: a variável
``is_deepseek`` era referenciada sem definição dentro de ``complete()``;
o ``NameError`` resultante — capturado pelo ``except Exception`` genérico
do loop de retry — descartava respostas válidas do Ollama em toda chamada
bem-sucedida, forçando retries até retornar None.

Todos os testes usam ``requests.post`` mockado: nenhuma chamada de rede
real é feita (executáveis offline, sem Ollama).
"""

from unittest import mock

import pytest
import requests

from src.handlers.llm_handler import OllamaAdapter

HOST = "http://localhost:11434/api/generate"


def _mock_response(status_code=200, response_text="FINAL: PURE"):
    """Resposta HTTP simulada no formato da API /api/generate do Ollama."""
    resp = mock.Mock()
    resp.status_code = status_code
    resp.json.return_value = {"response": response_text}
    resp.text = response_text
    return resp


class TestCompleteSuccessPath:
    """Regressão direta do defeito H0: resposta válida deve ser retornada."""

    @mock.patch("src.handlers.llm_handler.requests.post")
    def test_returns_response_on_first_attempt(self, mock_post):
        mock_post.return_value = _mock_response(response_text="FINAL: PURE")
        adapter = OllamaAdapter(HOST, "mistral")

        result = adapter.complete("prompt de teste")

        assert result == "FINAL: PURE"
        # Antes do fix, o NameError forçava esgotar todos os retries.
        assert mock_post.call_count == 1

    @mock.patch("src.handlers.llm_handler.requests.post")
    def test_deepseek_success_tracks_performance(self, mock_post):
        mock_post.return_value = _mock_response(response_text="FINAL: FLOSS")
        adapter = OllamaAdapter(HOST, "deepseek-r1:8b")

        with mock.patch.object(adapter, "_track_deepseek_performance") as track:
            result = adapter.complete("prompt de teste")

        assert result == "FINAL: FLOSS"
        track.assert_called_once()

    @mock.patch("src.handlers.llm_handler.requests.post")
    def test_non_deepseek_does_not_track_performance(self, mock_post):
        mock_post.return_value = _mock_response()
        adapter = OllamaAdapter(HOST, "mistral")

        with mock.patch.object(adapter, "_track_deepseek_performance") as track:
            adapter.complete("prompt de teste")

        track.assert_not_called()


class TestCompleteFailurePaths:
    """Comportamento do loop de retry em falhas de HTTP e timeout."""

    @mock.patch("src.handlers.llm_handler.requests.post")
    def test_deepseek_timeout_triggers_context_reset(self, mock_post):
        mock_post.side_effect = requests.exceptions.Timeout()
        adapter = OllamaAdapter(HOST, "deepseek-r1:8b")

        with mock.patch.object(adapter, "_reset_deepseek_context") as reset:
            result = adapter.complete("prompt de teste", attempts=2)

        assert result is None
        # Reset ocorre apenas quando ainda há tentativas restantes (i < attempts).
        reset.assert_called_once()

    @mock.patch("src.handlers.llm_handler.requests.post")
    def test_non_deepseek_timeout_does_not_reset(self, mock_post):
        mock_post.side_effect = requests.exceptions.Timeout()
        adapter = OllamaAdapter(HOST, "mistral")

        with mock.patch.object(adapter, "_reset_deepseek_context") as reset:
            result = adapter.complete("prompt de teste", attempts=2)

        assert result is None
        reset.assert_not_called()

    @mock.patch("src.handlers.llm_handler.requests.post")
    def test_http_error_exhausts_retries_and_returns_none(self, mock_post):
        mock_post.return_value = _mock_response(status_code=500, response_text="erro")
        adapter = OllamaAdapter(HOST, "mistral")

        result = adapter.complete("prompt de teste", attempts=3)

        assert result is None
        assert mock_post.call_count == 3


class TestDeepseekResetInterval:
    """Reset preventivo configurável (HARDENING_PLAN.md, Fase H8)."""

    def test_reset_fires_at_configured_interval(self, monkeypatch):
        from src.core.settings import settings
        monkeypatch.setattr(settings, "deepseek_reset_interval", 3)
        adapter = OllamaAdapter(HOST, "deepseek-r1:8b")

        with mock.patch.object(adapter, "_reset_deepseek_context") as reset:
            for _ in range(6):
                adapter._track_deepseek_performance(duration=1.0, prompt_size=100)

        # 6 análises com intervalo 3 -> resets nas análises 3 e 6.
        assert reset.call_count == 2


class TestReproducibility:
    """Seed fixo nas options de geração (HARDENING_PLAN.md, Fase H5)."""

    @mock.patch("src.handlers.llm_handler._settings")
    @mock.patch("src.handlers.llm_handler.requests.post")
    def test_fixed_seed_included_in_payload(self, mock_post, mock_settings):
        mock_settings.use_random_seed = False
        mock_settings.llm_seed = 42
        mock_settings.max_retries = 1
        mock_settings.is_deepseek.return_value = False
        mock_settings.context_small = 4096
        mock_settings.temperature = 0.1
        mock_settings.num_predict = 50000
        mock_settings.get_keep_alive.return_value = "5m"
        mock_settings.get_timeout.return_value = 200
        mock_post.return_value = _mock_response()

        OllamaAdapter(HOST, "mistral").complete("prompt de teste")

        payload = mock_post.call_args.kwargs["json"]
        assert payload["options"]["seed"] == 42

    @mock.patch("src.handlers.llm_handler._settings")
    @mock.patch("src.handlers.llm_handler.requests.post")
    def test_random_seed_regime_omits_seed(self, mock_post, mock_settings):
        """use_random_seed=True replica o regime do baseline TCC (sem seed)."""
        mock_settings.use_random_seed = True
        mock_settings.max_retries = 1
        mock_settings.is_deepseek.return_value = False
        mock_settings.context_small = 4096
        mock_settings.temperature = 0.1
        mock_settings.num_predict = 50000
        mock_settings.get_keep_alive.return_value = "5m"
        mock_settings.get_timeout.return_value = 200
        mock_post.return_value = _mock_response()

        OllamaAdapter(HOST, "mistral").complete("prompt de teste")

        payload = mock_post.call_args.kwargs["json"]
        assert "seed" not in payload["options"]


class TestGetModelInfo:
    """Fase E3 (REP-1): identidade exata do modelo via /api/tags + /api/version."""

    def _adapter(self):
        from src.handlers.llm_handler import OllamaAdapter
        return OllamaAdapter("http://localhost:11434/api/generate", "mistral")

    def test_resolves_digest_and_version(self):
        adapter = self._adapter()
        tags = mock.MagicMock(status_code=200)
        tags.json.return_value = {"models": [
            {"name": "mistral:latest", "digest": "sha256:abc", "size": 42,
             "modified_at": "2026-01-01T00:00:00Z"},
        ]}
        tags.raise_for_status.return_value = None
        version = mock.MagicMock(status_code=200)
        version.json.return_value = {"version": "0.9.9"}
        with mock.patch("src.handlers.llm_handler.requests.get", side_effect=[tags, version]):
            info = adapter.get_model_info()
        assert info["digest"] == "sha256:abc"
        assert info["ollama_version"] == "0.9.9"
        # cache: segunda chamada não refaz requests
        with mock.patch("src.handlers.llm_handler.requests.get") as get2:
            assert adapter.get_model_info()["digest"] == "sha256:abc"
            get2.assert_not_called()

    def test_model_absent_returns_none(self):
        adapter = self._adapter()
        tags = mock.MagicMock(status_code=200)
        tags.json.return_value = {"models": [{"name": "gemma:2b", "digest": "sha256:x"}]}
        tags.raise_for_status.return_value = None
        with mock.patch("src.handlers.llm_handler.requests.get", return_value=tags):
            assert adapter.get_model_info() is None

    def test_ollama_down_returns_none(self):
        adapter = self._adapter()
        with mock.patch(
            "src.handlers.llm_handler.requests.get",
            side_effect=ConnectionError("down"),
        ):
            assert adapter.get_model_info() is None
