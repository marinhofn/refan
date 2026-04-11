"""Interface de linha de comando para o Refan.

Permite execução headless/scriptável das funcionalidades que antes
só estavam disponíveis via menus interativos.

Uso:
    python refan.py analyze --model mistral --limit 50 --skip-analyzed
    python refan.py analyze --model deepseek-r1:8b --filter TRUE
    python refan.py status --model mistral
    python refan.py merge-sessions --model mistral
    python refan.py interactive          # menu legado
    python refan.py interactive --menu llm

Refs: REFACTORING_PLAN.md Phase 7
"""

from __future__ import annotations

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    """Constrói o parser de argumentos da CLI."""
    parser = argparse.ArgumentParser(
        prog="refan",
        description="Refan — Classificação de refatorações com LLMs",
    )
    subparsers = parser.add_subparsers(dest="command", help="Comando a executar")

    # --- analyze ---
    p_analyze = subparsers.add_parser(
        "analyze",
        help="Executar análise LLM em commits",
    )
    p_analyze.add_argument(
        "--model", "-m",
        default=None,
        help="Modelo Ollama a usar (default: configuração atual)",
    )
    p_analyze.add_argument(
        "--csv",
        default=None,
        help="Caminho do CSV de entrada (default: CSV padrão do sistema)",
    )
    p_analyze.add_argument(
        "--limit", "-n",
        type=int,
        default=None,
        help="Número máximo de commits a analisar",
    )
    p_analyze.add_argument(
        "--skip-analyzed",
        action="store_true",
        default=True,
        help="Pular commits já analisados (default: True)",
    )
    p_analyze.add_argument(
        "--no-skip",
        action="store_true",
        help="Reanalisar todos os commits, incluindo já analisados",
    )
    p_analyze.add_argument(
        "--filter",
        choices=["TRUE", "FALSE", "NONE"],
        default=None,
        help="Filtrar por classificação Purity (TRUE/FALSE/NONE)",
    )
    p_analyze.add_argument(
        "--dry-run",
        action="store_true",
        help="Simular análise sem chamar o LLM",
    )

    # --- status ---
    p_status = subparsers.add_parser(
        "status",
        help="Mostrar progresso das análises",
    )
    p_status.add_argument(
        "--model", "-m",
        default=None,
        help="Modelo para consultar status",
    )
    p_status.add_argument(
        "--csv",
        default=None,
        help="Caminho do CSV para consultar",
    )

    # --- merge-sessions ---
    p_merge = subparsers.add_parser(
        "merge-sessions",
        help="Mergear sessões JSONL no CSV master",
    )
    p_merge.add_argument(
        "--model", "-m",
        default=None,
        help="Modelo cujas sessões serão mergeadas",
    )
    p_merge.add_argument(
        "--csv",
        default=None,
        help="Caminho do CSV master a atualizar",
    )

    # --- interactive ---
    p_interactive = subparsers.add_parser(
        "interactive",
        help="Iniciar menu interativo legado",
    )
    p_interactive.add_argument(
        "--menu",
        choices=["full", "llm"],
        default="full",
        help="Tipo de menu: full (completo) ou llm (especializado)",
    )

    return parser


def cmd_analyze(args: argparse.Namespace) -> int:
    """Executa análise LLM via CLI."""
    from src.core.config import set_llm_model, get_current_llm_model, ensure_model_directories
    from src.analyzers.llm_purity_analyzer import LLMPurityAnalyzer

    model = args.model or get_current_llm_model()
    set_llm_model(model)
    ensure_model_directories()

    skip = not args.no_skip
    analyzer = LLMPurityAnalyzer(
        model=model,
        csv_file_path=args.csv,
        dry_run=args.dry_run,
    )

    stats = analyzer.analyze_commits(
        max_commits=args.limit,
        skip_analyzed=skip,
        purity_filter=args.filter,
    )

    print(f"\nResultados: {stats.get('successful_analyses', 0)} sucesso, "
          f"{stats.get('failed_analyses', 0)} falhas, "
          f"{stats.get('skipped_already_analyzed', 0)} pulados")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Mostra progresso das análises."""
    from src.core.config import set_llm_model, get_current_llm_model, ensure_model_directories
    from src.analyzers.llm_purity_analyzer import LLMPurityAnalyzer

    model = args.model or get_current_llm_model()
    set_llm_model(model)
    ensure_model_directories()

    analyzer = LLMPurityAnalyzer(model=model, csv_file_path=args.csv)
    summary = analyzer.get_analysis_summary()

    if summary:
        total = summary["total_hashes"]
        done = summary["completed_analyses"]
        pending = summary["pending_analyses"]
        pct = (done / total * 100) if total > 0 else 0

        print(f"\nModelo: {model}")
        print(f"Total de commits: {total}")
        print(f"Analisados: {done} ({pct:.1f}%)")
        print(f"Pendentes: {pending}")

        if summary.get("llm_distribution"):
            print(f"\nDistribuição LLM:")
            for cls, count in summary["llm_distribution"].items():
                print(f"  {cls}: {count}")
    else:
        print("Nenhum dado disponível.")
    return 0


def cmd_merge_sessions(args: argparse.Namespace) -> int:
    """Mergeia sessões JSONL no CSV master."""
    import glob
    from src.core.config import set_llm_model, get_current_llm_model, get_model_paths, ensure_model_directories
    from src.utils.persistence import merge_jsonl_to_csv

    model = args.model or get_current_llm_model()
    set_llm_model(model)
    ensure_model_directories()

    paths = get_model_paths(model)
    sessions_dir = str(paths["ANALISES_DIR"]) + "/sessions"
    csv_path = args.csv or "csv/floss_hashes_no_rpt_purity_with_analysis.csv"

    jsonl_files = sorted(glob.glob(f"{sessions_dir}/*.jsonl"))
    if not jsonl_files:
        print(f"Nenhuma sessão JSONL encontrada em {sessions_dir}")
        return 0

    total_merged = 0
    for jsonl_path in jsonl_files:
        updated = merge_jsonl_to_csv(jsonl_path, csv_path)
        if updated > 0:
            print(f"  {jsonl_path}: {updated} registros mergeados")
            total_merged += updated

    print(f"\nTotal: {total_merged} registros mergeados de {len(jsonl_files)} sessões")
    return 0


def cmd_interactive(args: argparse.Namespace) -> int:
    """Inicia menu interativo legado."""
    if args.menu == "llm":
        from src.core.menu_analysis import main as menu_main
        menu_main()
    else:
        from src.core.main import main as main_interface
        main_interface()
    return 0


def run_cli(argv: list[str] | None = None) -> int:
    """Entry point da CLI. Retorna exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        # Sem subcomando: mostrar help
        parser.print_help()
        return 0

    commands = {
        "analyze": cmd_analyze,
        "status": cmd_status,
        "merge-sessions": cmd_merge_sessions,
        "interactive": cmd_interactive,
    }

    handler = commands.get(args.command)
    if handler:
        return handler(args)

    parser.print_help()
    return 1
