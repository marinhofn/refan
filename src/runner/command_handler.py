"""Handler de comandos remotos para o runner de análise.

Processa comandos recebidos via Supabase command_queue, permitindo
controle remoto do runner a partir do dashboard.

Comandos suportados:
- pause: pausa o loop de análise (bloqueia até resume, com timeout máximo)
- resume: retoma análise pausada
- cancel: interrompe a sessão atual
- skip_commit: adiciona commit à skip list (hash validado)
- reanalyze_commit: agenda commit para reanálise (consumido pelo analisador
  via drain_reanalyze_queue a cada iteração)

Reformado na Fase E4 (EVOLUTION_PLAN.md, ROB-5):
- ``change_model`` foi REMOVIDO: trocar o modelo no meio de uma sessão muda a
  condição experimental sob o mesmo config_snapshot — o comando era aceito,
  marcado "Executed" e não fazia nada (falso sucesso). Agora é rejeitado com
  result_message explicativo (inicie nova sessão com --model).
- payloads são validados (formato de hash) antes de qualquer efeito;
- comando que falha é marcado ``failed`` no cloud (antes ficava preso em
  ``acknowledged`` para sempre);
- a pausa tem timeout máximo (settings.max_pause_s) com auto-resume logado,
  e o runner continua enviando heartbeat "paused" enquanto espera.

Refs: ARCHITECTURE_PLAN.md Phase 11.3; EVOLUTION_PLAN.md Fase E4.
"""

from __future__ import annotations

import time

from src.core.settings import settings as _settings
from src.handlers.git_handler import is_valid_commit_hash
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class AnalysisCancelled(Exception):
    """Exceção levantada quando a análise é cancelada via comando remoto."""
    pass


class CommandRejected(Exception):
    """Comando remoto inválido/não suportado — marcado como failed no cloud."""
    pass


class CommandHandler:
    """Processa comandos remotos entre iterações do loop de análise."""

    def __init__(self, supabase_client, runner_id: str):
        """
        Args:
            supabase_client: Instância de SupabaseClient (ou None se offline).
            runner_id: Identificador único deste runner.
        """
        self.supabase = supabase_client
        self.runner_id = runner_id
        self.state = "running"
        self.skip_list: set[str] = set()
        self.reanalyze_queue: list[str] = []

    def poll_and_execute(self) -> list[str]:
        """Consulta e executa comandos pendentes.

        Returns:
            Lista de comandos executados (nomes).
        """
        if self.supabase is None:
            return []

        commands = self.supabase.poll_commands(self.runner_id)
        executed = []

        for cmd in commands:
            command_name = cmd.get("command", "")
            payload = cmd.get("payload") or {}
            command_id = cmd.get("id", "")

            try:
                self._execute_command(command_name, payload)
                executed.append(command_name)
                self.supabase.complete_command(
                    command_id, result_message=f"Executed: {command_name}"
                )
                logger.info(f"Comando executado: {command_name}")
            except AnalysisCancelled:
                self.supabase.complete_command(
                    command_id, result_message="Sessão cancelada pelo comando"
                )
                raise
            except CommandRejected as e:
                # ROB-5: rejeição explícita — o dashboard vê 'failed' com o
                # motivo, nunca um falso "Executed".
                logger.warning(f"Comando rejeitado ({command_name}): {e}")
                self.supabase.fail_command(command_id, result_message=str(e))
            except Exception as e:
                # ROB-5: erro inesperado também vira 'failed' (antes o
                # comando ficava preso em 'acknowledged' para sempre).
                logger.warning(f"Erro ao executar comando {command_name}: {e}")
                self.supabase.fail_command(
                    command_id, result_message=f"Erro interno: {e}"
                )

        return executed

    def _execute_command(self, command: str, payload: dict) -> None:
        """Executa um comando individual (levanta CommandRejected se inválido)."""
        match command:
            case "pause":
                self.state = "paused"
                logger.info("Análise pausada via comando remoto")
            case "resume":
                self.state = "running"
                logger.info("Análise retomada via comando remoto")
            case "cancel":
                self.state = "cancelled"
                raise AnalysisCancelled("Cancelado via comando remoto")
            case "skip_commit":
                commit_hash = self._require_valid_hash(payload)
                self.skip_list.add(commit_hash)
                logger.info(f"Commit {commit_hash[:8]} adicionado à skip list")
            case "reanalyze_commit":
                commit_hash = self._require_valid_hash(payload)
                if commit_hash not in self.reanalyze_queue:
                    self.reanalyze_queue.append(commit_hash)
                logger.info(f"Commit {commit_hash[:8]} agendado para reanálise")
            case "change_model":
                raise CommandRejected(
                    "change_model não é suportado: trocar o modelo no meio da "
                    "sessão muda a condição experimental sob o mesmo "
                    "config_snapshot. Inicie uma nova sessão com --model."
                )
            case _:
                raise CommandRejected(f"Comando desconhecido: {command!r}")

    @staticmethod
    def _require_valid_hash(payload: dict) -> str:
        """Extrai e valida commit_hash do payload (ROB-5)."""
        commit_hash = str(payload.get("commit_hash", "") or "")
        if not is_valid_commit_hash(commit_hash):
            raise CommandRejected(
                f"payload.commit_hash inválido: {commit_hash!r} (esperado 7-40 hex)"
            )
        return commit_hash

    def wait_if_paused(self, poll_interval: float = 5.0) -> None:
        """Bloqueia enquanto o estado for 'paused'.

        Continua fazendo polling para detectar 'resume' ou 'cancel', envia
        heartbeat 'paused' (o runner não fica mudo) e respeita o timeout
        máximo de pausa (settings.max_pause_s) com auto-resume logado —
        um 'pause' sem 'resume' não congela mais o runner para sempre.
        """
        paused_since = time.monotonic()
        while self.state == "paused":
            if time.monotonic() - paused_since > _settings.max_pause_s:
                logger.warning(
                    f"Pausa excedeu {_settings.max_pause_s}s — auto-resume "
                    f"(registre novo pause se necessário)."
                )
                self.state = "running"
                break
            logger.info("Runner pausado, aguardando resume...")
            if self.supabase is not None:
                try:
                    self.supabase.update_heartbeat(
                        runner_id=self.runner_id, status="paused"
                    )
                except Exception:
                    pass  # heartbeat é best-effort
            time.sleep(poll_interval)
            self.poll_and_execute()

    def should_skip(self, commit_hash: str) -> bool:
        """Verifica se o commit está na skip list."""
        return commit_hash in self.skip_list

    def drain_reanalyze_queue(self) -> list[str]:
        """Retorna e limpa os commits agendados para reanálise (ROB-5).

        Consumido pelo analisador a cada iteração — antes desta fase a fila
        era populada e jamais lida (comando aceito sem efeito).
        """
        queued, self.reanalyze_queue = self.reanalyze_queue, []
        return queued
