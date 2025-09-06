#!/usr/bin/env python3
"""
Script de teste para verificar a nova estrutura de JSON com justificativas.
"""

import sys
import os
from pathlib import Path

# Adicionar src ao path
project_root = Path(__file__).parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

from src.analyzers.llm_purity_analyzer import LLMPurityAnalyzer
from src.core.config import set_llm_model, ensure_model_directories
from src.utils.colors import *

def test_new_json_structure():
    """Testa a nova estrutura de JSON com justificativas."""
    
    print(header("🧪 TESTE: Nova estrutura JSON com justificativas"))
    print(header("=" * 60))
    
    # Configurar modelo de teste
    test_model = "mistral:latest"
    set_llm_model(test_model)
    ensure_model_directories()
    
    # Testar com arquivo TRUE (poucas entradas para teste rápido)
    csv_true = "csv/true_purity_hashes_with_analysis.csv"
    
    print(info(f"Testando com arquivo: {csv_true}"))
    print(info(f"Modelo: {test_model}"))
    
    # Criar analisador
    analyzer = LLMPurityAnalyzer(
        model=test_model, 
        csv_file_path=csv_true,
        dry_run=True  # Modo dry-run para não fazer chamadas LLM reais
    )
    
    print(warning("Executando em modo DRY-RUN (não faz chamadas LLM reais)"))
    
    # Analisar apenas 3 commits para teste
    stats = analyzer.analyze_commits(max_commits=3, skip_analyzed=False)
    
    print(f"\n{success('Teste concluído!')}")
    print(f"Estatísticas: {stats}")
    
    # Verificar se o arquivo JSON foi criado com a nova estrutura
    if analyzer.session_log_file and os.path.exists(analyzer.session_log_file):
        print(f"\n{success('Arquivo JSON criado:')} {analyzer.session_log_file}")
        
        # Ler e exibir uma amostra do conteúdo
        import json
        with open(analyzer.session_log_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"\n{info('Estrutura do JSON:')}")
        print(f"  - session_info.model_used: {data.get('session_info', {}).get('model_used', 'N/A')}")
        print(f"  - session_info.analysis_type: {data.get('session_info', {}).get('analysis_type', 'N/A')}")
        print(f"  - session_info.description: {data.get('session_info', {}).get('description', 'N/A')}")
        print(f"  - detailed_analyses: {len(data.get('detailed_analyses', []))} entradas")
        print(f"  - summary.total_commits: {data.get('summary', {}).get('total_commits', 0)}")
        
        if data.get('detailed_analyses'):
            sample = data['detailed_analyses'][0]
            print(f"\n{info('Amostra de análise:')}")
            print(f"  - hash: {sample.get('hash', 'N/A')[:12]}...")
            print(f"  - purity_classification: {sample.get('purity_classification', 'N/A')}")
            print(f"  - llm_classification: {sample.get('llm_classification', 'N/A')}")
            print(f"  - llm_justification: {sample.get('llm_justification', 'N/A')[:100]}...")
    else:
        print(error("Arquivo JSON não foi criado!"))

if __name__ == "__main__":
    test_new_json_structure()