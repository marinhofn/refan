"""Persistência incremental via JSONL (JSON Lines).

Substitui o padrão de reescrever o CSV inteiro após cada commit
(llm_purity_analyzer.py) por append-only em arquivo JSONL.

JSONL: uma linha = um JSON object. Permite:
- Append atômico (sem ler o arquivo inteiro)
- Survives CTRL+C (linhas já escritas estão salvas)
- Fácil merge posterior em CSV

Refs: REFACTORING_PLAN.md Phase 6.1
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from src.core.settings import settings as _settings
from src.utils.atomic_io import atomic_write_text, file_lock
from src.utils.logging_config import get_logger
from src.utils.timeutils import utc_now_stamp

logger = get_logger(__name__)


class SessionWriter:
    """Escreve resultados de análise incrementalmente em arquivo JSONL.

    Cada chamada a append() adiciona uma linha ao arquivo sem reler o
    conteúdo existente. O arquivo é criado automaticamente na primeira
    escrita.

    Uso:
        writer = SessionWriter("output/models/mistral/sessions")
        writer.append(result_dict)
        writer.append(result_dict2)
        # No final:
        results = writer.read_all()
    """

    def __init__(self, sessions_dir: str, session_name: str | None = None):
        """Inicializa o writer.

        Args:
            sessions_dir: Diretório para arquivos de sessão.
            session_name: Nome do arquivo (sem extensão). Se None, gera
                         automaticamente com timestamp.
        """
        self.sessions_dir = Path(sessions_dir)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

        if session_name is None:
            session_name = f"session_{utc_now_stamp()}"

        self.file_path = self.sessions_dir / f"{session_name}.jsonl"
        self._count = 0

    def append(self, record: dict) -> None:
        """Adiciona um registro ao arquivo JSONL.

        Com ``settings.jsonl_fsync`` (default True — Fase E4, ROB-3), força
        flush+fsync por linha: o registro sobrevive a queda de energia, não
        só a crash do processo. Custo desprezível frente a uma inferência.
        """
        with open(self.file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            if _settings.jsonl_fsync:
                f.flush()
                os.fsync(f.fileno())
        self._count += 1

    def read_all(self) -> list[dict]:
        """Lê todos os registros do arquivo JSONL."""
        if not self.file_path.exists():
            return []
        records = []
        with open(self.file_path, "r", encoding="utf-8") as f:
            for line_number, line in enumerate(f, 1):
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        # ROB-3: linha truncada (crash no meio da escrita) é
                        # um REGISTRO PERDIDO — reportar, nunca engolir.
                        logger.warning(
                            "Linha %d inválida em %s — registro descartado "
                            "(possível escrita interrompida)",
                            line_number, self.file_path,
                        )
        return records

    @property
    def count(self) -> int:
        """Número de registros escritos nesta sessão."""
        return self._count

    @property
    def path(self) -> str:
        """Caminho do arquivo JSONL."""
        return str(self.file_path)


def merge_jsonl_to_csv(
    jsonl_path: str,
    csv_path: str,
    hash_column: str = "hash",
    value_column: str = "llm_analysis",
    value_key: str = "llm_classification",
) -> int:
    """Merge registros de um JSONL no CSV master.

    Para cada registro no JSONL, atualiza a coluna `value_column` no CSV
    onde a coluna `hash_column` corresponde ao campo `hash_column` do registro.

    Args:
        jsonl_path: Caminho do arquivo JSONL de sessão.
        csv_path: Caminho do CSV master a ser atualizado.
        hash_column: Nome da coluna de hash no CSV.
        value_column: Nome da coluna a ser atualizada no CSV.
        value_key: Chave no registro JSONL contendo o valor.

    Returns:
        Número de linhas atualizadas.
    """
    import pandas as pd

    records = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, 1):
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    logger.warning(
                        "Linha %d inválida em %s — registro ignorado no merge",
                        line_number, jsonl_path,
                    )

    if not records:
        return 0

    # Fase E4 (ROB-1): read-modify-write do master serializado por lock e
    # publicado atomicamente — sem clobber concorrente, sem CSV pela metade.
    with file_lock(csv_path):
        df = pd.read_csv(csv_path)
        # Coluna totalmente vazia é inferida como float64 (NaN); atribuir
        # strings nela é deprecated no pandas >= 2.1.
        if value_column in df.columns:
            df[value_column] = df[value_column].astype("object")
        updated = 0

        for record in records:
            commit_hash = record.get(hash_column)
            value = record.get(value_key)
            if commit_hash and value:
                mask = df[hash_column] == commit_hash
                if mask.any():
                    df.loc[mask, value_column] = value
                    updated += 1

        if updated > 0:
            atomic_write_text(csv_path, df.to_csv(index=False))

    return updated
