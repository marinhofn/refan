"""Adaptadores para tradução entre formatos legados e modelos canônicos.

Converte entre:
- Rows de CSV (commit1/commit2/project) <-> CommitPair
- Dicts do LLM handler <-> AnalysisResult
- AnalysisResult -> dict para CSV

Refs: REFACTORING_PLAN.md Phase 5.2
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from src.models.commit import CommitPair, AnalysisResult
from src.utils.classification import VALID_CLASSIFICATIONS


def commit_from_csv_row(row: pd.Series) -> CommitPair:
    """Constrói CommitPair a partir de uma row do CSV de commits.

    Suporta ambos os formatos de coluna:
    - Legado: commit1, commit2, project, project_name
    - Novo: commit_hash_before, commit_hash_current, repository
    """
    return CommitPair(
        repository=row.get("project", row.get("repository", "")),
        commit_hash_before=row.get("commit1", row.get("commit_hash_before", "")),
        commit_hash_current=row.get("commit2", row.get("commit_hash_current", "")),
        project_name=row.get("project_name", ""),
    )


def commit_from_dict(data: dict) -> CommitPair:
    """Constrói CommitPair a partir de um dicionário genérico."""
    return CommitPair(
        repository=data.get("project", data.get("repository", "")),
        commit_hash_before=data.get("commit1", data.get("commit_hash_before", "")),
        commit_hash_current=data.get("commit2", data.get("commit_hash_current", "")),
        project_name=data.get("project_name", ""),
        commit_message=data.get("commit_message", ""),
        diff=data.get("diff", ""),
    )


def analysis_from_llm_response(
    raw_dict: dict,
    commit: CommitPair,
    llm_raw_response: str = "",
) -> AnalysisResult:
    """Constrói AnalysisResult a partir do dict retornado pelo LLM handler.

    Normaliza variantes de campo (project -> repository, etc.) e preenche
    identificadores com dados do CommitPair quando ausentes.

    Guarda de fabricação (Fase E2, VAL-8): ``refactoring_type`` ausente ou
    inválido é erro do chamador — o handler só entrega dicts com veredito
    validado — e levanta ValueError em vez de degradar silenciosamente para
    'floss' (o antigo default contaminava os dados com rótulos que o modelo
    nunca emitiu). Variáveis de pesquisa ausentes permanecem None (VAL-3).
    """
    refactoring_type = str(raw_dict.get("refactoring_type") or "").strip().lower()
    if refactoring_type not in VALID_CLASSIFICATIONS:
        raise ValueError(
            f"refactoring_type inválido em resposta do LLM: "
            f"{raw_dict.get('refactoring_type')!r} (esperado pure|floss)"
        )
    return AnalysisResult(
        repository=raw_dict.get("repository", commit.repository),
        commit_hash_before=raw_dict.get("commit_hash_before", commit.commit_hash_before),
        commit_hash_current=raw_dict.get("commit_hash_current", commit.commit_hash_current),
        refactoring_type=refactoring_type,
        justification=raw_dict.get("justification"),
        confidence_level=raw_dict.get("confidence_level"),
        technical_evidence=raw_dict.get("technical_evidence"),
        llm_raw_response=raw_dict.get("llm_raw_response", llm_raw_response),
        extraction_method=raw_dict.get("extraction_method", ""),
        diff_size_chars=raw_dict.get("diff_size_chars", 0),
        diff_lines=raw_dict.get("diff_lines", 0),
        diff_source=raw_dict.get("diff_source", "direct"),
        original_diff_size_chars=raw_dict.get("original_diff_size_chars", 0),
        diff_truncated=raw_dict.get("diff_truncated", False),
        num_ctx_effective=raw_dict.get("num_ctx_effective", 0),
        num_predict_effective=raw_dict.get("num_predict_effective", 0),
        prompt_chars=raw_dict.get("prompt_chars", 0),
        seed_effective=raw_dict.get("seed_effective"),
        prompt_sha256_effective=raw_dict.get("prompt_sha256_effective", ""),
        diff_sha256=raw_dict.get("diff_sha256", ""),
        processing_time_ms=raw_dict.get("processing_time_ms", 0),
        commit_message=raw_dict.get("commit_message", commit.commit_message),
        project_name=commit.project_name,
        success=raw_dict.get("success", True),
    )


def analysis_to_session_dict(result: AnalysisResult) -> dict:
    """Converte AnalysisResult para dict usado nos JSONs/JSONL de sessão.

    Desde a Fase E2 (VAL-3) o dict inclui ``extraction_method`` e ``success``
    — antes eram descartados aqui, o que impedia auditar a proveniência do
    veredito nos registros históricos (docs/REPRODUCIBILITY.md §6).
    """
    return {
        "hash": result.commit_hash_current,
        "purity_classification": "",  # preenchido pelo caller
        "llm_classification": result.refactoring_type.upper(),
        "llm_justification": result.justification,
        "llm_confidence": result.confidence_level,
        "project_name": result.project_name,
        "analysis_timestamp": result.timestamp,
        "diff_size": result.diff_size_chars,
        "diff_lines": result.diff_lines,
        "llm_raw_response": result.llm_raw_response,
        "repository": result.repository,
        "commit_hash_before": result.commit_hash_before,
        "commit_hash_current": result.commit_hash_current,
        "technical_evidence": result.technical_evidence,
        "diff_source": result.diff_source,
        "extraction_method": result.extraction_method,
        "success": result.success,
        "original_diff_size_chars": result.original_diff_size_chars,
        "diff_truncated": result.diff_truncated,
        "num_ctx_effective": result.num_ctx_effective,
        "num_predict_effective": result.num_predict_effective,
        "prompt_chars": result.prompt_chars,
        "seed_effective": result.seed_effective,
        "prompt_sha256_effective": result.prompt_sha256_effective,
        "diff_sha256": result.diff_sha256,
        "processing_time_ms": result.processing_time_ms,
    }
