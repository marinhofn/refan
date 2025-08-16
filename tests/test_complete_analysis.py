#!/usr/bin/env python3
"""
Script de teste para a análise completa
"""

import sys
from pathlib import Path
import os

# Configurar paths para imports funcionarem quando executado diretamente
if __name__ == "__main__":
    # Adicionar o diretório raiz do projeto ao path (volta 1 nível: tests -> projeto)
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))

from src.core.menu_analysis import run_complete_analysis_from_start
from src.utils.colors import *

def test_complete_analysis_setup():
    """Testa apenas a configuração da análise completa."""
    
    print(header("🧪 TESTE DA ANÁLISE COMPLETA"))
    print(header("=" * 50))
    
    print(f"{info('📁 Verificando estrutura...')}")
    
    # Verificar se pasta existe
    if os.path.exists("analises_completas"):
        print(f"{success('✅ Pasta analises_completas existe')}")
    else:
        print(f"{error('❌ Pasta analises_completas não existe')}")
    
    # Verificar arquivo principal
    if os.path.exists("csv/hashes_no_rpt_purity_with_analysis.csv"):
        print(f"{success('✅ Arquivo principal existe')}")
        
        # Verificar tamanho
        import pandas as pd
        df = pd.read_csv("csv/hashes_no_rpt_purity_with_analysis.csv")
        print(f"{info(f'📊 Total de registros: {len(df):,}')}")
        
        # Verificar quantos já têm análise LLM
        analyzed = df[(df['llm_analysis'].notna()) & (df['llm_analysis'] != '') & (df['llm_analysis'] != 'FAILED')]
        print(f"{info(f'🤖 Já analisados: {len(analyzed):,}')}")
        print(f"{info(f'⏳ Restantes: {len(df) - len(analyzed):,}')}")
        
    else:
        print(f"{error('❌ Arquivo principal não encontrado')}")
    
    print(f"\n{warning('💡 Para executar a análise completa:')}")
    print("   1. Execute: python3 menu_analysis.py")
    print("   2. Escolha opção 5")
    print("   3. Confirme com 's'")
    print(f"\n{warning('⚠️ ATENÇÃO:')}")
    print("   • A análise completa pode levar MUITAS horas")
    print("   • Todos os commits serão reprocessados do início")
    print("   • O resultado será salvo em analises_completas/")

if __name__ == "__main__":
    test_complete_analysis_setup()
