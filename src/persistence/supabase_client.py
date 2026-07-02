"""Cliente Supabase para persistência cloud do Refan.

Encapsula todas as operações de banco de dados via supabase-py.
O runner usa service_role key (bypass RLS) para escrita direta.
Operações são idempotentes onde possível (upsert, ON CONFLICT).

Se o Supabase estiver indisponível (rede), os métodos logam o erro
e retornam None/False — o JSONL local (Fase 6) serve como fallback.

Refs: ARCHITECTURE_PLAN.md Phase 11.2
"""

from __future__ import annotations

import hashlib
import json
import time
from src.utils.timeutils import utc_now_iso
from typing import Optional

from src.utils.logging_config import get_logger

logger = get_logger(__name__)

# Import condicional: supabase pode não estar instalado
try:
    from supabase import create_client, Client
    try:
        from supabase import ClientOptions
    except ImportError:  # versões antigas expõem em submódulo
        from supabase.lib.client_options import ClientOptions
    HAS_SUPABASE = True
except ImportError:
    HAS_SUPABASE = False
    Client = None
    ClientOptions = None

from src.core.settings import settings as _settings


class PromptVersionConflictError(RuntimeError):
    """Tag de prompt reutilizada com conteúdo diferente do registrado.

    Levantada por get_or_create_prompt_version (Fase E2, VAL-4): versões de
    prompt publicadas são imutáveis; prosseguir gravaria resultados com
    proveniência falsa. A sessão deve ser abortada e uma nova tag registrada.
    """


class SupabaseClient:
    """Cliente para operações de persistência no Supabase."""

    def __init__(self, url: str, service_key: str):
        if not HAS_SUPABASE:
            raise ImportError(
                "supabase-py não instalado. Execute: pip install supabase"
            )
        if not url or not service_key:
            raise ValueError(
                "SUPABASE_URL e SUPABASE_SERVICE_KEY devem estar configurados"
            )
        # Timeout explícito: sem ele, uma chamada PostgREST pode bloquear o
        # runner indefinidamente em rede degradada (Fase H6).
        options = ClientOptions(postgrest_client_timeout=_settings.supabase_timeout_s)
        self.client: Client = create_client(url, service_key, options=options)
        self._model_cache: dict[str, str] = {}  # name -> uuid
        self._commit_cache: dict[str, str] = {}  # hash -> uuid
        self._prompt_cache: dict[str, str] = {}  # version_tag -> uuid

    def _execute_with_retry(self, operation: str, build_query, attempts: int | None = None):
        """Executa uma query PostgREST com retry e backoff exponencial.

        Args:
            operation: Nome da operação (para logging estruturado).
            build_query: Callable sem argumentos que constrói a query;
                reconstruída a cada tentativa para não reutilizar estado.
            attempts: Número de tentativas. Default: settings.supabase_max_retries.
                Operações periódicas (heartbeat, polling) devem passar 1 —
                a próxima iteração do loop já as repete naturalmente.

        Returns:
            O resultado de .execute().

        Raises:
            A última exceção, após esgotar as tentativas. Os métodos
            públicos capturam e preservam o contrato documentado
            (None/False/[] na falha final; fallback JSONL local).
        """
        if attempts is None:
            attempts = _settings.supabase_max_retries
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                return build_query().execute()
            except Exception as e:
                last_error = e
                logger.warning(
                    f"Supabase {operation} falhou "
                    f"(tentativa {attempt}/{attempts}): {e}"
                )
                if attempt < attempts:
                    time.sleep(_settings.supabase_backoff_base_s * (2 ** (attempt - 1)))
        logger.error(
            f"Supabase {operation}: desistindo após {attempts} tentativas: {last_error}"
        )
        raise last_error

    # ------------------------------------------------------------------
    # Commits
    # ------------------------------------------------------------------

    def upsert_commit(
        self,
        commit_hash_current: str,
        commit_hash_before: str,
        repository_url: str,
        project_name: str,
        purity_analysis: str | None = None,
    ) -> Optional[str]:
        """Insert ou get commit, retorna UUID.

        Chaves com valor None são OMITIDAS do payload (Fase E2, VAL-5):
        o upsert com ``"purity_analysis": None`` sobrescrevia para NULL o
        baseline Purity de commits já registrados — a variável independente
        da pesquisa era apagada em cada sync offline->online.
        """
        if commit_hash_current in self._commit_cache:
            return self._commit_cache[commit_hash_current]

        payload = {
            "commit_hash_current": commit_hash_current,
            "commit_hash_before": commit_hash_before,
            "repository_url": repository_url,
            "project_name": project_name,
        }
        if purity_analysis is not None:
            payload["purity_analysis"] = purity_analysis

        try:
            result = self._execute_with_retry(
                "upsert_commit",
                lambda: self.client.table("commits").upsert(
                    payload,
                    on_conflict="commit_hash_current",
                ),
            )
            if result.data:
                uid = result.data[0]["id"]
                self._commit_cache[commit_hash_current] = uid
                return uid
        except Exception as e:
            logger.warning(f"Supabase upsert_commit falhou: {e}")
        return None

    # ------------------------------------------------------------------
    # Modelos
    # ------------------------------------------------------------------

    def get_or_create_model(
        self,
        name: str,
        family: str = "",
        parameter_count: str = "",
    ) -> Optional[str]:
        """Retorna UUID do modelo, criando se necessário."""
        if name in self._model_cache:
            return self._model_cache[name]

        safe_name = name.replace(":", "_")
        try:
            result = self._execute_with_retry(
                "get_or_create_model",
                lambda: self.client.table("llm_models").upsert(
                    {
                        "name": name,
                        "safe_name": safe_name,
                        "family": family,
                        "parameter_count": parameter_count,
                    },
                    on_conflict="name",
                ),
            )
            if result.data:
                uid = result.data[0]["id"]
                self._model_cache[name] = uid
                return uid
        except Exception as e:
            logger.warning(f"Supabase get_or_create_model falhou: {e}")
        return None

    # ------------------------------------------------------------------
    # Prompt versions
    # ------------------------------------------------------------------

    def get_prompt_version(self, version_tag: str) -> Optional[dict]:
        """SELECT id e sha256_hash de uma versão de prompt já registrada.

        Usado para validar que o prompt em disco do runner é idêntico ao
        registrado no banco (HARDENING_PLAN.md, Fase H5). Retorna None se
        a versão não existe ou em falha de rede.
        """
        try:
            result = self._execute_with_retry(
                "get_prompt_version",
                lambda: self.client.table("prompt_versions")
                .select("id, sha256_hash")
                .eq("version_tag", version_tag),
            )
            if result.data:
                return result.data[0]
        except Exception as e:
            logger.warning(f"Supabase get_prompt_version falhou: {e}")
        return None

    def get_or_create_prompt_version(
        self,
        version_tag: str,
        system_prompt: str,
        description: str = "",
    ) -> Optional[str]:
        """Retorna UUID da versão do prompt, criando SOMENTE se inexistente.

        Registro de versão de prompt é IMUTÁVEL (Fase E2, VAL-4): o upsert
        anterior sobrescrevia system_prompt/sha256_hash quando a tag já
        existia com outro conteúdo — resultados históricos passavam a
        apontar para um prompt que não foi o usado (proveniência corrompida).

        Semântica get-then-insert:
        - tag inexistente -> INSERT e retorna o UUID novo;
        - tag existente com o MESMO sha256 -> retorna o UUID registrado;
        - tag existente com sha256 DIFERENTE -> PromptVersionConflictError.
          O operador deve registrar uma nova tag (REFAN_PROMPT_VERSION) em
          vez de reutilizar a antiga com texto alterado.

        Retorna None apenas em falha de rede/API (fallback local continua).
        """
        if version_tag in self._prompt_cache:
            return self._prompt_cache[version_tag]

        sha256 = hashlib.sha256(system_prompt.encode()).hexdigest()

        existing = self.get_prompt_version(version_tag)
        if existing:
            if existing.get("sha256_hash") != sha256:
                raise PromptVersionConflictError(
                    f"A tag '{version_tag}' já está registrada com sha256 "
                    f"{existing.get('sha256_hash', '')[:12]}..., mas o prompt "
                    f"local tem sha256 {sha256[:12]}.... Prompts publicados são "
                    f"imutáveis — registre uma NOVA versão (REFAN_PROMPT_VERSION) "
                    f"e documente-a em docs/PROMPTS.md."
                )
            uid = existing["id"]
            self._prompt_cache[version_tag] = uid
            return uid

        try:
            result = self._execute_with_retry(
                "get_or_create_prompt_version",
                lambda: self.client.table("prompt_versions").insert(
                    {
                        "version_tag": version_tag,
                        "system_prompt": system_prompt,
                        "sha256_hash": sha256,
                        "description": description,
                    },
                ),
            )
            if result.data:
                uid = result.data[0]["id"]
                self._prompt_cache[version_tag] = uid
                return uid
        except Exception as e:
            logger.warning(f"Supabase get_or_create_prompt_version falhou: {e}")
        return None

    # ------------------------------------------------------------------
    # Sessões
    # ------------------------------------------------------------------

    def start_session(
        self,
        model_id: str,
        prompt_version_id: str,
        config_snapshot: dict,
        runner_hostname: str = "",
        total_planned: int = 0,
        purity_filter: str | None = None,
    ) -> Optional[str]:
        """Cria analysis_session, retorna UUID."""
        try:
            result = self._execute_with_retry(
                "start_session",
                lambda: self.client.table("analysis_sessions").insert(
                    {
                        "model_id": model_id,
                        "prompt_version_id": prompt_version_id,
                        "config_snapshot": config_snapshot,
                        "runner_hostname": runner_hostname,
                        "total_planned": total_planned,
                        "purity_filter": purity_filter,
                        "status": "running",
                    }
                ),
            )
            if result.data:
                return result.data[0]["id"]
        except Exception as e:
            logger.warning(f"Supabase start_session falhou: {e}")
        return None

    def update_session_status(
        self,
        session_id: str,
        status: str,
        total_completed: int = 0,
        total_failed: int = 0,
        total_skipped: int = 0,
        error_message: str | None = None,
    ) -> bool:
        """Atualiza status e contadores da sessão."""
        try:
            data: dict = {
                "status": status,
                "total_completed": total_completed,
                "total_failed": total_failed,
                "total_skipped": total_skipped,
            }
            if status in ("completed", "failed", "cancelled"):
                data["completed_at"] = utc_now_iso()
            if error_message:
                data["error_message"] = error_message

            self._execute_with_retry(
                "update_session_status",
                lambda: self.client.table("analysis_sessions").update(data).eq(
                    "id", session_id
                ),
            )
            return True
        except Exception as e:
            logger.warning(f"Supabase update_session_status falhou: {e}")
            return False

    # ------------------------------------------------------------------
    # Resultados
    # ------------------------------------------------------------------

    def record_result(
        self,
        session_id: str,
        commit_id: str,
        model_id: str,
        prompt_version_id: str,
        classification: str,
        justification: str = "",
        confidence_level: str = "",
        technical_evidence: str = "",
        llm_raw_response: str = "",
        extraction_method: str = "",
        diff_size_chars: int = 0,
        diff_lines: int = 0,
        processing_time_ms: int = 0,
        diff_source: str = "direct",
    ) -> bool:
        """INSERT em analysis_results."""
        try:
            self._execute_with_retry(
                "record_result",
                lambda: self.client.table("analysis_results").upsert(
                    {
                        "session_id": session_id,
                        "commit_id": commit_id,
                        "model_id": model_id,
                        "prompt_version_id": prompt_version_id,
                        "classification": classification.upper(),
                        "justification": justification,
                        "confidence_level": confidence_level,
                        "technical_evidence": technical_evidence,
                        "llm_raw_response": llm_raw_response,
                        "extraction_method": extraction_method,
                        "diff_size_chars": diff_size_chars,
                        "diff_lines": diff_lines,
                        "processing_time_ms": processing_time_ms,
                        "diff_source": diff_source,
                    },
                    on_conflict="session_id,commit_id",
                ),
            )
            return True
        except Exception as e:
            logger.warning(f"Supabase record_result falhou: {e}")
            return False

    def record_failure(
        self,
        session_id: str,
        commit_id: str | None,
        model_id: str,
        error_type: str,
        error_message: str = "",
        llm_raw_response: str = "",
        prompt_excerpt: str = "",
    ) -> bool:
        """INSERT em analysis_failures."""
        try:
            data = {
                "session_id": session_id,
                "model_id": model_id,
                "error_type": error_type,
                "error_message": error_message,
                "llm_raw_response": llm_raw_response,
                "prompt_excerpt": prompt_excerpt,
            }
            if commit_id:
                data["commit_id"] = commit_id
            self._execute_with_retry(
                "record_failure",
                lambda: self.client.table("analysis_failures").insert(data),
            )
            return True
        except Exception as e:
            logger.warning(f"Supabase record_failure falhou: {e}")
            return False

    # ------------------------------------------------------------------
    # Runner heartbeat
    # ------------------------------------------------------------------

    def update_heartbeat(
        self,
        runner_id: str,
        session_id: str | None = None,
        status: str = "running",
        current_commit_hash: str = "",
        current_commit_index: int = 0,
        total_commits_in_batch: int = 0,
        model_name: str = "",
    ) -> bool:
        """UPSERT runner_status (heartbeat).

        Tentativa única: o heartbeat é periódico — a próxima iteração do
        loop já o repete; retry com backoff só atrasaria a análise.
        """
        try:
            self._execute_with_retry(
                "update_heartbeat",
                lambda: self.client.table("runner_status").upsert(
                    {
                        "runner_id": runner_id,
                        "session_id": session_id,
                        "status": status,
                        "current_commit_hash": current_commit_hash,
                        "current_commit_index": current_commit_index,
                        "total_commits_in_batch": total_commits_in_batch,
                        "model_name": model_name,
                        "last_heartbeat": utc_now_iso(),
                        "updated_at": utc_now_iso(),
                    },
                    on_conflict="runner_id",
                ),
                attempts=1,
            )
            return True
        except Exception as e:
            logger.warning(f"Supabase update_heartbeat falhou: {e}")
            return False

    # ------------------------------------------------------------------
    # Command queue
    # ------------------------------------------------------------------

    def poll_commands(self, runner_id: str) -> list[dict]:
        """SELECT pending commands, marca como acknowledged.

        Tentativa única: o polling é periódico — comandos não lidos agora
        serão lidos na próxima iteração do loop.
        """
        try:
            result = self._execute_with_retry(
                "poll_commands",
                lambda: self.client.table("command_queue")
                .select("*")
                .eq("runner_id", runner_id)
                .eq("status", "pending")
                .order("created_at"),
                attempts=1,
            )
            commands = result.data or []
            # Marcar como acknowledged
            for cmd in commands:
                self._execute_with_retry(
                    "acknowledge_command",
                    lambda cmd_id=cmd["id"]: self.client.table("command_queue").update(
                        {
                            "status": "acknowledged",
                            "acknowledged_at": utc_now_iso(),
                        }
                    ).eq("id", cmd_id),
                    attempts=1,
                )
            return commands
        except Exception as e:
            logger.warning(f"Supabase poll_commands falhou: {e}")
            return []

    def complete_command(
        self, command_id: str, result_message: str = ""
    ) -> bool:
        """Marca comando como completed."""
        try:
            self._execute_with_retry(
                "complete_command",
                lambda: self.client.table("command_queue").update(
                    {
                        "status": "completed",
                        "completed_at": utc_now_iso(),
                        "result_message": result_message,
                    }
                ).eq("id", command_id),
                attempts=1,
            )
            return True
        except Exception as e:
            logger.warning(f"Supabase complete_command falhou: {e}")
            return False

    # ------------------------------------------------------------------
    # Sync offline
    # ------------------------------------------------------------------

    def sync_local_jsonl(self, jsonl_path: str, session_id: str, model_id: str, prompt_version_id: str) -> int:
        """Bulk-upload de registros JSONL locais para o Supabase.

        Usado para recovery após perda de conexão. Lê o JSONL e
        insere cada registro que ainda não existe no banco.

        Returns:
            Número de registros sincronizados.
        """
        import os
        if not os.path.exists(jsonl_path):
            return 0

        synced = 0
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    commit_hash = record.get("hash", record.get("commit_hash_current", ""))
                    if not commit_hash:
                        continue

                    # VAL-5: propagar o purity do registro local quando
                    # existir; upsert_commit omite a chave quando None, então
                    # o valor já registrado no cloud nunca é sobrescrito.
                    commit_id = self.upsert_commit(
                        commit_hash_current=commit_hash,
                        commit_hash_before=record.get("commit_hash_before", ""),
                        repository_url=record.get("repository", ""),
                        project_name=record.get("project_name", ""),
                        purity_analysis=record.get("purity_classification") or None,
                    )
                    if not commit_id:
                        continue

                    classification = record.get("llm_classification", record.get("refactoring_type", "FAILED"))
                    self.record_result(
                        session_id=session_id,
                        commit_id=commit_id,
                        model_id=model_id,
                        prompt_version_id=prompt_version_id,
                        classification=classification,
                        justification=record.get("llm_justification", record.get("justification", "")),
                        confidence_level=record.get("llm_confidence", record.get("confidence_level", "")),
                        technical_evidence=record.get("technical_evidence", ""),
                        llm_raw_response=record.get("llm_raw_response", ""),
                        diff_size_chars=record.get("diff_size", 0),
                        diff_lines=record.get("diff_lines", 0),
                    )
                    synced += 1
                except (json.JSONDecodeError, Exception) as e:
                    logger.warning(f"Sync falhou para linha: {e}")
                    continue

        logger.info(f"Sync completo: {synced} registros de {jsonl_path}")
        return synced
