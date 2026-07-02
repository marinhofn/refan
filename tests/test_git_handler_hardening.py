"""Endurecimento do GitHandler (Fase E4, ROB-4).

Regressões cobertas: colisão de basename entre owners, validação de hash
antes de subprocess, re-clone de diretório corrompido, fetch direcionado
apenas quando hashes faltam (fim do fetch --all incondicional) e limpeza
LRU do cache de clones.
"""

import os
import subprocess
import time
from unittest.mock import MagicMock, patch

import pytest

from src.handlers.git_handler import GitHandler, is_valid_commit_hash


@pytest.fixture
def handler():
    with patch.object(GitHandler, "_ensure_repo_dir_exists"):
        yield GitHandler()


class TestHashValidation:
    @pytest.mark.parametrize("valid", ["abc1234", "a" * 40, "0123456789abcdef"])
    def test_valid_hashes(self, valid):
        assert is_valid_commit_hash(valid) is True

    @pytest.mark.parametrize(
        "invalid",
        ["", None, "abc123", "g" * 10, "--upload-pack=evil", "a" * 41, "abc 1234"],
    )
    def test_invalid_hashes(self, invalid):
        assert is_valid_commit_hash(invalid) is False

    def test_commit_exists_rejects_invalid_without_subprocess(self, handler):
        with patch("src.handlers.git_handler.subprocess.run") as run:
            assert handler.commit_exists("/repo", "--evil-flag") is False
            run.assert_not_called()

    def test_get_commit_diff_rejects_invalid(self, handler):
        with patch("src.handlers.git_handler.subprocess.run") as run:
            assert handler.get_commit_diff("/repo", "ok1234567", "--bad") is None
            run.assert_not_called()


class TestOwnerNamespacedPaths:
    def test_same_basename_different_owners_do_not_collide(self, handler):
        a = handler._get_repo_local_path("https://github.com/apache/log4j")
        b = handler._get_repo_local_path("https://github.com/fork/log4j")
        assert a != b
        assert a.endswith("apache__log4j")
        assert b.endswith("fork__log4j")

    def test_dot_git_and_trailing_slash(self, handler):
        path = handler._get_repo_local_path("https://github.com/owner/repo.git/")
        assert path.endswith("owner__repo")


class TestEnsureRepoCloned:
    def test_corrupted_dir_is_recloned(self, handler, tmp_path, monkeypatch):
        repo_dir = tmp_path / "owner__repo"
        repo_dir.mkdir()
        (repo_dir / "leftover.txt").write_text("clone interrompido")
        monkeypatch.setattr(
            handler, "_get_repo_local_path", lambda url: str(repo_dir)
        )
        monkeypatch.setattr(handler, "_is_valid_repo", lambda p: False)
        clone_calls = []

        def fake_clone(url, path):
            clone_calls.append(path)
            os.makedirs(path, exist_ok=True)
            return True

        monkeypatch.setattr(handler, "_clone", fake_clone)
        ok, path = handler.ensure_repo_cloned("https://github.com/owner/repo")
        assert ok is True
        assert clone_calls == [str(repo_dir)]
        assert not (repo_dir / "leftover.txt").exists()

    def test_existing_repo_without_required_hashes_does_no_fetch(
        self, handler, tmp_path, monkeypatch
    ):
        repo_dir = tmp_path / "owner__repo"
        repo_dir.mkdir()
        monkeypatch.setattr(handler, "_get_repo_local_path", lambda url: str(repo_dir))
        monkeypatch.setattr(handler, "_is_valid_repo", lambda p: True)
        with patch("src.handlers.git_handler.subprocess.run") as run:
            ok, _ = handler.ensure_repo_cloned("https://github.com/owner/repo")
        assert ok is True
        run.assert_not_called()  # fim do fetch --all incondicional

    def test_missing_required_hash_triggers_targeted_fetch(
        self, handler, tmp_path, monkeypatch
    ):
        repo_dir = tmp_path / "owner__repo"
        repo_dir.mkdir()
        monkeypatch.setattr(handler, "_get_repo_local_path", lambda url: str(repo_dir))
        monkeypatch.setattr(handler, "_is_valid_repo", lambda p: True)
        present = {"aaaaaaa1"}
        monkeypatch.setattr(
            handler, "commit_exists", lambda p, h: h in present
        )

        def fake_fetch(path, missing):
            present.update(missing)
            return True

        monkeypatch.setattr(handler, "_fetch_missing", fake_fetch)
        ok, _ = handler.ensure_repo_cloned(
            "https://github.com/owner/repo",
            required_hashes=["aaaaaaa1", "bbbbbbb2"],
        )
        assert ok is True
        assert "bbbbbbb2" in present

    def test_partial_clone_flag_used_first(self, handler, tmp_path, monkeypatch):
        monkeypatch.setattr(
            handler, "_get_repo_local_path", lambda url: str(tmp_path / "o__r")
        )
        with patch("src.handlers.git_handler.subprocess.run") as run:
            run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            handler.ensure_repo_cloned("https://github.com/o/r")
        first_call_args = run.call_args_list[0].args[0]
        assert "--filter=blob:none" in first_call_args
        assert "--" in first_call_args


class TestCleanupRepos:
    def test_lru_removal_respects_budget(self, handler, tmp_path, monkeypatch):
        monkeypatch.setattr("src.handlers.git_handler.REPO_DIR", str(tmp_path))
        old = tmp_path / "old__repo"
        new = tmp_path / "new__repo"
        for d in (old, new):
            d.mkdir()
            (d / "blob.bin").write_bytes(b"x" * 1024)
        past = time.time() - 86400 * 30
        os.utime(old, (past, past))

        report = handler.cleanup_repos(max_gb=1024 / (1024**3), dry_run=False)

        removed_names = [name for name, _ in report["removed"]]
        assert "old__repo" in removed_names
        assert new.exists()

    def test_dry_run_removes_nothing(self, handler, tmp_path, monkeypatch):
        monkeypatch.setattr("src.handlers.git_handler.REPO_DIR", str(tmp_path))
        repo = tmp_path / "a__b"
        repo.mkdir()
        (repo / "f").write_bytes(b"x" * 2048)

        report = handler.cleanup_repos(max_gb=0.0, dry_run=True)

        assert repo.exists()
        assert len(report["removed"]) == 1

    def test_under_budget_removes_nothing(self, handler, tmp_path, monkeypatch):
        monkeypatch.setattr("src.handlers.git_handler.REPO_DIR", str(tmp_path))
        (tmp_path / "a__b").mkdir()
        report = handler.cleanup_repos(max_gb=10.0)
        assert report["removed"] == []
