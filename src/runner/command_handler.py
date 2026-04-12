"""Handler de comandos remotos para o runner de análise.

Processa comandos recebidos via Supabase command_queue, permitindo
controle remoto do runner a partir do dashboard.

Comandos suportados:
- pause: pausa o loop de análise (bloqueia até resume)
- resume: retoma análise pausada
- cancel: interrompe a sessão atual
- skip_commit: adiciona commit à skip list
- reanalyze_commit: agenda commit para reanálise
- change_model: troca modelo mid-session

Refs: ARCHITECTURE_PLAN.md Phase 11.3
"""

from __future__ import annotations

import time
from typing import Optional

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class AnalysisCancelled(Exception):
    """Exceção levantada quando a análise é cancelada via comando remoto."""
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
        self._model_change_request: Optional[str] = None

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
                if self.supabase:
                    self.supabase.complete_command(
                        command_id, result_message=f"Executed: {command_name}"
                    )
                logger.info(f"Comando executado: {command_name}")
            except AnalysisCancelled:
                if self.supabase:
                    self.supabase.complete_command(
                        command_id, result_message="Analysis cancelled"
                    )
                raise
            except Exception as e:
                logger.warning(f"Erro ao executar comando {command_name}: {e}")

        return executed

    def _execute_command(self, command: str, payload: dict) -> None:
        """Executa um comando individual."""
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
                commit_hash = payload.get("commit_hash", "")
                if commit_hash:
                    self.skip_list.add(commit_hash)
                    logger.info(f"Commit {commit_hash[:8]} adicionado à skip list")
            case "reanalyze_commit":
                commit_hash = payload.get("commit_hash", "")
                if commit_hash:
                    self.reanalyze_queue.append(commit_hash)
                    logger.info(f"Commit {commit_hash[:8]} agendado para reanálise")
            case "change_model":
                model_name = payload.get("model_name", "")
                if model_name:
                    self._model_change_request = model_name
                    logger.info(f"Troca de modelo solicitada: {model_name}")
            case _:
                logger.warning(f"Comando desconhecido: {command}")

    def wait_if_paused(self, poll_interval: float = 5.0) -> None:
        """Bloqueia enquanto o estado for 'paused'.

        Continua fazendo polling para detectar 'resume' ou 'cancel'.
        """
        while self.state == "paused":
            logger.info("Runner pausado, aguardando resume...")
            time.sleep(poll_interval)
            self.poll_and_execute()

    def should_skip(self, commit_hash: str) -> bool:
        """Verifica se o commit está na skip list."""
        return commit_hash in self.skip_list

    def get_model_change_request(self) -> Optional[str]:
        """Retorna e limpa pedido de troca de modelo, se houver."""
        request = self._model_change_request
        self._model_change_request = None
        return request
