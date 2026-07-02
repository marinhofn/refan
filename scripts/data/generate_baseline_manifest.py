#!/usr/bin/env python3
"""Gera e verifica o manifesto SHA256 do baseline imutável do TCC.

O diretório baseline_tcc_2025/ é o snapshot de referência dos resultados
do TCC (set/2025), base de comparação dos experimentos do mestrado. O
manifesto (MANIFEST.sha256) registra o hash de cada arquivo e prova a
integridade do snapshot independentemente do mecanismo de armazenamento
(Git LFS, backup externo ou cópia local) — HARDENING_PLAN.md, Fase H7.

Uso:
    python scripts/data/generate_baseline_manifest.py            # gera
    python scripts/data/generate_baseline_manifest.py --verify   # verifica

Formato (compatível com `shasum -a 256 -c`):
    <sha256 hex>  <caminho relativo ao baseline>

Exit codes (--verify): 0 íntegro; 1 divergência/arquivo faltando; 2 sem manifesto.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

BASELINE_DIR = Path(__file__).resolve().parents[2] / "baseline_tcc_2025"
MANIFEST_NAME = "MANIFEST.sha256"


def _iter_baseline_files(baseline_dir: Path):
    """Arquivos do baseline em ordem determinística, excluindo o manifesto."""
    for path in sorted(baseline_dir.rglob("*")):
        if path.is_file() and path.name != MANIFEST_NAME and path.name != ".DS_Store":
            yield path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def generate(baseline_dir: Path) -> int:
    manifest_path = baseline_dir / MANIFEST_NAME
    lines = []
    for path in _iter_baseline_files(baseline_dir):
        rel = path.relative_to(baseline_dir)
        lines.append(f"{_sha256(path)}  {rel}")
    manifest_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Manifesto gerado: {manifest_path} ({len(lines)} arquivos)")
    return 0


def verify(baseline_dir: Path) -> int:
    manifest_path = baseline_dir / MANIFEST_NAME
    if not manifest_path.exists():
        print(f"ERRO: manifesto não encontrado: {manifest_path}")
        return 2

    expected: dict[str, str] = {}
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            digest, rel = line.split("  ", 1)
            expected[rel] = digest

    actual = {
        str(p.relative_to(baseline_dir)): _sha256(p)
        for p in _iter_baseline_files(baseline_dir)
    }

    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))
    mismatched = sorted(
        rel for rel in set(expected) & set(actual) if expected[rel] != actual[rel]
    )

    if not (missing or extra or mismatched):
        print(f"Baseline íntegro: {len(actual)} arquivos conferem com o manifesto.")
        return 0

    for rel in missing:
        print(f"FALTANDO:   {rel}")
    for rel in extra:
        print(f"NÃO LISTADO: {rel}")
    for rel in mismatched:
        print(f"DIVERGENTE: {rel}")
    print(
        f"\nERRO: {len(missing)} faltando, {len(extra)} não listados, "
        f"{len(mismatched)} divergentes. O baseline deve ser imutável — "
        f"investigue antes de qualquer ação."
    )
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--verify", action="store_true", help="Verifica em vez de gerar")
    parser.add_argument(
        "--baseline-dir", default=str(BASELINE_DIR),
        help="Diretório do baseline (default: baseline_tcc_2025/ na raiz)",
    )
    args = parser.parse_args()

    baseline_dir = Path(args.baseline_dir)
    if not baseline_dir.is_dir():
        print(f"ERRO: diretório não encontrado: {baseline_dir}")
        return 2

    return verify(baseline_dir) if args.verify else generate(baseline_dir)


if __name__ == "__main__":
    sys.exit(main())
