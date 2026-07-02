"""Recomputação retroativa da convergência Purity×LLM (Fase E2, VAL-1).

Contexto: até a correção da Fase E2, o resumo de sessão comparava o rótulo do
LLM (PURE/FLOSS) com os literais 'TRUE'/'FALSE' — toda sessão persistida
reporta ``convergence_analysis`` com 0 agree. Os registros POR COMMIT estão
corretos; apenas o agregado estava errado. Este script recomputa a
convergência de cada JSON de sessão com a fonte única atual
(``summarize_convergence``: TRUE↔PURE, FALSE↔FLOSS, sem veredito →
not_comparable) e reporta antes/depois.

Os arquivos de sessão NUNCA são modificados (dados históricos são imutáveis);
a tabela corrigida sai em ``output/audits/``.

Uso:
    python scripts/research/recompute_convergence.py [caminhos...]
    # sem argumentos: varre output/models/*/analises/*.json

Exit code: 0 na execução normal; 2 se nenhum arquivo de sessão foi achado.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.classification import summarize_convergence  # noqa: E402
from src.utils.timeutils import utc_now_stamp  # noqa: E402


def recompute_session(data: dict) -> dict | None:
    """Recomputa a convergência de um dict de sessão; None se não aplicável."""
    analyses = data.get("detailed_analyses") or data.get("analyses")
    if not isinstance(analyses, list) or not analyses:
        return None
    recomputed = summarize_convergence(
        (a.get("purity_classification"), a.get("llm_classification"))
        for a in analyses
        if isinstance(a, dict)
    )
    recorded = (data.get("summary") or {}).get("convergence_analysis") or {}
    return {
        "total_analyses": len(analyses),
        "recorded_agree": recorded.get("agree", ""),
        "recorded_disagree": recorded.get("disagree", ""),
        "recomputed_agree": recomputed["agree"],
        "recomputed_disagree": recomputed["disagree"],
        "recomputed_not_comparable": recomputed["not_comparable"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "paths", nargs="*", type=Path,
        help="JSONs de sessão (default: output/models/*/analises/*.json)",
    )
    args = parser.parse_args(argv)

    targets: list[Path] = []
    for p in args.paths:
        if p.is_dir():
            targets.extend(sorted(p.rglob("*.json")))
        elif p.is_file():
            targets.append(p)
    if not args.paths:
        models_dir = PROJECT_ROOT / "output" / "models"
        if models_dir.is_dir():
            targets = sorted(models_dir.glob("*/analises/*.json"))

    if not targets:
        print("Nenhum JSON de sessão encontrado.")
        return 2

    rows: list[dict] = []
    for path in targets:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        result = recompute_session(data)
        if result is None:
            continue
        result["file"] = (
            str(path.relative_to(PROJECT_ROOT))
            if path.is_relative_to(PROJECT_ROOT)
            else str(path)
        )
        rows.append(result)
        print(
            f"  {path.name}: registrado agree={result['recorded_agree']!s:>4} "
            f"disagree={result['recorded_disagree']!s:>4} -> recomputado "
            f"agree={result['recomputed_agree']} "
            f"disagree={result['recomputed_disagree']} "
            f"not_comparable={result['recomputed_not_comparable']}"
        )

    if not rows:
        print("Nenhuma sessão com bloco de análises encontrado.")
        return 2

    out_dir = PROJECT_ROOT / "output" / "audits"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"convergence_recompute_{utc_now_stamp()}.csv"
    fieldnames = [
        "file", "total_analyses",
        "recorded_agree", "recorded_disagree",
        "recomputed_agree", "recomputed_disagree", "recomputed_not_comparable",
    ]
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n{len(rows)} sessão(ões) recomputada(s). Tabela: {out_path}")
    print("Os arquivos de sessão originais permanecem intocados (política de imutabilidade).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
