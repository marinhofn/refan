#!/usr/bin/env python3
"""
Teste específico da opção 2 do menu com DeepSeek 1.5b
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.analyzers.llm_purity_analyzer import LLMPurityAnalyzer
from src.core.config import set_llm_model, get_current_llm_model
from src.utils.colors import *

def test_option_2_deepseek():
    """Testa a opção 2 do menu com DeepSeek 1.5b"""
    
    print(header("🧪 TESTE OPÇÃO 2 COM DEEPSEEK 1.5B"))
    
    # Configurar para DeepSeek 1.5b
    print(info("🔧 Configurando DeepSeek 1.5b..."))
    set_llm_model("deepseek-r1:1.5b")
    
    current_model = get_current_llm_model()
    print(success(f"✅ Modelo ativo: {current_model}"))
    
    # Criar analyzer como na opção 2
    print(info("🔍 Criando LLMPurityAnalyzer..."))
    analyzer = LLMPurityAnalyzer()
    
    # Verificar se o analyzer está usando o modelo correto
    adapter_model = analyzer.llm_handler.adapter.model
    print(info(f"📊 Modelo no adapter: {adapter_model}"))
    print(info(f"🔍 DeepSeek detectado: {'deepseek' in adapter_model.lower()}"))
    
    # Verificar configurações do adapter
    if hasattr(analyzer.llm_handler.adapter, '_analysis_count'):
        print(info(f"📈 Contador análises: {analyzer.llm_handler.adapter._analysis_count}"))
    
    # Simular análise como na opção 2 (mas com 3 commits para teste)
    print(info("\n🚀 Simulando análise de lote (3 commits para teste)..."))
    
    try:
        stats = analyzer.analyze_commits(max_commits=3, skip_analyzed=True)
        print(success(f"✅ Análise concluída!"))
        print(f"📊 Estatísticas: {stats}")
        
        # Verificar contador após análise
        if hasattr(analyzer.llm_handler.adapter, '_analysis_count'):
            print(info(f"📈 Análises realizadas: {analyzer.llm_handler.adapter._analysis_count}"))
            
    except Exception as e:
        print(error(f"❌ Erro na análise: {e}"))
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_option_2_deepseek()