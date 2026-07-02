#!/usr/bin/env python3
"""Reconciliação entre os JSONL locais de sessão e o Supabase (somente leitura).

As duas camadas de persistência (JSONL crash-safe local e analysis_results
no cloud) podem divergir após quedas de rede no meio de uma sessão. Este
script audita a integridade entre elas antes da consolidação dos resultados
da pesquisa (HARDENING_PLAN.md, Fase H6):

- presentes apenas localmente (escrita cloud perdida — candidatos a
  sync_local_jsonl);
- presentes apenas no cloud (JSONL local removido ou de outro runner);
- classificação divergente para o mesmo (modelo, commit) — exige
  investigação manual; o script NUNCA corrige automaticamente.

Uso:
    python scripts/data/reconcile_supabase.py [--model mistral]

Exit code 1 quando há divergência de classificação; 0 caso contrário
(registros faltantes em um dos lados são reportados mas são esperados
em sessões interrompidas).

Requer SUPABASE_URL e SUPABASE_SERVICE_KEY configurados.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# Classificações que nunca são enviadas ao cloud
_LOCAL_ONLY_CLASSIFICATIONS = {"DRY_RUN", "FAILED"}


def load_local_records(
    output_root: str = "output/models", model: str | None = None
) -> dict[tuple[str, str], str]:
    """Carrega {(modelo, hash): classificação} dos JSONL de sessão locais.

    Em caso de hash repetido entre sessões, prevalece o registro mais
    recente (ordem lexicográfica dos nomes de arquivo = ordem temporal,
    pois os nomes embutem timestamp).
    """
    import json

    records: dict[tuple[str, str], str] = {}
    root = Path(output_root)
    if not root.is_dir():
        return records

    model_dirs = [root / model] if model else sorted(root.iterdir())
    for model_dir in model_dirs:
        sessions_dir = model_dir / "analises" / "sessions"
        if not sessions_dir.is_dir():
            continue
        for jsonl_path in sorted(sessions_dir.glob("*.jsonl")):
            with open(jsonl_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    commit_hash = rec.get("hash", "")
                    classification = str(rec.get("llm_classification", "")).upper()
                    if not commit_hash or classification in _LOCAL_ONLY_CLASSIFICATIONS:
                        continue
                    records[(model_dir.name, commit_hash)] = classification
    return records


def load_cloud_records(client, model: str | None = None) -> dict[tuple[str, str], str]:
    """Carrega {(modelo, hash): classificação} de analysis_results no Supabase.

    Usa embedding PostgREST para resolver as FKs de modelo e commit em uma
    única consulta. O nome do modelo é normalizado como nos diretórios
    locais (':' -> '_').
    """
    result = client.client.table("analysis_results").select(
        "classification, llm_models(name), commits(commit_hash_current)"
    ).execute()

    records: dict[tuple[str, str], str] = {}
    for row in result.data or []:
        model_name = ((row.get("llm_models") or {}).get("name") or "").replace(":", "_")
        commit_hash = (row.get("commits") or {}).get("commit_hash_current") or ""
        classification = str(row.get("classification", "")).upper()
        if not model_name or not commit_hash:
            continue
        if model and model_name != model:
            continue
        if classification in _LOCAL_ONLY_CLASSIFICATIONS:
            continue
        records[(model_name, commit_hash)] = classification
    return records


def reconcile(
    local: dict[tuple[str, str], str], cloud: dict[tuple[str, str], str]
) -> dict[str, list]:
    """Compara os dois conjuntos e classifica as diferenças."""
    local_keys, cloud_keys = set(local), set(cloud)
    divergent = [
        {"model": k[0], "hash": k[1], "local": local[k], "cloud": cloud[k]}
        for k in sorted(local_keys & cloud_keys)
        if local[k] != cloud[k]
    ]
    return {
        "local_only": sorted(local_keys - cloud_keys),
        "cloud_only": sorted(cloud_keys - local_keys),
        "divergent": divergent,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", default=None, help="Restringir a um modelo (nome do diretório em output/models)")
    parser.add_argument("--output-root", default="output/models", help="Raiz dos outputs locais")
    args = parser.parse_args()

    from src.core.settings import settings
    from src.persistence.supabase_client import SupabaseClient

    if not settings.supabase_enabled:
        print("ERRO: SUPABASE_URL e SUPABASE_SERVICE_KEY devem estar configurados.")
        return 2

    client = SupabaseClient(settings.supabase_url, settings.supabase_service_key)

    local = load_local_records(args.output_root, args.model)
    cloud = load_cloud_records(client, args.model)
    report = reconcile(local, cloud)

    print(f"Registros locais (JSONL):  {len(local)}")
    print(f"Registros no Supabase:     {len(cloud)}")
    print(f"Apenas locais:             {len(report['local_only'])}")
    print(f"Apenas no cloud:           {len(report['cloud_only'])}")
    print(f"Classificação divergente:  {len(report['divergent'])}")

    if report["local_only"]:
        print("\n-- Apenas locais (candidatos a sync_local_jsonl) --")
        for model_name, commit_hash in report["local_only"][:20]:
            print(f"  {model_name}  {commit_hash}")
        if len(report["local_only"]) > 20:
            print(f"  ... e mais {len(report['local_only']) - 20}")

    if report["divergent"]:
        print("\n-- DIVERGENTES (investigação manual obrigatória) --")
        for d in report["divergent"]:
            print(f"  {d['model']}  {d['hash']}  local={d['local']}  cloud={d['cloud']}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
