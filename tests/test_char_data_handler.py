"""Testes de caracterização para src/handlers/data_handler.py.

Foca no carregamento de commits analisados e no suporte a ambos os
formatos de campo (commit2 vs commit_hash_current).

Refs: REFACTORING_PLAN.md Fase 0.3
"""

import json
import sys

import pytest
from unittest.mock import patch

if sys.version_info < (3, 10):
    pytest.skip(
        "Código de produção usa sintaxe str | None (requer Python >= 3.10)",
        allow_module_level=True,
    )


class TestLoadAnalyzedCommits:
    """Testa _load_analyzed_commits com ambos os formatos de campo."""

    def test_loads_commit2_format(self, tmp_path):
        """Formato legado usando 'commit2' como chave."""
        log_file = tmp_path / "analyzed_commits.json"
        log_file.write_text(json.dumps([
            {"commit2": "aaa111", "project": "repo-a"},
            {"commit2": "bbb222", "project": "repo-b"},
        ]))

        with patch("src.handlers.data_handler.get_model_paths") as mock_paths, \
             patch("src.handlers.data_handler.get_current_llm_model", return_value="test"), \
             patch("src.handlers.data_handler.CSV_PATH", str(tmp_path / "nonexistent.csv")):
            mock_paths.return_value = {"ANALYZED_COMMITS_LOG": str(log_file)}

            from src.handlers.data_handler import DataHandler
            handler = DataHandler()

            assert "aaa111" in handler.analyzed_commits
            assert "bbb222" in handler.analyzed_commits
            assert len(handler.analyzed_commits) == 2

    def test_loads_commit_hash_current_format(self, tmp_path):
        """Formato novo usando 'commit_hash_current' como chave."""
        log_file = tmp_path / "analyzed_commits.json"
        log_file.write_text(json.dumps([
            {"commit_hash_current": "ccc333"},
            {"commit_hash_current": "ddd444"},
        ]))

        with patch("src.handlers.data_handler.get_model_paths") as mock_paths, \
             patch("src.handlers.data_handler.get_current_llm_model", return_value="test"), \
             patch("src.handlers.data_handler.CSV_PATH", str(tmp_path / "nonexistent.csv")):
            mock_paths.return_value = {"ANALYZED_COMMITS_LOG": str(log_file)}

            from src.handlers.data_handler import DataHandler
            handler = DataHandler()

            assert "ccc333" in handler.analyzed_commits
            assert "ddd444" in handler.analyzed_commits

    def test_returns_empty_set_when_file_missing(self, tmp_path):
        """Retorna set vazio quando o arquivo não existe."""
        with patch("src.handlers.data_handler.get_model_paths") as mock_paths, \
             patch("src.handlers.data_handler.get_current_llm_model", return_value="test"), \
             patch("src.handlers.data_handler.CSV_PATH", str(tmp_path / "nonexistent.csv")):
            mock_paths.return_value = {
                "ANALYZED_COMMITS_LOG": str(tmp_path / "nonexistent.json")
            }

            from src.handlers.data_handler import DataHandler
            handler = DataHandler()

            assert handler.analyzed_commits == set()

    def test_handles_mixed_formats(self, tmp_path):
        """Lida com registros que misturam os dois formatos."""
        log_file = tmp_path / "analyzed_commits.json"
        log_file.write_text(json.dumps([
            {"commit2": "aaa111"},
            {"commit_hash_current": "bbb222"},
            {"commit2": "ccc333", "commit_hash_current": "ccc333"},
        ]))

        with patch("src.handlers.data_handler.get_model_paths") as mock_paths, \
             patch("src.handlers.data_handler.get_current_llm_model", return_value="test"), \
             patch("src.handlers.data_handler.CSV_PATH", str(tmp_path / "nonexistent.csv")):
            mock_paths.return_value = {"ANALYZED_COMMITS_LOG": str(log_file)}

            from src.handlers.data_handler import DataHandler
            handler = DataHandler()

            assert "aaa111" in handler.analyzed_commits
            assert "bbb222" in handler.analyzed_commits
            assert "ccc333" in handler.analyzed_commits
