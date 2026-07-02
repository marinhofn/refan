"""Auditoria retroativa da proveniência de vereditos (Fase E2, VAL-2/VAL-3).

Contexto: até a série v2.1, `extraction_method` não era persistido e, quando o
parse falhava, uma heurística de palavras-chave fabricava o rótulo. Este
script reprocessa OFFLINE (sem LLM, sem rede) o `llm_raw_response` armazenado
em cada registro histórico e classifica de onde o veredito teria vindo no
pipeline atual:

- ``final_pattern+json``  — linha FINAL: e JSON válido concordantes;
- ``final_pattern``       — apenas a linha FINAL:;
- ``json``                — apenas JSON com refactoring_type válido;
- ``no_verdict``          — nem FINAL: nem JSON válido. **Nas séries <= v2.1
  estes registros receberam rótulo da heurística de keywords ou de defaults —
  são os candidatos a exclusão nas análises da dissertação**;
- ``empty_response``      — resposta bruta vazia/ausente (irrecuperável).

Fontes aceitas: arquivos ``.jsonl`` (sessões incrementais) e ``.json`` de
sessão (lista em ``detailed_analyses``/``analyses`` ou lista raiz). Os arquivos de entrada NUNCA
são modificados; o relatório sai em ``output/audits/``.

Uso:
    python scripts/research/audit_extraction_methods.py [caminhos...]
    # sem argumentos: varre output/models/*/analises/{sessions/*.jsonl,*.json}

Exit code: 0 sempre que a auditoria executa (presença de no_verdict não é
erro do script — é achado).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.classification import extract_final_classification  # noqa: E402
from src.utils.json_parser import extract_classification_json  # noqa: E402
from src.utils.timeutils import utc_now_stamp  # noqa: E402

CATEGORIES = (
    "final_pattern+json",
    "final_pattern",
    "json",
    "no_verdict",
    "empty_response",
)


def classify_extraction(raw_response: str | None) -> str:
    """Classifica a proveniência do veredito reprocessando a resposta bruta."""
    if raw_response is None or not str(raw_response).strip():
        return "empty_response"
    text = str(raw_response)
    final = extract_final_classification(text)
    parsed = extract_classification_json(text)
    if final and parsed:
        return "final_pattern+json"
    if final:
        return "final_pattern"
    if parsed:
        return "json"
    return "no_verdict"


def iter_records(path: Path):
    """Itera registros de análise de um arquivo .jsonl ou .json de sessão."""
    if path.suffix == ".jsonl":
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return
    if isinstance(data, list):
        records = data
    elif isinstance(data, dict):
        records = (
            data.get("detailed_analyses")
            or data.get("analyses")
            or data.get("results")
            or []
        )
    else:
        records = []
    for record in records:
        if isinstance(record, dict):
            yield record


def audit_file(path: Path) -> tuple[Counter, list[dict]]:
    """Audita um arquivo; retorna (contagens, linhas detalhadas)."""
    counts: Counter = Counter()
    rows: list[dict] = []
    for record in iter_records(path):
        raw = record.get("llm_raw_response")
        category = classify_extraction(raw)
        counts[category] += 1
        rows.append(
            {
                "file": str(path.relative_to(PROJECT_ROOT)) if path.is_relative_to(PROJECT_ROOT) else str(path),
                "commit_hash": record.get(
                    "hash", record.get("commit_hash_current", "")
                ),
                "recorded_classification": record.get(
                    "llm_classification", record.get("refactoring_type", "")
                ),
                "recorded_extraction_method": record.get("extraction_method", ""),
                "reprocessed_extraction": category,
            }
        )
    return counts, rows


def discover_default_paths() -> list[Path]:
    paths: list[Path] = []
    models_dir = PROJECT_ROOT / "output" / "models"
    if models_dir.is_dir():
        paths.extend(sorted(models_dir.glob("*/analises/sessions/*.jsonl")))
        paths.extend(sorted(models_dir.glob("*/analises/*.json")))
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "paths", nargs="*", type=Path,
        help="Arquivos/diretórios a auditar (default: output/models/**)",
    )
    args = parser.parse_args(argv)

    targets: list[Path] = []
    for p in args.paths:
        if p.is_dir():
            targets.extend(sorted(p.rglob("*.jsonl")))
            targets.extend(sorted(p.rglob("*.json")))
        elif p.is_file():
            targets.append(p)
    if not args.paths:
        targets = discover_default_paths()

    if not targets:
        print("Nenhum arquivo de sessão encontrado para auditar.")
        return 0

    total: Counter = Counter()
    all_rows: list[dict] = []
    print(f"Auditando {len(targets)} arquivo(s)...\n")
    for path in targets:
        counts, rows = audit_file(path)
        if not rows:
            continue
        total.update(counts)
        all_rows.extend(rows)
        n = sum(counts.values())
        fabricated = counts.get("no_verdict", 0) + counts.get("empty_response", 0)
        print(f"  {path.name}: {n} registros | sem veredito real: {fabricated}")

    n_total = sum(total.values())
    if n_total == 0:
        print("Nenhum registro com llm_raw_response encontrado.")
        return 0

    print("\n===== RESUMO GERAL =====")
    for category in CATEGORIES:
        count = total.get(category, 0)
        print(f"  {category:22s} {count:6d}  ({count / n_total:6.1%})")
    suspect = total.get("no_verdict", 0) + total.get("empty_response", 0)
    print(
        f"\nRegistros cujo rótulo histórico NÃO veio de veredito explícito do "
        f"modelo: {suspect} de {n_total} ({suspect / n_total:.1%}).\n"
        f"Em séries <= v2.1 esses rótulos foram fabricados por heurística/"
        f"defaults — trate-os como exclusão candidata (ameaças à validade)."
    )

    out_dir = PROJECT_ROOT / "output" / "audits"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"extraction_audit_{utc_now_stamp()}.csv"
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(all_rows[0].keys()))
        writer.writeheader()
        writer.writerows(all_rows)
    print(f"\nDetalhe por registro: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
