"""Testes unitários para CommandHandler (src/runner/command_handler.py).

Primeira cobertura do controle remoto do runner via command_queue
(Fase H4 do HARDENING_PLAN.md). O SupabaseClient é substituído por um
stub em memória — nenhuma chamada de rede.
"""

import sys

import pytest

if sys.version_info < (3, 10):
    pytest.skip(
        "Código de produção usa sintaxe str | None (requer Python >= 3.10)",
        allow_module_level=True,
    )

from src.runner.command_handler import AnalysisCancelled, CommandHandler


class FakeSupabase:
    """Stub mínimo da interface usada pelo CommandHandler."""

    def __init__(self, commands=None):
        self.pending = list(commands or [])
        self.completed = []

    def poll_commands(self, runner_id):
        commands, self.pending = self.pending, []
        return commands

    def complete_command(self, command_id, result_message=""):
        self.completed.append((command_id, result_message))
        return True


def make_handler(commands=None):
    return CommandHandler(FakeSupabase(commands), runner_id="test-runner")


class TestOfflineMode:
    def test_without_supabase_poll_returns_empty(self):
        handler = CommandHandler(None, runner_id="test-runner")
        assert handler.poll_and_execute() == []
        assert handler.state == "running"


class TestStateCommands:
    def test_pause_sets_paused_state(self):
        handler = make_handler([{"id": "1", "command": "pause", "payload": {}}])
        executed = handler.poll_and_execute()
        assert executed == ["pause"]
        assert handler.state == "paused"

    def test_resume_restores_running_state(self):
        handler = make_handler([
            {"id": "1", "command": "pause", "payload": {}},
            {"id": "2", "command": "resume", "payload": {}},
        ])
        handler.poll_and_execute()
        assert handler.state == "running"

    def test_cancel_raises_and_acknowledges_command(self):
        handler = make_handler([{"id": "1", "command": "cancel", "payload": {}}])
        with pytest.raises(AnalysisCancelled):
            handler.poll_and_execute()
        # O comando é marcado como completed antes de propagar a exceção,
        # para que o dashboard saiba que o cancel foi recebido.
        assert handler.supabase.completed == [("1", "Analysis cancelled")]


class TestCommitCommands:
    def test_skip_commit_populates_skip_list(self):
        handler = make_handler([
            {"id": "1", "command": "skip_commit", "payload": {"commit_hash": "abc123"}},
        ])
        handler.poll_and_execute()
        assert handler.should_skip("abc123") is True
        assert handler.should_skip("outro") is False

    def test_skip_commit_without_hash_is_noop(self):
        handler = make_handler([
            {"id": "1", "command": "skip_commit", "payload": {}},
        ])
        handler.poll_and_execute()
        assert handler.skip_list == set()

    def test_reanalyze_commit_enqueues(self):
        handler = make_handler([
            {"id": "1", "command": "reanalyze_commit", "payload": {"commit_hash": "abc123"}},
        ])
        handler.poll_and_execute()
        assert handler.reanalyze_queue == ["abc123"]


class TestModelChange:
    def test_change_model_request_is_returned_once(self):
        handler = make_handler([
            {"id": "1", "command": "change_model", "payload": {"model_name": "gemma2:2b"}},
        ])
        handler.poll_and_execute()
        assert handler.get_model_change_request() == "gemma2:2b"
        # Segunda leitura: pedido já consumido.
        assert handler.get_model_change_request() is None


class TestRobustness:
    def test_unknown_command_does_not_raise(self):
        handler = make_handler([
            {"id": "1", "command": "autodestruir", "payload": {}},
        ])
        executed = handler.poll_and_execute()
        assert executed == ["autodestruir"]  # logado como warning, não propaga
        assert handler.state == "running"

    def test_commands_are_acknowledged_in_order(self):
        handler = make_handler([
            {"id": "1", "command": "pause", "payload": {}},
            {"id": "2", "command": "resume", "payload": {}},
        ])
        handler.poll_and_execute()
        assert [c[0] for c in handler.supabase.completed] == ["1", "2"]

    def test_null_payload_is_tolerated(self):
        handler = make_handler([
            {"id": "1", "command": "skip_commit", "payload": None},
        ])
        handler.poll_and_execute()  # não deve levantar
        assert handler.skip_list == set()
