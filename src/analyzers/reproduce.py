"""refan reproduce — verificação executável de reprodutibilidade de sessão.

Fase E3 (EVOLUTION_PLAN.md): materializa o procedimento do
docs/REPRODUCIBILITY.md §3 em um comando. Dado o JSONL de uma sessão:

1. verifica que o AMBIENTE atual corresponde ao registrado (hash do prompt,
   versão da ferramenta, digest do modelo — REP-1);
2. re-executa os mesmos commits em uma cópia ISOLADA (CSV master temporário,
   JSONL temporário, sem Supabase — reprodução não é coleta);
3. compara classificação a classificação e reporta divergências.

Com seed fixo, mesmo digest de modelo e mesma versão da ferramenta, espera-se
concordância de 100%; qualquer divergência é evidência de irreprodutibilidade
a investigar ANTES de usar os dados. Sessões pré-E3 (sem digest registrado)
recebem aviso explícito — a identidade dos pesos não é verificável.
"""

from __future__ import annotations

import csv
import json
import tempfile
from pathlib import Path

from src.utils.colors import dim, error, header, info, success, warning

VERDICTS = ("PURE", "FLOSS")


def load_session_records(path: Path) -> list[dict]:
    """Carrega registros do JSONL de sessão (linhas inválidas são reportadas)."""
    records: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for line_number, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                print(warning(f"Linha {line_number} inválida em {path.name} — ignorada"))
    return records


def verify_environment(records: list[dict], current_prompt_sha256: str,
                       current_tool_version: str, current_model_digest: str | None) -> tuple[bool, list[str]]:
    """Compara o ambiente atual com o registrado na sessão.

    Returns:
        (pode_prosseguir, mensagens). Divergência de prompt é BLOQUEANTE
        (outra condição experimental); tool_version/digest divergentes são
        bloqueantes quando registrados; ausências históricas viram aviso.
    """
    messages: list[str] = []
    ok = True

    recorded_prompts = {r.get("prompt_sha256") for r in records if r.get("prompt_sha256")}
    if not recorded_prompts:
        messages.append("AVISO: sessão sem prompt_sha256 registrado (pré-H5) — comparação de prompt impossível")
    elif recorded_prompts != {current_prompt_sha256}:
        ok = False
        messages.append(
            f"BLOQUEANTE: prompt atual ({current_prompt_sha256[:12]}...) difere do registrado "
            f"({', '.join(p[:12] + '...' for p in recorded_prompts)}) — outra condição experimental"
        )

    recorded_tools = {r.get("tool_version") for r in records if r.get("tool_version")}
    if recorded_tools and recorded_tools != {current_tool_version}:
        ok = False
        messages.append(
            f"BLOQUEANTE: tool_version atual ({current_tool_version}) difere do registrado "
            f"({', '.join(sorted(recorded_tools))}) — faça checkout da versão registrada"
        )

    recorded_digests = {r.get("model_digest") for r in records if r.get("model_digest")}
    if not recorded_digests:
        messages.append(
            "AVISO: sessão pré-E3 sem model_digest — a identidade dos pesos não é verificável "
            "(limitação documentada em docs/REPRODUCIBILITY.md)"
        )
    elif current_model_digest and recorded_digests != {current_model_digest}:
        ok = False
        messages.append(
            f"BLOQUEANTE: digest do modelo local ({current_model_digest[:19]}...) difere do registrado "
            f"({', '.join(d[:19] + '...' for d in recorded_digests)}) — pesos diferentes"
        )
    return ok, messages


def compare_classifications(original: list[dict], reproduced: list[dict]) -> dict:
    """Compara classificações por commit entre a sessão original e a reprodução."""
    original_by_hash = {
        r.get("hash", r.get("commit_hash_current")): r.get("llm_classification")
        for r in original
        if r.get("llm_classification") in VERDICTS
    }
    reproduced_by_hash = {
        r.get("hash", r.get("commit_hash_current")): r.get("llm_classification")
        for r in reproduced
    }
    matches: list[str] = []
    mismatches: list[tuple[str, str, str]] = []
    missing: list[str] = []
    for commit_hash, recorded in original_by_hash.items():
        new = reproduced_by_hash.get(commit_hash)
        if new is None:
            missing.append(commit_hash)
        elif new == recorded:
            matches.append(commit_hash)
        else:
            mismatches.append((commit_hash, recorded, new))
    return {"matches": matches, "mismatches": mismatches, "missing": missing,
            "total_comparable": len(original_by_hash)}


def run_reproduction(session_path: str, model: str | None = None,
                     limit: int | None = None, analyzer_factory=None) -> int:
    """Executa a reprodução completa. Exit code: 0 = 100% concordância."""
    path = Path(session_path)
    if not path.is_file():
        print(error(f"Sessão não encontrada: {path}"))
        return 2

    records = load_session_records(path)
    verdict_records = [r for r in records if r.get("llm_classification") in VERDICTS]
    if not verdict_records:
        print(error("A sessão não contém registros com veredito (PURE/FLOSS) para reproduzir."))
        return 2
    if limit:
        verdict_records = verdict_records[:limit]

    # --- ambiente atual ---
    import hashlib
    from src.analyzers.optimized_prompt import OPTIMIZED_LLM_PROMPT
    from src.utils.version_info import get_tool_version
    from src.handlers.llm_handler import LLMHandler

    current_prompt = hashlib.sha256(OPTIMIZED_LLM_PROMPT.encode()).hexdigest()
    current_tool = get_tool_version()
    handler_for_info = LLMHandler(model=model)
    model_info = handler_for_info.get_model_info()
    current_digest = (model_info or {}).get("digest")

    ok, messages = verify_environment(verdict_records, current_prompt, current_tool, current_digest)
    print(header("\nVerificação de ambiente"))
    for message in messages:
        print(warning(f"  {message}") if message.startswith("AVISO") else error(f"  {message}"))
    if not messages:
        print(success("  ambiente idêntico ao registrado"))
    if not ok:
        print(error("\nReprodução abortada: o ambiente atual não corresponde ao da sessão."))
        return 1

    # --- re-execução isolada ---
    with tempfile.TemporaryDirectory(prefix="refan_reproduce_") as tmp:
        tmp_dir = Path(tmp)
        master = tmp_dir / "reproduce_master.csv"
        with master.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["hash", "purity_analysis", "llm_analysis"])
            for r in verdict_records:
                writer.writerow([
                    r.get("hash", r.get("commit_hash_current")),
                    r.get("purity_classification", ""),
                    "",
                ])

        if analyzer_factory is None:
            from src.analyzers.llm_purity_analyzer import LLMPurityAnalyzer

            def analyzer_factory(csv_path):  # noqa: F811 — default factory
                analyzer = LLMPurityAnalyzer(model=model, csv_file_path=csv_path)
                # Reprodução é local e efêmera: nada de cloud, nada de
                # controle remoto, artefatos no diretório temporário.
                analyzer.supabase = None
                analyzer.command_handler = None
                analyzer.backup_dir = str(tmp_dir)
                analyzer.session_log_file = None
                return analyzer

        analyzer = analyzer_factory(str(master))
        print(info(f"\nReproduzindo {len(verdict_records)} análise(s) em ambiente isolado..."))
        analyzer.analyze_commits(max_commits=limit)

        reproduced: list[dict] = []
        sessions_dir = Path(analyzer.backup_dir) / "sessions"
        if sessions_dir.is_dir():
            for jsonl in sorted(sessions_dir.glob("*.jsonl")):
                reproduced.extend(load_session_records(jsonl))

    report = compare_classifications(verdict_records, reproduced)
    print(header("\nResultado da reprodução"))
    print(info(f"  comparáveis: {report['total_comparable']}"))
    print(success(f"  concordantes: {len(report['matches'])}"))
    if report["mismatches"]:
        print(error(f"  DIVERGENTES: {len(report['mismatches'])}"))
        for commit_hash, old, new in report["mismatches"][:10]:
            print(error(f"    {commit_hash[:12]}...: registrado {old} -> reproduzido {new}"))
    if report["missing"]:
        print(warning(f"  não reproduzidos (falha/skip): {len(report['missing'])}"))

    if report["mismatches"] or report["missing"]:
        print(error("\nIRREPRODUTÍVEL: investigue antes de usar os dados (docs/REPRODUCIBILITY.md)."))
        return 1
    print(success("\nREPRODUTÍVEL: 100% de concordância com a sessão registrada."))
    return 0
