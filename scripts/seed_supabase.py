#!/usr/bin/env python3
"""Seed script: carrega dados existentes do CSV para o Supabase.

Importa:
- commits_with_refactoring.csv -> tabela commits
- llm_models estáticos (8 modelos do TCC)
- prompt_versions (v1.0-tcc, v2.0-mestrado)

Uso:
    python scripts/seed_supabase.py

Requer SUPABASE_URL e SUPABASE_SERVICE_KEY no .env ou variáveis de ambiente.

Refs: ARCHITECTURE_PLAN.md Phase 11.1 (Seed de dados existentes)
"""

import sys
import os
from pathlib import Path

# Garantir imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from src.core.settings import settings
from src.persistence.supabase_client import SupabaseClient


def seed_commits(
    client: SupabaseClient,
    csv_path: str = "csv/commits_with_refactoring.csv",
) -> tuple[int, list[str]]:
    """Carrega commits do CSV para a tabela commits.

    Idempotente por construção (upsert com on_conflict). Falha em um
    registro não aborta o lote: o hash é acumulado e reportado ao final.

    Returns:
        (commits carregados, hashes que falharam)
    """
    if not os.path.exists(csv_path):
        print(f"CSV não encontrado: {csv_path}")
        return 0, []

    df = pd.read_csv(csv_path)
    print(f"Carregando {len(df)} commits de {csv_path}...")

    count = 0
    failed: list[str] = []
    for _, row in df.iterrows():
        commit_hash = str(row.get("commit2", ""))
        result = client.upsert_commit(
            commit_hash_current=commit_hash,
            commit_hash_before=str(row.get("commit1", "")),
            repository_url=str(row.get("project", "")),
            project_name=str(row.get("project_name", "")),
        )
        if result:
            count += 1
        else:
            failed.append(commit_hash)
        if count % 500 == 0 and count > 0:
            print(f"  {count} commits carregados...")

    print(f"Total: {count} commits carregados, {len(failed)} falhas")
    return count, failed


def seed_models(client: SupabaseClient) -> tuple[int, list[str]]:
    """Registra os modelos usados no TCC."""
    models = [
        {"name": "mistral:latest", "family": "mistral", "parameter_count": "7B"},
        {"name": "deepseek-r1:1.5b", "family": "deepseek", "parameter_count": "1.5B"},
        {"name": "deepseek-r1:8b", "family": "deepseek", "parameter_count": "8B"},
        {"name": "gemma2:2b", "family": "gemma", "parameter_count": "2B"},
        {"name": "gemma3:1b", "family": "gemma", "parameter_count": "1B"},
        {"name": "gemma3:4b", "family": "gemma", "parameter_count": "4B"},
        {"name": "gpt-oss:20b", "family": "gpt-oss", "parameter_count": "20B"},
        {"name": "mistral", "family": "mistral", "parameter_count": "7B"},
    ]

    count = 0
    failed: list[str] = []
    for m in models:
        result = client.get_or_create_model(**m)
        if result:
            count += 1
            print(f"  Modelo registrado: {m['name']}")
        else:
            failed.append(m["name"])

    print(f"Total: {count} modelos registrados, {len(failed)} falhas")
    return count, failed


def seed_prompt_versions(client: SupabaseClient) -> tuple[int, list[str]]:
    """Registra as versões de prompt usadas."""
    from src.core.config import LLM_PROMPT
    from src.analyzers.optimized_prompt import OPTIMIZED_LLM_PROMPT

    prompts = [
        {
            "version_tag": "v1.0-tcc",
            "system_prompt": LLM_PROMPT,
            "description": "Prompt original do TCC (config.py LLM_PROMPT)",
        },
        {
            "version_tag": "v2.0-mestrado",
            "system_prompt": OPTIMIZED_LLM_PROMPT,
            "description": "Prompt otimizado para mestrado (optimized_prompt.py)",
        },
    ]

    count = 0
    failed: list[str] = []
    for p in prompts:
        result = client.get_or_create_prompt_version(**p)
        if result:
            count += 1
            print(f"  Prompt registrado: {p['version_tag']}")
        else:
            failed.append(p["version_tag"])

    print(f"Total: {count} versões de prompt registradas, {len(failed)} falhas")
    return count, failed


def main():
    if not settings.supabase_enabled:
        print("ERRO: SUPABASE_URL e SUPABASE_SERVICE_KEY devem estar configurados.")
        print("Configure no .env ou variáveis de ambiente.")
        sys.exit(1)

    print("=== Seed Supabase ===\n")
    client = SupabaseClient(settings.supabase_url, settings.supabase_service_key)

    _, failed_models = seed_models(client)
    print()
    _, failed_prompts = seed_prompt_versions(client)
    print()
    _, failed_commits = seed_commits(client)

    failures = {
        "modelos": failed_models,
        "prompts": failed_prompts,
        "commits": failed_commits,
    }
    total_failures = sum(len(v) for v in failures.values())
    if total_failures:
        print(f"\n=== Seed concluído com {total_failures} falha(s) ===")
        for category, items in failures.items():
            if items:
                shown = ", ".join(items[:10])
                suffix = f" ... e mais {len(items) - 10}" if len(items) > 10 else ""
                print(f"  {category}: {shown}{suffix}")
        print("Reexecute o seed (idempotente) após restabelecer a conexão.")
        sys.exit(1)

    print("\n=== Seed concluído sem falhas ===")


if __name__ == "__main__":
    main()
