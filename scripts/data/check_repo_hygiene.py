"""Verificação de higiene do repositório contra artefatos de sincronização.

Contexto (EVOLUTION_PLAN.md, achados INT-1/INT-2): o repositório residiu em um
diretório sincronizado pelo iCloud Drive, que cria cópias de conflito com o
sufixo ``" 2"`` (ex.: ``arquivo 2.csv``) e chegou a remover arquivos originais
do baseline imutável ``baseline_tcc_2025/``. Este script torna essas condições
detectáveis de forma barata (sem exigir download dos objetos LFS), para uso
local e na CI.

Checagens (todas read-only):

1. Nenhum caminho **rastreado** pelo git contém ``" 2"`` no nome — impede que
   um ``git add -A`` descuidado versione artefatos de conflito.
2. Nenhum arquivo ``" 2"`` existe na working tree (fora de ``.git``, ``.venv``
   e ``.claude``) — alerta local de que a sincronização voltou a agir.
3. A working tree do ``baseline_tcc_2025/`` está limpa segundo
   ``git status --porcelain`` — deleções/modificações no snapshot imutável são
   erro. (A verificação criptográfica completa é feita por
   ``generate_baseline_manifest.py --verify``, que exige LFS.)

Uso:
    python scripts/data/check_repo_hygiene.py

Exit codes: 0 = higiene OK; 1 = violação encontrada (detalhes em stdout).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXCLUDED_DIRS = {".git", ".venv", ".claude"}
SYNC_ARTIFACT_MARKER = " 2"


def _git(*args: str) -> str:
    """Executa um comando git na raiz do projeto e retorna stdout."""
    result = subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def check_tracked_artifacts() -> list[str]:
    """Caminhos rastreados cujo nome contém o marcador de conflito ' 2'."""
    tracked = _git("ls-files").splitlines()
    return [path for path in tracked if SYNC_ARTIFACT_MARKER in path]


def check_working_tree_artifacts() -> list[str]:
    """Arquivos/diretórios ' 2' presentes na working tree (fora dos excluídos)."""
    found: list[str] = []
    for path in PROJECT_ROOT.rglob(f"*{SYNC_ARTIFACT_MARKER}*"):
        relative = path.relative_to(PROJECT_ROOT)
        if relative.parts and relative.parts[0] in EXCLUDED_DIRS:
            continue
        if SYNC_ARTIFACT_MARKER in path.name:
            found.append(str(relative))
    return sorted(found)


def check_baseline_clean() -> list[str]:
    """Entradas de `git status` dentro do baseline imutável (deve ser vazio)."""
    status = _git("status", "--porcelain", "--", "baseline_tcc_2025/")
    return [line for line in status.splitlines() if line.strip()]


def main() -> int:
    violations = 0

    tracked = check_tracked_artifacts()
    if tracked:
        violations += 1
        print(f"ERRO: {len(tracked)} caminho(s) rastreado(s) com marcador ' 2':")
        for path in tracked:
            print(f"  - {path}")

    working = check_working_tree_artifacts()
    if working:
        violations += 1
        print(
            f"ERRO: {len(working)} artefato(s) de sincronização ' 2' na working "
            "tree (compare com o original via diff antes de remover):"
        )
        for path in working[:20]:
            print(f"  - {path}")
        if len(working) > 20:
            print(f"  ... e mais {len(working) - 20}")

    baseline = check_baseline_clean()
    if baseline:
        violations += 1
        print(
            "ERRO: baseline_tcc_2025/ tem modificações na working tree "
            "(o snapshot é imutável — restaure com `git restore -- baseline_tcc_2025/`):"
        )
        for line in baseline[:20]:
            print(f"  {line}")

    if violations:
        print(f"\nHigiene do repositório REPROVADA ({violations} categoria(s) de violação).")
        return 1

    print("Higiene do repositório OK: sem artefatos ' 2' e baseline limpo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
