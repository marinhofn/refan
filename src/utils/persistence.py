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
from datetime import datetime
from pathlib import Path
from typing import Optional


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
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            session_name = f"session_{timestamp}"

        self.file_path = self.sessions_dir / f"{session_name}.jsonl"
        self._count = 0

    def append(self, record: dict) -> None:
        """Adiciona um registro ao arquivo JSONL (append atômico)."""
        with open(self.file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._count += 1

    def read_all(self) -> list[dict]:
        """Lê todos os registros do arquivo JSONL."""
        if not self.file_path.exists():
            return []
        records = []
        with open(self.file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
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
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    if not records:
        return 0

    df = pd.read_csv(csv_path)
    # Coluna totalmente vazia é inferida como float64 (NaN); atribuir strings
    # nela é deprecated no pandas >= 2.1 e passará a levantar erro.
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
        df.to_csv(csv_path, index=False)

    return updated
