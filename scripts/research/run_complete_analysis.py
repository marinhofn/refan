#!/usr/bin/env python3
"""
Script para executar análise LLM completa e contínua
"""

import sys
from pathlib import Path
import time

# Configurar paths para imports funcionarem quando executado diretamente
if __name__ == "__main__":
    # Adicionar o diretório raiz do projeto ao path (volta 2 níveis: scripts/analysis -> projeto)
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))

from src.analyzers.llm_purity_analyzer import LLMPurityAnalyzer
from src.utils.colors import *

def run_complete_analysis():
    """Executa análise completa em lotes para evitar timeout."""
    
    analyzer = LLMPurityAnalyzer()
    
    print(header("🚀 ANÁLISE LLM COMPLETA"))
    print(header("=" * 50))
    
    # Configurações
    BATCH_SIZE = 50  # Processa 50 commits por vez
    total_batches = 0
    total_processed = 0
    total_successful = 0
    
    while True:
        print(f"\n{info(f'🔄 Executando lote {total_batches + 1}...')}")
        
        # Executar lote
        stats = analyzer.analyze_commits(
            max_commits=BATCH_SIZE,
            skip_analyzed=True,
            purity_filter=None
        )
        
        # Atualizar contadores
        batch_processed = stats['total_processed']
        batch_successful = stats['successful_analyses']
        
        total_batches += 1
        total_processed += batch_processed
        total_successful += batch_successful
        
        print(f"\n{success('📊 Estatísticas do Lote:')}")
        print(f"   Processados: {batch_processed}")
        print(f"   Sucessos: {batch_successful}")
        print(f"   Taxa: {(batch_successful/batch_processed*100) if batch_processed > 0 else 0:.1f}%")
        
        print(f"\n{info('📈 Totais Acumulados:')}")
        print(f"   Lotes executados: {total_batches}")
        print(f"   Total processado: {total_processed}")
        print(f"   Total sucessos: {total_successful}")
        print(f"   Taxa geral: {(total_successful/total_processed*100) if total_processed > 0 else 0:.1f}%")
        
        # Verificar se terminou
        if batch_processed == 0:
            print(success(f"\n🎉 ANÁLISE COMPLETA FINALIZADA!"))
            print(f"   Total final: {total_processed} commits processados")
            print(f"   Sucessos: {total_successful}")
            print(f"   Taxa final: {(total_successful/total_processed*100) if total_processed > 0 else 0:.1f}%")
            break
            
        # Pausa entre lotes
        print(f"\n{dim('⏸️ Pausa de 5 segundos entre lotes...')}")
        time.sleep(5)

if __name__ == "__main__":
    run_complete_analysis()
