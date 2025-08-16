#!/usr/bin/env python3
"""
Script de entrada unificado para o sistema de análise de refatoramento.
Permite escolher entre diferentes interfaces: menu interativo ou linha de comando.
"""

import sys
import os
from pathlib import Path

# Adicionar src ao path para imports
project_root = Path(__file__).parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

from src.core.config import create_directories, list_available_ollama_models, set_llm_model, get_current_llm_model, ensure_model_directories, check_llm_model_status
from src.utils.colors import *

def show_welcome():
    """Exibe mensagem de boas-vindas."""
    print(f"\n{header('=' * 60)}")
    print(f"{header('SISTEMA DE ANÁLISE DE REFATORAMENTO')}")
    print(f"{header('=' * 60)}")
    print(f"{info('Sistema reorganizado com estrutura modular')}")
    print(f"{dim('Desenvolvido para pesquisa acadêmica em refatoramento de código')}")
    print(f"{header('=' * 60)}")

def choose_model():
    """Permite ao usuário escolher o modelo LLM disponível no Ollama."""
    print(f"\n{cyan('Detecção de modelos Ollama disponíveis...')}")
    models = list_available_ollama_models()
    # Remover duplicatas preservando ordem
    models = list(dict.fromkeys(models))
    if not models:
        print(error('Nenhum modelo encontrado no Ollama. Certifique-se de executar: ollama pull mistral'))
        return False
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
            if idx < 0 or idx >= len(models):
                print(warning('Opção inválida, mantendo modelo atual.'))
                model = get_current_llm_model()
            else:
                model = models[idx]
        except ValueError:
            print(warning('Entrada inválida, mantendo modelo atual.'))
            model = get_current_llm_model()
    # Definir e garantir diretórios
    set_llm_model(model)
    ensure_model_directories()
    print(success(f"Modelo selecionado: {model}"))
    # Health check rápido
    hc = check_llm_model_status(model, verbose=True)
    if not hc.get("available"):
        from src.utils.colors import warning, error
        if not hc.get("pulled"):
            print(error(f"O modelo '{model}' não está disponível localmente. Use 'ollama pull {model}'."))
        else:
            print(warning(f"O modelo '{model}' pode estar carregando ou indisponível. Tentará novamente quando iniciar uma análise."))
    return True

def show_interface_menu():
    """Mostra menu de escolha de interface."""
    print(f"\n{cyan('Escolha a interface:')}")
    print(f"{cyan('1.')} Menu interativo completo (recomendado)")
    print(f"{cyan('2.')} Menu de análise LLM (especializado)")
    print(f"{cyan('3.')} Linha de comando (modo direto)")
    print(f"{cyan('0.')} Sair")
    print()

def main():
    """Função principal do sistema."""
    # Criar diretórios necessários
    try:
        # Selecionar modelo antes de criar diretórios
        choose_model()
    except Exception as e:
        print(f"{error(f'Erro ao criar diretórios: {e}')}")
        return 1
    
    show_welcome()
    
    while True:
        show_interface_menu()
        choice = input(f"{bold('Escolha uma opção (0-3):')} ").strip()
        
        if choice == '0':
            print(f"{success('Encerrando sistema. Obrigado!')}")
            return 0
        
        elif choice == '1':
            print(f"{info('Iniciando menu interativo completo...')}")
            try:
                from src.core.main import main as main_interface
                main_interface()
            except KeyboardInterrupt:
                print(f"\n{warning('Interface interrompida pelo usuário.')}")
            except Exception as e:
                print(f"{error(f'Erro na interface principal: {e}')}")
            return 0
        
        elif choice == '2':
            print(f"{info('Iniciando menu de análise LLM...')}")
            try:
                from src.core.menu_analysis import main as menu_interface
                menu_interface()
            except KeyboardInterrupt:
                print(f"\n{warning('Interface interrompida pelo usuário.')}")
            except Exception as e:
                print(f"{error(f'Erro no menu LLM: {e}')}")
            return 0
        
        elif choice == '3':
            print(f"{info('Modo linha de comando não implementado ainda.')}")
            print(f"{warning('Use as opções 1 ou 2 por enquanto.')}")
            continue
        
        else:
            print(f"{error('Opção inválida. Escolha 0-3.')}")

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print(f"\n{warning('Sistema interrompido pelo usuário.')}")
        sys.exit(0)
    except Exception as e:
        print(f"\n{error(f'Erro inesperado: {e}')}")
        sys.exit(1)
