"""Logging centralizado de falhas de parsing JSON.

Consolida save_json_failure() de:
- llm_handler.py:192-238 (~46 linhas)
- optimized_llm_handler.py:355-399 (~44 linhas)

Ambas versões eram quase idênticas (mesma lógica de load/append/save).
Diferenças absorvidas via parâmetro extra_fields.

Refs: REFACTORING_PLAN.md Phase 1.3
"""

import json
import os
import datetime
from typing import Optional


def save_json_failure(
    failures_file: str,
    commit_hash: str,
    repository: str,
    commit_message: str,
    raw_response: str,
    error_msg: str,
    prompt_excerpt: Optional[str] = None,
    extra_fields: Optional[dict] = None,
) -> None:
    """Salva falha de parsing JSON em arquivo separado.

    Mantém compatibilidade com o formato existente (JSON array) para não
    quebrar scripts que leem json_failures.json.

    Args:
        failures_file: Caminho do arquivo de falhas.
        commit_hash: Hash do commit que falhou.
        repository: URL ou nome do repositório.
        commit_message: Mensagem do commit.
        raw_response: Resposta bruta do LLM.
        error_msg: Descrição do erro.
        prompt_excerpt: Trecho do prompt enviado ao LLM.
        extra_fields: Campos adicionais específicos do handler
            (ex: parse_attempts, notes).
    """
    try:
        failure_entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "commit_hash": commit_hash,
            "repository": repository,
            "commit_message": commit_message,
            "error": error_msg,
            "llm_response_complete": raw_response,
            "llm_response_excerpt": raw_response,
            "analysis_attempt": "JSON parsing failed",
            "prompt_excerpt": prompt_excerpt,
        }
        if extra_fields:
            failure_entry.update(extra_fields)

        existing_failures = []
        if os.path.exists(failures_file):
            try:
                with open(failures_file, "r", encoding="utf-8") as f:
                    existing_failures = json.load(f)
            except json.JSONDecodeError:
                existing_failures = []

        existing_failures.append(failure_entry)

        with open(failures_file, "w", encoding="utf-8") as f:
            json.dump(existing_failures, f, indent=2, ensure_ascii=False)

    except Exception:
        # Falha no logger não deve interromper a análise principal
        pass
