#!/usr/bin/env python3
"""Entry point unificado para o Refan.

Comportamento:
- Com argumentos (ex: refan.py analyze --model mistral): despacha para CLI
- Sem argumentos: menu interativo de seleção de modelo + interface

Refs: REFACTORING_PLAN.md Phase 7.3
"""

import sys
from pathlib import Path

# Garantir que src/ é importável
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def _run_interactive() -> int:
    """Menu interativo legado (comportamento original do refan.py)."""
    from src.core.config import (
        list_available_ollama_models,
        set_llm_model,
        get_current_llm_model,
        ensure_model_directories,
        check_llm_model_status,
    )
    from src.utils.colors import (
        header, info, dim, success, warning, error, cyan, bold,
    )

    # Seleção de modelo
    print(f"\n{cyan('Detecção de modelos Ollama disponíveis...')}")
    models = list(dict.fromkeys(list_available_ollama_models()))
    if not models:
        print(error('Nenhum modelo encontrado no Ollama. Execute: ollama pull mistral'))
        return 1

    print(f"{info('Modelos encontrados:')}")
    for idx, name in enumerate(models, 1):
        marker = ' (atual)' if name == get_current_llm_model() else ''
        print(f"  {cyan(str(idx)+'.')} {name}{marker}")
    print(f"  {cyan('0.')} Usar modelo atual ({get_current_llm_model()})")

    choice = input(bold('Selecione o modelo para esta sessão: ')).strip()
    if choice == '0' or choice == '':
        model = get_current_llm_model()
    else:
        try:
            idx = int(choice) - 1
            model = models[idx] if 0 <= idx < len(models) else get_current_llm_model()
        except (ValueError, IndexError):
            model = get_current_llm_model()

    set_llm_model(model)
    ensure_model_directories()
    print(success(f"Modelo selecionado: {model}"))

    hc = check_llm_model_status(model, verbose=True)
    if not hc.get("available") and not hc.get("pulled"):
        print(error(f"O modelo '{model}' não está disponível localmente. Use 'ollama pull {model}'."))

    # Menu de interface
    print(f"\n{header('=' * 60)}")
    print(f"{header('REFAN — CLASSIFICAÇÃO DE REFATORAÇÕES COM LLMs')}")
    print(f"{header('=' * 60)}")

    print(f"\n{cyan('Escolha a interface:')}")
    print(f"{cyan('1.')} Menu interativo completo")
    print(f"{cyan('2.')} Menu de análise LLM (especializado)")
    print(f"{cyan('0.')} Sair")

    choice = input(f"\n{bold('Opção:')} ").strip()

    if choice == '1':
        from src.core.main import main as main_interface
        main_interface()
    elif choice == '2':
        from src.core.menu_analysis import main as menu_interface
        menu_interface()
    elif choice == '0':
        print(success('Encerrando.'))
    else:
        print(error('Opção inválida.'))

    return 0


def main() -> int:
    """Decide entre CLI (com argumentos) e interativo (sem argumentos)."""
    # Se há argumentos de linha de comando, usar CLI
    if len(sys.argv) > 1:
        from src.cli import run_cli
        return run_cli()
    else:
        return _run_interactive()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nInterrompido pelo usuário.")
        sys.exit(0)
    except Exception as e:
        print(f"\nErro inesperado: {e}")
        sys.exit(1)
