#!/usr/bin/env python3
"""
Teste da correção do PurityHandler - opção 6
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

# Adicionar o diretório atual ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.handlers.purity_handler import PurityHandler
from src.utils.colors import *

def test_purity_handler():
    """Testa o PurityHandler corrigido"""
    
    print(header("Testando PurityHandler - Correção da Opção 6"))
    
    # Inicializar handler
    purity_handler = PurityHandler()
    
    # Carregar dados
    print(progress("Carregando dados do Purity..."))
    if not purity_handler.load_purity_data():
        print(error("Falha ao carregar dados do Purity"))
        return
    
    # Testar get_all_purity_commits com limite pequeno
    print(progress("Testando get_all_purity_commits com limite de 5..."))
    commits = purity_handler.get_all_purity_commits(limit=5)
    
    if commits:
        print(success(f"✅ Método executou com sucesso! Encontrados {len(commits)} commits"))
        
        # Mostrar alguns exemplos
        for i, commit in enumerate(commits[:3]):
            print(info(f"Commit {i+1}:"))
            print(f"  Hash: {commit['commit_hash_current'][:12]}")
            print(f"  Tipo: {commit['type']}")
            print(f"  Purity Value: {commit['purity_value']}")
            
        # Contar tipos
        types = {}
        for commit in commits:
            commit_type = commit['type']
            types[commit_type] = types.get(commit_type, 0) + 1
        
        print(info("Distribuição de tipos:"))
        for type_name, count in types.items():
            print(f"  {type_name}: {count}")
            
    else:
        print(error("❌ Método retornou None ou lista vazia"))

if __name__ == "__main__":
    test_purity_handler()
