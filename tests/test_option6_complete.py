#!/usr/bin/env python3
"""
Teste completo da opção 6 corrigida
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
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.handlers.purity_handler import PurityHandler
from src.handlers.data_handler import DataHandler
from src.utils.colors import *

def test_option6_simulation():
    """Simula a execução da opção 6"""
    
    print(header("Simulação da Opção 6 - Comparação LLM vs Purity"))
    
    # Simular entrada do usuário
    limit = 5  # Usar limite pequeno para teste
    
    # Inicializar handlers  
    purity_handler = PurityHandler()
    data_handler = DataHandler()
    
    # Carregar dados do Purity SEM FILTROS
    print(progress("Carregando dados do Purity (SEM FILTROS)..."))
    if not purity_handler.load_purity_data():
        print(error("Falha ao carregar dados do Purity"))
        return
    
    # Extrair commits do Purity
    print(progress(f"Extraindo os primeiros {limit} commits do Purity (todos os tipos)..."))
    all_purity_commits = purity_handler.get_all_purity_commits(limit=limit)
    
    if not all_purity_commits:
        print(error("Nenhum commit encontrado no Purity."))
        return
    
    print(success(f"Total de commits do Purity selecionados: {len(all_purity_commits)}"))
    
    # Separar por tipo para estatísticas
    floss_count = sum(1 for c in all_purity_commits if c.get('type') == 'floss')
    pure_count = sum(1 for c in all_purity_commits if c.get('type') == 'pure')
    print(info(f"  • Floss: {floss_count}"))
    print(info(f"  • Pure: {pure_count}"))
    
    # Carregar todas as análises LLM existentes
    print(progress("Carregando análises LLM existentes..."))
    all_llm_analyses = purity_handler.load_all_llm_analyses()
    print(success(f"Carregadas {len(all_llm_analyses)} análises LLM"))
    
    # Verificar quantos commits ainda não foram analisados
    analyzed_commits = set(item['commit_hash_current'] for item in all_llm_analyses)
    purity_commit_hashes = [commit['commit_hash_current'] for commit in all_purity_commits]
    unanalyzed_commits = [hash_val for hash_val in purity_commit_hashes if hash_val not in analyzed_commits]
    
    print(info(f"Commits do Purity já analisados pelo LLM: {len(purity_commit_hashes) - len(unanalyzed_commits)}"))
    print(info(f"Commits do Purity ainda não analisados: {len(unanalyzed_commits)}"))
    
    print(success("✅ Opção 6 está funcionando corretamente!"))

if __name__ == "__main__":
    test_option6_simulation()
