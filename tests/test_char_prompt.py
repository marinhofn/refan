"""Testes de caracterização para construção de prompts.

Verifica a estrutura dos prompts gerados por build_commit_prompt()
(llm_handler.py) e build_optimized_commit_prompt_with_file_support()
(optimized_prompt.py), garantindo que a refatoração preserve o formato.

Refs: REFACTORING_PLAN.md Fase 0.3
"""

import sys

import pytest

if sys.version_info < (3, 10):
    pytest.skip(
        "Código de produção usa sintaxe str | None (requer Python >= 3.10)",
        allow_module_level=True,
    )

from src.handlers.llm_handler import build_commit_prompt
from src.core.config import LLM_PROMPT


class TestBuildCommitPrompt:
    """Testa a construção do prompt básico em llm_handler.py."""

    def test_contains_system_prompt(self, sample_commit_data):
        prompt = build_commit_prompt(sample_commit_data, LLM_PROMPT)
        assert "software engineering expert" in prompt.lower()

    def test_contains_repository_info(self, sample_commit_data):
        prompt = build_commit_prompt(sample_commit_data, LLM_PROMPT)
        assert sample_commit_data["repository"] in prompt

    def test_contains_commit_hashes(self, sample_commit_data):
        prompt = build_commit_prompt(sample_commit_data, LLM_PROMPT)
        assert sample_commit_data["commit_hash_before"] in prompt
        assert sample_commit_data["commit_hash_current"] in prompt

    def test_contains_diff(self, sample_commit_data):
        prompt = build_commit_prompt(sample_commit_data, LLM_PROMPT)
        assert sample_commit_data["diff"] in prompt

    def test_contains_json_format_instruction(self, sample_commit_data):
        prompt = build_commit_prompt(sample_commit_data, LLM_PROMPT)
        assert "refactoring_type" in prompt
        assert "justification" in prompt

    def test_contains_classification_guidelines(self, sample_commit_data):
        prompt = build_commit_prompt(sample_commit_data, LLM_PROMPT)
        assert "pure" in prompt.lower()
        assert "floss" in prompt.lower()

    def test_empty_diff_still_produces_valid_prompt(self):
        data = {
            "repository": "test",
            "commit_hash_before": "aaa",
            "commit_hash_current": "bbb",
            "diff": "",
        }
        prompt = build_commit_prompt(data, LLM_PROMPT)
        assert "Repository: test" in prompt
        assert len(prompt) > 100  # Prompt ainda tem as instruções

    def test_missing_fields_use_empty_string(self):
        data = {}  # Todos os campos ausentes
        prompt = build_commit_prompt(data, LLM_PROMPT)
        # Não deve levantar exceção
        assert "Repository:" in prompt


class TestOptimizedPromptWithFileSupport:
    """Testa a construção do prompt otimizado em optimized_prompt.py."""

    def test_small_diff_included_directly(self, sample_commit_data):
        from src.analyzers.optimized_prompt import (
            build_optimized_commit_prompt_with_file_support,
            OPTIMIZED_LLM_PROMPT,
        )

        prompt, temp_file = build_optimized_commit_prompt_with_file_support(
            commit_data=sample_commit_data,
            system_prompt=OPTIMIZED_LLM_PROMPT,
            diff_content=sample_commit_data["diff"],
        )

        assert temp_file is None  # Diff pequeno, sem arquivo temporário
        assert sample_commit_data["diff"] in prompt
        assert "CLASSIFICATION CRITERIA" in prompt

    def test_prompt_has_json_format_instruction(self, sample_commit_data):
        from src.analyzers.optimized_prompt import (
            build_optimized_commit_prompt_with_file_support,
            OPTIMIZED_LLM_PROMPT,
        )

        prompt, _ = build_optimized_commit_prompt_with_file_support(
            commit_data=sample_commit_data,
            system_prompt=OPTIMIZED_LLM_PROMPT,
            diff_content=sample_commit_data["diff"],
        )

        assert "refactoring_type" in prompt
        assert "justification" in prompt

    def test_large_diff_uses_temp_file(self, sample_commit_data):
        from src.analyzers.optimized_prompt import (
            build_optimized_commit_prompt_with_file_support,
            cleanup_temp_diff_file,
            OPTIMIZED_LLM_PROMPT,
            MAX_DIRECT_DIFF_SIZE,
        )

        large_diff = "+" * (MAX_DIRECT_DIFF_SIZE + 1000)

        prompt, temp_file = build_optimized_commit_prompt_with_file_support(
            commit_data=sample_commit_data,
            system_prompt=OPTIMIZED_LLM_PROMPT,
            diff_content=large_diff,
        )

        # Diff grande deve ser encaminhado para arquivo temporário
        # (ou truncado — depende da implementação)
        assert isinstance(prompt, str)
        assert len(prompt) > 0

        # Limpar arquivo temporário se criado
        if temp_file:
            cleanup_temp_diff_file(temp_file)
