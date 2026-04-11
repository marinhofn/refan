#!/usr/bin/env python3
"""
Teste final e completo da opção 6 - versão que simula o fluxo completo
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

from src.core.main import _process_purity_comparison_internal
from src.utils.colors import *

def test_option6_final():
    """Testa exatamente a função da opção 6"""
    
    print(header("TESTE FINAL - OPÇÃO 6 CORRIGIDA"))
    print("Simulando: python main.py -> opção 6 -> limite 3 -> não analisar")
    
    try:
        # Simular exatamente o que a opção 6 faz
        _process_purity_comparison_internal(3)
        print(success("✅ Opção 6 executou sem erros!"))
        
    except Exception as e:
        print(error(f"❌ Erro encontrado: {e}"))
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_option6_final()
