"""Fixtures compartilhadas para todos os testes do Refan."""

import sys
from pathlib import Path

import pytest
import pandas as pd

# Garantir que src/ é importável independente de como pytest é invocado
sys.path.insert(0, str(Path(__file__).parent.parent))

# O código de produção usa sintaxe `str | None` (PEP 604, Python 3.10+).
# Em Python 3.9, importar qualquer módulo que passe por config.py falha.
requires_py310 = pytest.mark.skipif(
    sys.version_info < (3, 10),
    reason="Código de produção usa sintaxe str | None (requer Python >= 3.10)",
)


@pytest.fixture
def sample_commit_data():
    """Dict padrão de commit para testes unitários."""
    return {
        "repository": "https://github.com/test/repo",
        "commit_hash_before": "abc123def456",
        "commit_hash_current": "789ghi012jkl",
        "commit_message": "Refactor: extract method",
        "diff": (
            "diff --git a/Foo.java b/Foo.java\n"
            "--- a/Foo.java\n"
            "+++ b/Foo.java\n"
            "@@ -1,5 +1,5 @@\n"
            " public class Foo {\n"
            "-    public void oldMethod() {\n"
            "+    public void newMethod() {\n"
            "         return;\n"
            "     }\n"
            " }"
        ),
        "project_name": "repo",
    }


@pytest.fixture
def sample_csv_dataframe():
    """DataFrame pequeno simulando commits_with_refactoring.csv."""
    return pd.DataFrame({
        "commit1": ["aaa111", "bbb222", "ccc333"],
        "commit2": ["ddd444", "eee555", "fff666"],
        "project": [
            "https://github.com/a/repo-a",
            "https://github.com/b/repo-b",
            "https://github.com/c/repo-c",
        ],
        "project_name": ["repo-a", "repo-b", "repo-c"],
    })


@pytest.fixture
def mock_ollama_response_factory():
    """Factory para respostas LLM previsíveis em formato JSON."""
    def _make(
        refactoring_type="floss",
        justification="Test justification",
        repository="test-repo",
    ):
        return (
            f'{{"repository": "{repository}",'
            f' "commit_hash_before": "abc123",'
            f' "commit_hash_current": "def456",'
            f' "refactoring_type": "{refactoring_type}",'
            f' "justification": "{justification}"}}'
        )
    return _make


@pytest.fixture
def tmp_output_dir(tmp_path):
    """Diretório temporário simulando output/models/<model>/analises/."""
    out = tmp_path / "output" / "models" / "test-model" / "analises"
    out.mkdir(parents=True)
    return out
