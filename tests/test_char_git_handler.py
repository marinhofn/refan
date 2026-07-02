"""Testes de caracterização para src/handlers/git_handler.py.

Usa mocks de subprocess para evitar dependência de repos reais.
Documenta o comportamento atual (incluindo o uso de os.chdir) que
será corrigido na Fase 4.

Refs: REFACTORING_PLAN.md Fase 0.3
"""

import subprocess
import sys
from unittest.mock import patch, MagicMock

import pytest

if sys.version_info < (3, 10):
    pytest.skip(
        "Código de produção usa sintaxe str | None (requer Python >= 3.10)",
        allow_module_level=True,
    )

from src.handlers.git_handler import GitHandler


@pytest.fixture
def git_handler(tmp_path):
    """GitHandler com REPO_DIR apontando para diretório temporário."""
    with patch("src.handlers.git_handler.REPO_DIR", str(tmp_path / "repos")):
        handler = GitHandler()
        yield handler


class TestGetRepoLocalPath:
    def test_extracts_repo_name_from_url(self, git_handler):
        path = git_handler._get_repo_local_path("https://github.com/owner/my-repo")
        assert path.endswith("my-repo")

    def test_strips_dot_git_suffix(self, git_handler):
        path = git_handler._get_repo_local_path("https://github.com/owner/my-repo.git")
        assert path.endswith("my-repo")
        assert not path.endswith(".git")

    def test_handles_trailing_slash(self, git_handler):
        path = git_handler._get_repo_local_path("https://github.com/owner/my-repo/")
        assert path.endswith("my-repo")


class TestEnsureRepoCloned:
    def test_clones_when_not_exists(self, git_handler, tmp_path):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=b"", stderr=b"")
            success, path = git_handler.ensure_repo_cloned("https://github.com/test/repo")

            assert success is True
            assert "repo" in path
            # Verifica que git clone foi chamado
            clone_call = mock_run.call_args_list[0]
            assert "clone" in clone_call[0][0]

    def test_fetches_when_exists(self, git_handler, tmp_path):
        # Criar o diretório do repo para simular que já existe
        with patch("src.handlers.git_handler.REPO_DIR", str(tmp_path / "repos")):
            repo_path = tmp_path / "repos" / "repo"
            repo_path.mkdir(parents=True)

            with patch("subprocess.run") as mock_run, \
                 patch("os.chdir"):  # mock os.chdir para não mudar de dir
                mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
                handler = GitHandler()
                success, path = handler.ensure_repo_cloned("https://github.com/test/repo")

                assert success is True

    def test_returns_false_on_clone_failure(self, git_handler):
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                128, "git clone", stderr="fatal: repo not found"
            )
            success, msg = git_handler.ensure_repo_cloned("https://github.com/test/nonexistent")
            assert success is False


class TestGetCommitDiff:
    def test_returns_diff_content(self, git_handler, tmp_path):
        repo_path = str(tmp_path / "repo")
        diff_content = b"diff --git a/file.txt b/file.txt\n-old\n+new"

        with patch("subprocess.run") as mock_run, \
             patch("os.chdir"):
            mock_run.return_value = MagicMock(
                returncode=0, stdout=diff_content, stderr=b""
            )
            result = git_handler.get_commit_diff(repo_path, "abc1234", "def4567")

            assert result is not None
            assert "diff --git" in result

    def test_returns_none_on_error(self, git_handler, tmp_path):
        repo_path = str(tmp_path / "repo")

        with patch("subprocess.run") as mock_run, \
             patch("os.chdir"):
            mock_run.side_effect = subprocess.CalledProcessError(
                128, "git diff", stderr=b"fatal: bad revision"
            )
            result = git_handler.get_commit_diff(repo_path, "bad1", "bad2")
            assert result is None


class TestGetCommitMessage:
    def test_returns_commit_message(self, git_handler, tmp_path):
        repo_path = str(tmp_path / "repo")

        with patch("subprocess.run") as mock_run, \
             patch("os.chdir"):
            mock_run.return_value = MagicMock(
                returncode=0, stdout="Refactor: extract method\n", stderr=""
            )
            result = git_handler.get_commit_message(repo_path, "abc1234")
            assert result == "Refactor: extract method"

    def test_returns_none_on_error(self, git_handler, tmp_path):
        repo_path = str(tmp_path / "repo")

        with patch("subprocess.run") as mock_run, \
             patch("os.chdir"):
            mock_run.side_effect = subprocess.CalledProcessError(
                128, "git log", stderr="fatal: bad object"
            )
            result = git_handler.get_commit_message(repo_path, "bad123")
            assert result is None


class TestCommitExists:
    def test_returns_true_when_exists(self, git_handler, tmp_path):
        repo_path = str(tmp_path / "repo")

        with patch("subprocess.run") as mock_run, \
             patch("os.chdir"):
            mock_run.return_value = MagicMock(returncode=0)
            assert git_handler.commit_exists(repo_path, "abc1234") is True

    def test_returns_false_when_not_exists(self, git_handler, tmp_path):
        repo_path = str(tmp_path / "repo")

        with patch("subprocess.run") as mock_run, \
             patch("os.chdir"):
            mock_run.return_value = MagicMock(returncode=1)
            assert git_handler.commit_exists(repo_path, "nonexistent") is False
