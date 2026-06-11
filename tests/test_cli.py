"""Testes unitários para a CLI (src/cli.py).

Primeira cobertura da interface de linha de comando (Fase H4 do
HARDENING_PLAN.md): parsing de argumentos e dispatch de subcomandos.
Os handlers reais são substituídos por stubs — nenhum analyzer, LLM
ou CSV real é tocado.
"""

import sys

import pytest

if sys.version_info < (3, 10):
    pytest.skip(
        "Código de produção usa sintaxe str | None (requer Python >= 3.10)",
        allow_module_level=True,
    )

import src.cli as cli
from src.cli import build_parser, run_cli


class TestBuildParser:
    def test_analyze_full_flags(self):
        args = build_parser().parse_args([
            "analyze", "--model", "deepseek-r1:8b", "--limit", "5",
            "--filter", "TRUE", "--dry-run", "--no-skip",
        ])
        assert args.command == "analyze"
        assert args.model == "deepseek-r1:8b"
        assert args.limit == 5
        assert args.filter == "TRUE"
        assert args.dry_run is True
        assert args.no_skip is True

    def test_analyze_defaults(self):
        args = build_parser().parse_args(["analyze"])
        assert args.model is None
        assert args.limit is None
        assert args.filter is None
        assert args.dry_run is False
        assert args.no_skip is False

    def test_analyze_short_flags(self):
        args = build_parser().parse_args(["analyze", "-m", "mistral", "-n", "10"])
        assert args.model == "mistral"
        assert args.limit == 10

    def test_filter_rejects_invalid_choice(self):
        with pytest.raises(SystemExit):
            build_parser().parse_args(["analyze", "--filter", "MAYBE"])

    def test_unknown_command_rejected(self):
        with pytest.raises(SystemExit):
            build_parser().parse_args(["explode"])

    def test_status_and_merge_sessions_accept_model(self):
        parser = build_parser()
        assert parser.parse_args(["status", "-m", "mistral"]).command == "status"
        assert parser.parse_args(
            ["merge-sessions", "-m", "mistral"]
        ).command == "merge-sessions"

    def test_interactive_menu_choices(self):
        parser = build_parser()
        assert parser.parse_args(["interactive"]).menu == "full"
        assert parser.parse_args(["interactive", "--menu", "llm"]).menu == "llm"
        with pytest.raises(SystemExit):
            parser.parse_args(["interactive", "--menu", "outro"])


class TestRunCli:
    def test_no_command_prints_help_and_returns_zero(self, capsys):
        assert run_cli([]) == 0
        assert "usage: refan" in capsys.readouterr().out

    @pytest.mark.parametrize("command,handler_name", [
        (["analyze", "--dry-run"], "cmd_analyze"),
        (["status"], "cmd_status"),
        (["merge-sessions"], "cmd_merge_sessions"),
        (["interactive"], "cmd_interactive"),
    ])
    def test_dispatches_to_handler(self, monkeypatch, command, handler_name):
        captured = {}

        def fake_handler(args):
            captured["args"] = args
            return 0

        monkeypatch.setattr(cli, handler_name, fake_handler)
        assert run_cli(command) == 0
        assert captured["args"].command == command[0]

    def test_handler_exit_code_is_propagated(self, monkeypatch):
        monkeypatch.setattr(cli, "cmd_status", lambda args: 3)
        assert run_cli(["status"]) == 3
