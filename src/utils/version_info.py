"""Identificação da versão da ferramenta para rastreabilidade de resultados.

Cada resultado de análise deve ser rastreável ao commit exato do Refan
que o produziu (HARDENING_PLAN.md, Fase H5). A versão é obtida via
`git describe --tags --always --dirty`: tag mais próxima + hash curto,
com sufixo -dirty se a árvore de trabalho tiver modificações não
commitadas (sinaliza execução com código não auditável).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_cached_version: str | None = None


def get_tool_version() -> str:
    """Retorna a versão da ferramenta (git describe), com cache por processo.

    Fallback "unknown" quando o git não está disponível ou o código roda
    fora de um repositório (ex.: distribuição empacotada).
    """
    global _cached_version
    if _cached_version is not None:
        return _cached_version

    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--always", "--dirty"],
            cwd=_PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=5,
        )
        version = result.stdout.strip()
        _cached_version = version if result.returncode == 0 and version else "unknown"
    except Exception:
        _cached_version = "unknown"

    return _cached_version
