"""refan doctor — diagnóstico de prontidão para uma sessão reprodutível.

Fase E3 (EVOLUTION_PLAN.md): consolida em um comando as pré-condições que o
protocolo experimental exige antes de qualquer sessão de análise. Cada check
é uma função pura que retorna :class:`CheckResult`; o comando agrega e sai
com código != 0 se qualquer check obrigatório falhar.

Checks:
1. higiene do repositório (artefatos de sync, baseline limpo) — via script;
2. artefato de prompt da tag ativa existe e é o que o código executa;
3. Ollama respondendo (/api/version);
4. modelo ativo presente no Ollama com digest resolvível (REP-1);
5. Supabase: configurado e acessível (INFO quando em modo local-only);
6. espaço em disco para clones/saídas;
7. (--full) verificação criptográfica do manifesto do baseline (exige LFS).
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import requests

from src.core.settings import settings as _settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MIN_FREE_DISK_GB = 5.0


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str  # "OK" | "FAIL" | "WARN" | "INFO"
    detail: str

    @property
    def is_failure(self) -> bool:
        return self.status == "FAIL"


def check_repo_hygiene() -> CheckResult:
    """Sem artefatos ' 2' e baseline com working tree limpa."""
    script = PROJECT_ROOT / "scripts" / "data" / "check_repo_hygiene.py"
    result = subprocess.run(
        [sys.executable, str(script)], capture_output=True, text=True
    )
    if result.returncode == 0:
        return CheckResult("higiene do repositório", "OK", "sem artefatos ' 2'; baseline limpo")
    detail = (result.stdout or result.stderr).strip().splitlines()
    return CheckResult("higiene do repositório", "FAIL", detail[0] if detail else "violação")


def check_prompt_artifact() -> CheckResult:
    """O artefato da tag ativa existe e é exatamente o prompt executado."""
    tag = _settings.prompt_version_tag
    artifact = PROJECT_ROOT / "configs" / "prompts" / f"{tag}.txt"
    if not artifact.is_file():
        return CheckResult(
            "artefato de prompt", "FAIL",
            f"configs/prompts/{tag}.txt inexistente para REFAN_PROMPT_VERSION={tag}",
        )
    from src.analyzers.optimized_prompt import OPTIMIZED_LLM_PROMPT

    executing = hashlib.sha256(OPTIMIZED_LLM_PROMPT.encode()).hexdigest()
    registered = hashlib.sha256(artifact.read_bytes()).hexdigest()
    if executing != registered:
        return CheckResult(
            "artefato de prompt", "FAIL",
            f"o código executa um prompt DIFERENTE de configs/prompts/{tag}.txt "
            f"({executing[:12]}... != {registered[:12]}...) — proveniência inválida (VAL-4)",
        )
    return CheckResult("artefato de prompt", "OK", f"{tag} sha256 {executing[:12]}...")


def check_ollama_up() -> CheckResult:
    base = _settings.ollama_host.split("/api/")[0]
    try:
        resp = requests.get(f"{base}/api/version", timeout=5)
        resp.raise_for_status()
        version = resp.json().get("version", "?")
        return CheckResult("ollama", "OK", f"respondendo em {base} (v{version})")
    except Exception as e:
        return CheckResult("ollama", "FAIL", f"sem resposta em {base}: {e}")


def check_model_digest(model: str | None = None) -> CheckResult:
    """Modelo presente no Ollama local com digest resolvível (REP-1)."""
    from src.handlers.llm_handler import OllamaAdapter

    name = model or _settings.llm_model
    adapter = OllamaAdapter(_settings.ollama_host, name)
    info = adapter.get_model_info()
    if not info or not info.get("digest"):
        return CheckResult(
            "modelo + digest", "FAIL",
            f"'{name}' sem digest resolvível — ollama pull {name}?",
        )
    return CheckResult(
        "modelo + digest", "OK",
        f"{info['model']} digest {info['digest'][:19]}...",
    )


def check_supabase() -> CheckResult:
    if not _settings.supabase_enabled:
        return CheckResult(
            "supabase", "INFO",
            "não configurado — modo local-only (JSONL/CSV); configure .env para sync cloud",
        )
    try:
        from src.persistence.supabase_client import SupabaseClient

        client = SupabaseClient(_settings.supabase_url, _settings.supabase_service_key)
        client.get_prompt_version(_settings.prompt_version_tag)  # SELECT leve
        return CheckResult("supabase", "OK", f"acessível ({_settings.supabase_url})")
    except Exception as e:
        return CheckResult("supabase", "FAIL", f"configurado mas inacessível: {e}")


def check_disk_space() -> CheckResult:
    usage = shutil.disk_usage(PROJECT_ROOT)
    free_gb = usage.free / (1024**3)
    if free_gb < MIN_FREE_DISK_GB:
        return CheckResult(
            "disco", "WARN",
            f"apenas {free_gb:.1f} GB livres (< {MIN_FREE_DISK_GB} GB) — clones podem falhar",
        )
    return CheckResult("disco", "OK", f"{free_gb:.1f} GB livres")


def check_baseline_manifest_full() -> CheckResult:
    """Verificação criptográfica completa do baseline (exige objetos LFS)."""
    script = PROJECT_ROOT / "scripts" / "data" / "generate_baseline_manifest.py"
    result = subprocess.run(
        [sys.executable, str(script), "--verify"], capture_output=True, text=True
    )
    tail = (result.stdout or result.stderr).strip().splitlines()
    detail = tail[-1] if tail else ""
    status = "OK" if result.returncode == 0 else "FAIL"
    return CheckResult("manifesto do baseline", status, detail)


def run_doctor(model: str | None = None, full: bool = False) -> int:
    """Executa todos os checks e imprime o relatório. Exit code: 0/1."""
    checks = [
        check_repo_hygiene(),
        check_prompt_artifact(),
        check_ollama_up(),
        check_model_digest(model),
        check_supabase(),
        check_disk_space(),
    ]
    if full:
        checks.append(check_baseline_manifest_full())

    icon = {"OK": "✅", "FAIL": "❌", "WARN": "⚠️ ", "INFO": "ℹ️ "}
    print("\nrefan doctor — prontidão para sessão reprodutível\n" + "=" * 52)
    for check in checks:
        print(f"{icon.get(check.status, '?')} {check.name:24s} {check.detail}")
    failures = [c for c in checks if c.is_failure]
    print("=" * 52)
    if failures:
        print(f"REPROVADO: {len(failures)} check(s) obrigatório(s) falharam.")
        return 1
    print("PRONTO: pré-condições de sessão reprodutível satisfeitas.")
    return 0
