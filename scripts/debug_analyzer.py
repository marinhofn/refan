#!/usr/bin/env python3
"""
Debug específico para encontrar o erro 'bool' object is not callable
"""

import sys
from pathlib import Path

# Configurar paths para imports funcionarem quando executado diretamente
if __name__ == "__main__":
    # Adicionar o diretório raiz do projeto ao path
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))


from src.analyzers.llm_purity_analyzer import LLMPurityAnalyzer
import traceback

def debug_analyzer():
    """Debug detalhado do analisador."""
    print("=== DEBUG DO LLM PURITY ANALYZER ===\n")
    
    try:
        # Criar analisador
        analyzer = LLMPurityAnalyzer()
        
        # Carregar dados
        df = analyzer._load_csv_data()
        if df is None:
            print("❌ Falha ao carregar CSV")
            return
        
        # Pegar o primeiro hash disponível
        first_hash = df.iloc[2]['hash']  # Terceiro hash para evitar os já testados
        purity_class = df.iloc[2]['purity_analysis']
        
        print(f"🔍 Analisando hash: {first_hash}")
        print(f"🔍 Classificação Purity: {purity_class}")
        
        # Buscar dados do commit step by step
        print("\n📋 Buscando dados do commit...")
        commit_data = analyzer._get_commit_data_from_refactoring_csv(first_hash)
        if not commit_data:
            print("❌ Não encontrou dados do commit")
            return
        
        print(f"✅ Dados encontrados: {commit_data}")
        
        # Obter diff step by step
        print("\n📄 Obtendo diff...")
        diff_content = analyzer._get_diff_for_commit(
            commit_data['project'],
            commit_data['commit1'],
            commit_data['commit2']
        )
        
        if not diff_content:
            print("❌ Não conseguiu obter diff")
            return
        
        print(f"✅ Diff obtido: {len(diff_content)} caracteres")
        
        # Análise LLM step by step
        print("\n🤖 Iniciando análise LLM...")
        try:
            llm_result = analyzer.llm_handler.analyze_commit_refactoring(
                current_hash=first_hash,
                previous_hash=commit_data['commit1'],
                repository=commit_data['project'],
                diff_content=diff_content
            )
            
            print(f"✅ Resultado LLM: {llm_result}")
            
        except Exception as llm_error:
            print(f"❌ Erro na análise LLM: {str(llm_error)}")
            print("📍 Stack trace completo:")
            traceback.print_exc()
            
    except Exception as e:
        print(f"❌ Erro geral: {str(e)}")
        print("📍 Stack trace completo:")
        traceback.print_exc()

if __name__ == "__main__":
    debug_analyzer()
