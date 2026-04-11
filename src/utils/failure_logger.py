"""Logging centralizado de falhas de parsing JSON via JSONL.

Migrado de JSON array (read-modify-write) para JSONL (append-only).

Antes: carregar json_failures.json inteiro (12MB), append, reescrever.
Depois: abrir em modo append, escrever uma linha. O(1) por falha.

O formato JSONL é compatível com leitura linha por linha:
    with open(file) as f:
        for line in f:
            record = json.loads(line)

Refs: REFACTORING_PLAN.md Phase 6.2
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
    """Salva falha de parsing JSON em arquivo JSONL (append-only).

    Args:
        failures_file: Caminho do arquivo de falhas (.jsonl ou .json).
        commit_hash: Hash do commit que falhou.
        repository: URL ou nome do repositório.
        commit_message: Mensagem do commit.
        raw_response: Resposta bruta do LLM.
        error_msg: Descrição do erro.
        prompt_excerpt: Trecho do prompt enviado ao LLM.
        extra_fields: Campos adicionais específicos do handler.
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

        # Garantir que o diretório existe
        parent = os.path.dirname(failures_file)
        if parent:
            os.makedirs(parent, exist_ok=True)

        # Append-only: uma linha JSON por falha
        with open(failures_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(failure_entry, ensure_ascii=False) + "\n")

    except Exception:
        # Falha no logger não deve interromper a análise principal
        pass


def read_failures(failures_file: str) -> list:
    """Lê falhas de um arquivo JSONL ou JSON legado."""
    if not os.path.exists(failures_file):
        return []

    records = []
    with open(failures_file, "r", encoding="utf-8") as f:
        content = f.read().strip()

    if not content:
        return []

    # Detectar formato: JSONL (linhas) vs JSON array legado
    if content.startswith("["):
        # Formato legado: JSON array
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return []
    else:
        # Formato JSONL: uma entrada por linha
        for line in content.splitlines():
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return records
