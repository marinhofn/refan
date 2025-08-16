#!/usr/bin/env python3
"""
Script de teste para o LLM Purity Analyzer
"""

import sys
from pathlib import Path

# Configurar paths para imports funcionarem quando executado diretamente
if __name__ == "__main__":
    # Adicionar o diretório raiz do projeto ao path
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))


from src.analyzers.llm_purity_analyzer import LLMPurityAnalyzer
import json

def test_analyzer():
    """Testa o analisador com um commit simples."""
    print("=== TESTE DO LLM PURITY ANALYZER ===\n")
    
    # Criar analisador
    analyzer = LLMPurityAnalyzer()
    
    # Verificar se o arquivo CSV existe e mostrar estatísticas iniciais
    summary = analyzer.get_analysis_summary()
    if summary:
        print("📊 ESTATÍSTICAS INICIAIS:")
        print(f"  Total de hashes: {summary['total_hashes']}")
        print(f"  Análises concluídas: {summary['completed_analyses']}")
        print(f"  Análises pendentes: {summary['pending_analyses']}")
        print()
        
        print("📈 DISTRIBUIÇÃO PURITY:")
        for category, count in summary['purity_distribution'].items():
            print(f"  {category}: {count}")
        print()
        
        print("🤖 DISTRIBUIÇÃO LLM:")
        for category, count in summary['llm_distribution'].items():
            print(f"  {category}: {count}")
        print()
    
    # Testar análise de 1 commit
    print("🧪 TESTANDO ANÁLISE DE 1 COMMIT...")
    try:
        stats = analyzer.analyze_commits(max_commits=1, skip_analyzed=True)
        
        print("\n📋 RESULTADOS DO TESTE:")
        print(f"  Processados: {stats['total_processed']}")
        print(f"  Sucessos: {stats['successful_analyses']}")
        print(f"  Falhas: {stats['failed_analyses']}")
        print(f"  Erros: {stats['processing_errors']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro no teste: {str(e)}")
        return False

if __name__ == "__main__":
    test_analyzer()
