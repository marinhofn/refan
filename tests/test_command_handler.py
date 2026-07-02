"""Testes unitários para CommandHandler (src/runner/command_handler.py).

Cobertura original da Fase H4; atualizada na Fase E4 (ROB-5,
EVOLUTION_PLAN.md) para o contrato honesto do runner remoto:
- payloads inválidos e comandos desconhecidos são marcados ``failed`` no
  cloud com o motivo (antes: falso "Executed"/preso em acknowledged);
- ``change_model`` é rejeitado (trocar modelo mid-sessão muda a condição
  experimental) — o comando antigo era aceito e não fazia nada;
- a fila de reanálise agora é consumível (drain_reanalyze_queue);
- a pausa tem timeout máximo com auto-resume.

O SupabaseClient é substituído por um stub em memória — nenhuma rede.
"""

import sys

import pytest

if sys.version_info < (3, 10):
    pytest.skip(
        "Código de produção usa sintaxe str | None (requer Python >= 3.10)",
        allow_module_level=True,
    )

from src.runner.command_handler import AnalysisCancelled, CommandHandler

VALID_HASH = "abc1234def"
OTHER_HASH = "1234567abcd"


class FakeSupabase:
    """Stub mínimo da interface usada pelo CommandHandler."""

    def __init__(self, commands=None):
        self.pending = list(commands or [])
        self.completed = []
        self.failed = []
        self.heartbeats = []

    def poll_commands(self, runner_id):
        commands, self.pending = self.pending, []
        return commands

    def complete_command(self, command_id, result_message=""):
        self.completed.append((command_id, result_message))
        return True

    def fail_command(self, command_id, result_message=""):
        self.failed.append((command_id, result_message))
        return True

    def update_heartbeat(self, **kwargs):
        self.heartbeats.append(kwargs)
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
        assert handler.supabase.completed == [("1", "Sessão cancelada pelo comando")]

    def test_pause_timeout_auto_resumes(self, monkeypatch):
        from src.core.settings import settings
        monkeypatch.setattr(settings, "max_pause_s", 0)  # timeout imediato
        handler = make_handler()
        handler.state = "paused"
        handler.wait_if_paused(poll_interval=0)  # não pode bloquear
        assert handler.state == "running"

    def test_paused_runner_keeps_heartbeating(self, monkeypatch):
        from src.core.settings import settings
        monkeypatch.setattr(settings, "max_pause_s", 3600)
        handler = make_handler()
        handler.state = "paused"
        beats = handler.supabase.heartbeats

        # resume chega no primeiro poll; um heartbeat 'paused' foi enviado
        handler.supabase.pending = [{"id": "9", "command": "resume", "payload": {}}]
        monkeypatch.setattr("src.runner.command_handler.time.sleep", lambda s: None)
        handler.wait_if_paused(poll_interval=0)

        assert handler.state == "running"
        assert beats and beats[0]["status"] == "paused"


class TestCommitCommands:
    def test_skip_commit_populates_skip_list(self):
        handler = make_handler([
            {"id": "1", "command": "skip_commit", "payload": {"commit_hash": VALID_HASH}},
        ])
        handler.poll_and_execute()
        assert handler.should_skip(VALID_HASH) is True
        assert handler.should_skip(OTHER_HASH) is False

    def test_skip_commit_without_hash_is_failed(self):
        """ROB-5: payload inválido vira 'failed' com motivo, não noop mudo."""
        handler = make_handler([
            {"id": "1", "command": "skip_commit", "payload": {}},
        ])
        handler.poll_and_execute()
        assert handler.skip_list == set()
        assert len(handler.supabase.failed) == 1
        assert "commit_hash inválido" in handler.supabase.failed[0][1]

    def test_reanalyze_enqueues_and_drains(self):
        """ROB-5: a fila agora é consumível — antes era populada e nunca lida."""
        handler = make_handler([
            {"id": "1", "command": "reanalyze_commit", "payload": {"commit_hash": VALID_HASH}},
        ])
        handler.poll_and_execute()
        assert handler.drain_reanalyze_queue() == [VALID_HASH]
        assert handler.drain_reanalyze_queue() == []  # drenada

    def test_reanalyze_deduplicates(self):
        handler = make_handler([
            {"id": "1", "command": "reanalyze_commit", "payload": {"commit_hash": VALID_HASH}},
            {"id": "2", "command": "reanalyze_commit", "payload": {"commit_hash": VALID_HASH}},
        ])
        handler.poll_and_execute()
        assert handler.drain_reanalyze_queue() == [VALID_HASH]


class TestModelChange:
    def test_change_model_is_rejected_with_reason(self):
        """ROB-5: o comando era aceito, marcado 'Executed' e não fazia NADA.
        Agora é rejeitado explicitamente (mudança de condição experimental)."""
        handler = make_handler([
            {"id": "1", "command": "change_model", "payload": {"model_name": "gemma2:2b"}},
        ])
        executed = handler.poll_and_execute()
        assert executed == []
        assert handler.supabase.completed == []
        assert len(handler.supabase.failed) == 1
        assert "condição experimental" in handler.supabase.failed[0][1]


class TestRobustness:
    def test_unknown_command_is_failed_not_fake_executed(self):
        handler = make_handler([
            {"id": "1", "command": "autodestruir", "payload": {}},
        ])
        executed = handler.poll_and_execute()
        assert executed == []
        assert handler.supabase.failed == [("1", "Comando desconhecido: 'autodestruir'")]
        assert handler.state == "running"

    def test_commands_are_acknowledged_in_order(self):
        handler = make_handler([
            {"id": "1", "command": "pause", "payload": {}},
            {"id": "2", "command": "resume", "payload": {}},
        ])
        handler.poll_and_execute()
        assert [c[0] for c in handler.supabase.completed] == ["1", "2"]

    def test_null_payload_is_failed_gracefully(self):
        handler = make_handler([
            {"id": "1", "command": "skip_commit", "payload": None},
        ])
        handler.poll_and_execute()  # não deve levantar
        assert handler.skip_list == set()
        assert len(handler.supabase.failed) == 1
