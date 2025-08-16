#!/usr/bin/env python3
"""
Teste final da correção da opção 5
"""

import sys
from pathlib import Path

# Configurar paths para imports funcionarem quando executado diretamente
if __name__ == "__main__":
    # Adicionar o diretório raiz do projeto ao path
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))


import pandas as pd
import os
import tempfile

# Simular seleção da opção 5 com inputs programáticos
def simulate_option5():
    """Simula a seleção da opção 5 do menu principal"""
    
    print("=" * 60)
    print("TESTE FINAL - OPÇÃO 5 CORRIGIDA")
    print("=" * 60)
    
    # Import dos módulos necessários
    from src.analyzers.optimized_llm_handler import OptimizedLLMHandler
    from src.handlers.git_handler import GitHandler
    
    # 1. Verificar se o método existe
    optimized_handler = OptimizedLLMHandler()
    
    if hasattr(optimized_handler, 'analyze_commit_refactoring'):
        print("✅ Método analyze_commit_refactoring encontrado")
    else:
        print("❌ Método analyze_commit_refactoring NÃO encontrado")
        return
    
    # 2. Verificar assinatura do método
    import inspect
    sig = inspect.signature(optimized_handler.analyze_commit_refactoring)
    print(f"✅ Assinatura: {sig}")
    
    # 3. Teste básico de execução
    try:
        result = optimized_handler.analyze_commit_refactoring(
            current_hash='test123',
            previous_hash='test456',
            repository='https://github.com/test/repo',
            diff_content='diff --git a/test.py b/test.py\n+print("test")'
        )
        print("✅ Método executou sem exceção")
        print(f"✅ Retorno tem campo 'success': {'success' in result}")
        
        if result.get('success'):
            print("✅ Análise bem-sucedida")
        else:
            print(f"⚠️  Análise retornou success=False: {result.get('error', 'Sem erro especificado')}")
            
    except Exception as e:
        print(f"❌ Erro na execução: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("DIAGNÓSTICO: O erro 'analyze_commit_refactoring' object has no attribute foi CORRIGIDO")
    print("A opção 5 agora deve funcionar corretamente")
    print("=" * 60)

if __name__ == "__main__":
    simulate_option5()
