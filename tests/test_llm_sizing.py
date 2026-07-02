"""Planejamento de contexto e fim do truncamento silencioso (Fase E2, VAL-7).

Regressões cobertas:
- num_ctx era dimensionado só pelo diff (ignorando template+contexto) e,
  para DeepSeek, o valor calculado era descartado e forçado a 4096;
- num_predict=50000 disputava a janela com o input;
- um prompt maior que o teto era enviado assim mesmo e o Ollama descartava
  o excedente sem registro — o modelo classificava sem ver o diff inteiro.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.core.settings import settings
from src.handlers.llm_handler import LLMHandler, OllamaAdapter
from src.utils.llm_sizing import (
    GenerationPlan,
    context_ceiling_for,
    estimate_token_count,
    plan_generation,
)


class TestEstimateTokenCount:
    def test_empty(self):
        assert estimate_token_count("") == 0

    def test_scaling(self):
        assert estimate_token_count("x" * 400) == 100
        assert estimate_token_count("ab") == 1  # mínimo 1 para texto não vazio


class TestContextCeiling:
    def test_default_model(self):
        assert context_ceiling_for("mistral") == settings.context_ceiling

    def test_deepseek_has_own_ceiling(self):
        assert context_ceiling_for("deepseek-r1:8b") == settings.context_ceiling_deepseek

    def test_empty_model_uses_default(self):
        assert context_ceiling_for("") == settings.context_ceiling


class TestPlanGeneration:
    def test_small_prompt_fits_with_minimum_context(self):
        plan = plan_generation("short prompt", "mistral")
        assert plan.fits is True
        assert plan.num_ctx == settings.context_small
        assert plan.num_predict == settings.max_output_tokens

    def test_medium_prompt_scales_context(self):
        # ~16k chars -> ~4k tokens * 1.25 + 2048 = ~7048 -> arredonda p/ cima
        plan = plan_generation("x" * 16000, "mistral")
        assert plan.fits is True
        assert settings.context_small < plan.num_ctx <= settings.context_ceiling
        assert plan.num_ctx % 512 == 0

    def test_oversized_prompt_does_not_fit(self):
        """Regressão VAL-7: 60k chars (~15k tokens) NÃO cabem em 8192 — o
        plano precisa dizê-lo em vez de deixar o Ollama truncar em silêncio."""
        plan = plan_generation("x" * 60000, "mistral")
        assert plan.fits is False
        assert plan.num_ctx == settings.context_ceiling
        assert 0 < plan.max_prompt_chars < 60000

    def test_reduced_to_budget_fits(self):
        oversized = plan_generation("x" * 60000, "mistral")
        replanned = plan_generation("x" * oversized.max_prompt_chars, "mistral")
        assert replanned.fits is True

    def test_deepseek_ceiling_respected(self):
        plan = plan_generation("x" * 16000, "deepseek-r1:8b")
        assert plan.num_ctx <= settings.context_ceiling_deepseek
        assert plan.fits is False  # 16k chars não cabem no teto DeepSeek


class TestAdapterHonorsPlan:
    """O OllamaAdapter respeita o plano; teto DeepSeek é limite, não override."""

    def _capture_payload(self, adapter, **kwargs):
        with patch("src.handlers.llm_handler.requests.post") as post:
            post.return_value = MagicMock(
                status_code=200, json=lambda: {"response": "FINAL: PURE"}
            )
            adapter.complete("prompt", attempts=1, **kwargs)
            return post.call_args.kwargs["json"]

    def test_num_ctx_and_num_predict_forwarded(self):
        adapter = OllamaAdapter("http://host/api/generate", "mistral")
        payload = self._capture_payload(adapter, num_ctx=6144, num_predict=2048)
        assert payload["options"]["num_ctx"] == 6144
        assert payload["options"]["num_predict"] == 2048

    def test_deepseek_ceiling_is_upper_bound_not_override(self):
        adapter = OllamaAdapter("http://host/api/generate", "deepseek-r1:8b")
        # abaixo do teto: valor do plano é respeitado (antes: sempre 4096)
        payload = self._capture_payload(adapter, num_ctx=3072)
        assert payload["options"]["num_ctx"] == 3072
        # acima do teto: limitado
        payload = self._capture_payload(adapter, num_ctx=8192)
        assert payload["options"]["num_ctx"] == settings.context_ceiling_deepseek


class TestAnalyzeCommitTruncationTrace:
    """analyze_commit reduz o diff para caber e REGISTRA o corte (VAL-7)."""

    @pytest.fixture
    def handler(self, tmp_path, monkeypatch):
        h = LLMHandler(model="mistral")
        h.failures_file = str(tmp_path / "failures.jsonl")
        monkeypatch.setattr(
            "src.handlers.llm_handler.check_llm_model_status",
            lambda *a, **k: {"available": True},
        )
        h.adapter = MagicMock()
        h.adapter.complete.return_value = (
            'FINAL: FLOSS\n{"refactoring_type": "floss", "justification": "big change"}'
        )
        return h

    def test_oversized_diff_is_reduced_and_flagged(self, handler):
        huge_diff = "diff --git a/f b/f\n" + ("+line of code\n" * 30000)  # ~420k chars
        result = handler.analyze_commit(
            repository="repo", commit1="a", commit2="b",
            commit_message="msg", diff=huge_diff,
        )
        assert result is not None
        assert result["diff_truncated"] is True
        assert result["original_diff_size_chars"] == len(huge_diff)
        assert result["diff_size_chars"] < len(huge_diff)
        assert 0 < result["num_ctx_effective"] <= settings.context_ceiling
        assert result["num_predict_effective"] == settings.max_output_tokens
        # o prompt efetivamente enviado coube no plano
        sent_prompt = handler.adapter.complete.call_args.args[0]
        assert result["prompt_chars"] == len(sent_prompt)
        plan_check = plan_generation(sent_prompt, "mistral")
        assert plan_check.fits is True

    def test_small_diff_not_flagged(self, handler):
        small_diff = "diff --git a/f b/f\n+one line\n"
        result = handler.analyze_commit(
            repository="repo", commit1="a", commit2="b",
            commit_message="msg", diff=small_diff,
        )
        assert result["diff_truncated"] is False
        assert result["original_diff_size_chars"] == len(small_diff)
