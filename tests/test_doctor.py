"""refan doctor (Fase E3) — checks de prontidão, todos offline/mockados."""

from unittest import mock

import pytest

from src.core import doctor
from src.core.doctor import (
    CheckResult,
    check_model_digest,
    check_ollama_up,
    check_prompt_artifact,
    run_doctor,
)


class TestCheckOllama:
    def test_up(self):
        resp = mock.MagicMock(status_code=200)
        resp.json.return_value = {"version": "0.9.9"}
        resp.raise_for_status.return_value = None
        with mock.patch("src.core.doctor.requests.get", return_value=resp):
            result = check_ollama_up()
        assert result.status == "OK"
        assert "0.9.9" in result.detail

    def test_down(self):
        with mock.patch(
            "src.core.doctor.requests.get", side_effect=ConnectionError("x")
        ):
            result = check_ollama_up()
        assert result.status == "FAIL"
        assert result.is_failure


class TestCheckModelDigest:
    def test_ok_with_digest(self):
        info = {"model": "mistral:latest", "digest": "sha256:abcdef1234567890abc"}
        with mock.patch(
            "src.handlers.llm_handler.OllamaAdapter.get_model_info",
            return_value=info,
        ):
            result = check_model_digest("mistral")
        assert result.status == "OK"
        assert "sha256:" in result.detail

    def test_fail_without_digest(self):
        with mock.patch(
            "src.handlers.llm_handler.OllamaAdapter.get_model_info",
            return_value=None,
        ):
            result = check_model_digest("mistral")
        assert result.status == "FAIL"
        assert "ollama pull" in result.detail


class TestCheckPromptArtifact:
    def test_active_tag_matches_executing_prompt(self):
        # tag default v2.0-mestrado: o artefato É a fonte da constante
        result = check_prompt_artifact()
        assert result.status == "OK"

    def test_unknown_tag_fails(self, monkeypatch):
        from src.core.settings import settings
        monkeypatch.setattr(settings, "prompt_version_tag", "v9.9-inexistente")
        result = check_prompt_artifact()
        assert result.status == "FAIL"
        assert "v9.9-inexistente" in result.detail


class TestRunDoctor:
    def _ok(self, name="x"):
        return CheckResult(name, "OK", "ok")

    def test_exit_zero_when_all_pass(self, monkeypatch, capsys):
        for fn in (
            "check_repo_hygiene", "check_prompt_artifact", "check_ollama_up",
            "check_model_digest", "check_supabase", "check_disk_space",
        ):
            monkeypatch.setattr(
                doctor, fn, lambda *a, _n=fn, **k: self._ok(_n)
            )
        assert run_doctor() == 0
        assert "PRONTO" in capsys.readouterr().out

    def test_exit_one_on_failure(self, monkeypatch, capsys):
        monkeypatch.setattr(doctor, "check_repo_hygiene", lambda: self._ok())
        monkeypatch.setattr(doctor, "check_prompt_artifact", lambda: self._ok())
        monkeypatch.setattr(
            doctor, "check_ollama_up",
            lambda: CheckResult("ollama", "FAIL", "down"),
        )
        monkeypatch.setattr(doctor, "check_model_digest", lambda m=None: self._ok())
        monkeypatch.setattr(doctor, "check_supabase", lambda: self._ok())
        monkeypatch.setattr(doctor, "check_disk_space", lambda: self._ok())
        assert run_doctor() == 1
        assert "REPROVADO" in capsys.readouterr().out

    def test_warn_and_info_do_not_fail(self, monkeypatch):
        monkeypatch.setattr(doctor, "check_repo_hygiene", lambda: self._ok())
        monkeypatch.setattr(doctor, "check_prompt_artifact", lambda: self._ok())
        monkeypatch.setattr(doctor, "check_ollama_up", lambda: self._ok())
        monkeypatch.setattr(doctor, "check_model_digest", lambda m=None: self._ok())
        monkeypatch.setattr(
            doctor, "check_supabase",
            lambda: CheckResult("supabase", "INFO", "local-only"),
        )
        monkeypatch.setattr(
            doctor, "check_disk_space",
            lambda: CheckResult("disco", "WARN", "pouco espaço"),
        )
        assert run_doctor() == 0
