"""Modelos de dados canônicos para commits e resultados de análise.

Define as estruturas que padronizam os nomes de campos entre:
- CSVs de entrada (commit1/commit2/project/project_name)
- Handlers LLM (commit_hash_before/commit_hash_current/repository)
- Resultados de análise (refactoring_type/classification/llm_analysis)

Todos os módulos devem usar estes modelos como interface comum.
A tradução entre formatos legados é feita por src/models/adapters.py.

Refs: REFACTORING_PLAN.md Phase 5.1
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.utils.timeutils import utc_now_iso


@dataclass
class CommitPair:
    """Par de commits para análise de refatoração.

    Nomes canônicos:
    - repository (era: project, project_name)
    - commit_hash_before (era: commit1, previous_hash)
    - commit_hash_current (era: commit2, commit_hash)
    """

    repository: str
    commit_hash_before: str
    commit_hash_current: str
    project_name: str = ""
    commit_message: str = ""
    diff: str = ""


@dataclass
class AnalysisResult:
    """Resultado de uma análise LLM de refatoração.

    Nomes canônicos:
    - refactoring_type (era: classification, llm_analysis)
    - llm_raw_response (era: llm_response_complete, llm_response_excerpt)
    """

    repository: str
    commit_hash_before: str
    commit_hash_current: str
    refactoring_type: str
    justification: str
    confidence_level: str = "medium"
    technical_evidence: str = ""
    llm_raw_response: str = ""
    extraction_method: str = ""
    diff_size_chars: int = 0
    diff_lines: int = 0
    diff_source: str = "direct"
    processing_time_ms: int = 0
    timestamp: str = field(default_factory=utc_now_iso)
    success: bool = True
    commit_message: str = ""
    project_name: str = ""

    def to_csv_value(self) -> str:
        """Retorna valor para a coluna llm_analysis do CSV."""
        return self.refactoring_type.upper()
