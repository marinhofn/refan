#!/usr/bin/env python3
"""
Teste rápido da opção 5 - análise com handler e prompt otimizados
"""

import sys
from pathlib import Path

# Configurar paths para imports funcionarem quando executado diretamente
if __name__ == "__main__":
    # Adicionar o diretório raiz do projeto ao path
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))


import pandas as pd
import sys
import os

# Adicionar o diretório atual ao path para importações
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.analyzers.optimized_llm_handler import OptimizedLLMHandler
from src.handlers.git_handler import GitHandler
from src.utils.colors import *

def test_option5():
    """Testa a opção 5 com um commit."""
    
    print(header("Testando opção 5 - Handler + Prompt Otimizados"))
    
    # Criar dados de teste simples
    test_data = {
        'commit1': ['abc123'],
        'commit2': ['def456'], 
        'project': ['https://github.com/apache/log4j'],
        'project_name': ['log4j']
    }
    df = pd.DataFrame(test_data)
    commits_data = df.head(1)
    
    # Instanciar handlers
    git_handler = GitHandler()
    optimized_llm_handler = OptimizedLLMHandler()
    
    print(info("Testando se o método analyze_commit_refactoring existe..."))
    
    # Verificar se o método existe
    if hasattr(optimized_llm_handler, 'analyze_commit_refactoring'):
        print(success("✅ Método analyze_commit_refactoring encontrado!"))
        
        # Testar chamada do método (com dados fictícios)
        try:
            result = optimized_llm_handler.analyze_commit_refactoring(
                current_hash='def456',
                previous_hash='abc123', 
                repository='https://github.com/apache/log4j',
                diff_content='diff fake for testing'
            )
            print(success("✅ Método executou sem erro!"))
            print(info(f"Resultado: {result}"))
        except Exception as e:
            print(error(f"❌ Erro ao executar método: {str(e)}"))
            import traceback
            traceback.print_exc()
    else:
        print(error("❌ Método analyze_commit_refactoring não encontrado!"))

if __name__ == "__main__":
    test_option5()
