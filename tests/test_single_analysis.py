#!/usr/bin/env python3
"""
Script para testar rapidamente análise de um commit com sistema de falhas.
"""

import sys
from pathlib import Path

# Configurar paths para imports funcionarem quando executado diretamente
if __name__ == "__main__":
    # Adicionar o diretório raiz do projeto ao path
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))


import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.handlers.data_handler import DataHandler
from src.analyzers.optimized_llm_handler import OptimizedLLMHandler
from src.handlers.git_handler import GitHandler
from src.utils.colors import *

def test_single_commit_analysis():
    """Testa análise de um commit com sistema de falhas."""
    print(f"\n{header('TESTE DE ANÁLISE DE COMMIT COM SISTEMA DE FALHAS')}")
    
    # Inicializar handlers
    data_handler = DataHandler()
    git_handler = GitHandler()
    llm_handler = OptimizedLLMHandler()
    
    # Carregar e filtrar dados
    if not data_handler.load_data() or not data_handler.filter_data():
        print(error("Falha ao carregar dados"))
        return False
    
    # Pegar o primeiro commit dos dados filtrados
    first_commit = data_handler.filtered_data.iloc[0]
    
    repository = first_commit['project']
    commit1 = first_commit['commit1'] 
    commit2 = first_commit['commit2']
    project_name = first_commit['project_name']
    
    print(f"{info('Testando commit:')} {commit2[:8]}")
    print(f"{info('Repositório:')} {project_name}")
    print(f"{info('URL:')} {repository}")
    
    # Garantir que o repositório esteja disponível
    print(f"\n{progress('Clonando/atualizando repositório...')}")
    success_flag, repo_path = git_handler.ensure_repo_cloned(repository)
    if not success_flag:
        print(error(f"Erro ao processar repositório {repository}"))
        return False
    
    # Verificar se ambos os commits existem
    if not git_handler.commit_exists(repo_path, commit1):
        print(error(f"Commit {commit1} não encontrado"))
        return False
        
    if not git_handler.commit_exists(repo_path, commit2):
        print(error(f"Commit {commit2} não encontrado"))
        return False
    
    # Obter diff e mensagem do commit
    print(f"{progress('Obtendo diff do commit...')}")
    diff = git_handler.get_commit_diff(repo_path, commit1, commit2)
    if diff is None:
        print(error("Não foi possível obter o diff"))
        return False
        
    commit_message = git_handler.get_commit_message(repo_path, commit2)
    if commit_message is None:
        print(error("Não foi possível obter a mensagem do commit"))
        return False
    
    print(f"{info('Tamanho do diff:')} {len(diff)} caracteres")
    print(f"{info('Mensagem do commit:')} {commit_message[:100]}...")
    
    # Analisar o commit
    print(f"\n{progress('Analisando commit com LLM...')}")
    analysis = llm_handler.analyze_commit(
        repository, commit1, commit2, commit_message, diff, show_prompt=False
    )
    
    if analysis is not None:
        refact_type = analysis['refactoring_type']
        processing_method = analysis.get('processing_method', 'unknown')
        print(f"\n{success('✅ Análise bem-sucedida!')}")
        print(f"{info('Tipo de refatoramento:')} {refact_type}")
        print(f"{info('Método de processamento:')} {processing_method}")
        print(f"{info('Justificação:')} {analysis.get('justification', 'N/A')[:200]}...")
        return True
    else:
        print(f"\n{error('❌ Falha na análise')}")
        print(f"{warning('Verificar arquivo json_failures.json para detalhes da falha')}")
        
        # Verificar se a falha foi salva
        if os.path.exists(llm_handler.failures_file):
            import json
            try:
                with open(llm_handler.failures_file, 'r') as f:
                    failures = json.load(f)
                latest_failure = failures[-1] if failures else None
                if latest_failure and latest_failure['commit_hash'] == commit2:
                    print(f"{success('✅ Falha JSON capturada e salva corretamente')}")
                    return True
            except Exception as e:
                print(f"{error(f'Erro ao verificar arquivo de falhas: {e}')}")
        
        return False

if __name__ == "__main__":
    test_single_commit_analysis()
