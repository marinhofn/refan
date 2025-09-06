#!/usr/bin/env python3
"""
Teste para verificar se os novos campos estão sendo salvos nos JSONs de análise.
"""

import sys
import os
import json

# Adicionar o diretório do projeto ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_llm_analyzer_result_structure():
    """Testa se o LLMPurityAnalyzer retorna os novos campos."""
    print("🧪 Testando estrutura de resultado do LLMPurityAnalyzer...")
    
    try:
        from src.analyzers.llm_purity_analyzer import LLMPurityAnalyzer
        from src.handlers.optimized_llm_handler import OptimizedLLMHandler
        
        # Criar analyzer com dry-run
        analyzer = LLMPurityAnalyzer(dry_run=True)
        
        # Usar dados de teste
        test_hash = "b8b2d434de426995aa4dd9d563dba3f314d2b05d"
        
        # Simular análise
        result = analyzer._analyze_single_commit(test_hash, purity_classification=True)
        
        if result:
            print("✅ Resultado do analyzer:")
            expected_new_fields = [
                'llm_raw_response', 'repository', 'commit_hash_before', 
                'commit_hash_current', 'technical_evidence', 'diff_source'
            ]
            
            for field in expected_new_fields:
                if field in result:
                    print(f"   ✅ {field}: {str(result[field])[:100]}...")
                else:
                    print(f"   ❌ {field}: campo ausente")
            
            print(f"\n📋 Campos totais no resultado: {list(result.keys())}")
            return True
        else:
            print("❌ Nenhum resultado retornado")
            return False
            
    except Exception as e:
        print(f"❌ Erro ao testar analyzer: {e}")
        return False

def test_llm_handler_output():
    """Testa se o OptimizedLLMHandler retorna os novos campos."""
    print("\n🧪 Testando output do OptimizedLLMHandler...")
    
    try:
        from src.handlers.optimized_llm_handler import OptimizedLLMHandler
        
        handler = OptimizedLLMHandler()
        
        # Simular resposta LLM que não é JSON válido
        mock_response = {
            'response': '''
            Analisando este commit, vejo que há mudanças estruturais significativas.
            O código mostra extrações de métodos com possíveis modificações comportamentais.
            Classificação: floss
            Confiança: alta
            '''
        }
        
        # Processar resposta
        result = handler._process_llm_response(
            mock_response['response'],
            "Test commit message",
            commit_hash="b8b2d434de426995aa4dd9d563dba3f314d2b05d",
            previous_hash="d3b996cbbb3a726dcadb851ee753648d9c77337a",
            repository="log4j"
        )
        
        if result:
            print("✅ Resultado do handler:")
            expected_fields = [
                'llm_raw_response', 'repository', 'commit_hash_before', 
                'commit_hash_current', 'justification', 'technical_evidence'
            ]
            
            for field in expected_fields:
                if field in result:
                    value = str(result[field])[:100] + "..." if len(str(result[field])) > 100 else str(result[field])
                    print(f"   ✅ {field}: {value}")
                else:
                    print(f"   ❌ {field}: campo ausente")
            
            return True
        else:
            print("❌ Nenhum resultado retornado pelo handler")
            return False
            
    except Exception as e:
        print(f"❌ Erro ao testar handler: {e}")
        return False

def main():
    """Executa todos os testes."""
    print("🔧 Verificando se novos campos são salvos nos JSONs\n")
    
    tests = [
        test_llm_analyzer_result_structure,
        test_llm_handler_output
    ]
    
    results = []
    for test in tests:
        result = test()
        results.append(result)
    
    print(f"\n📊 Resultados: {sum(results)}/{len(results)} testes passaram")
    
    if all(results):
        print("🎉 Novos campos estão sendo incluídos nos resultados!")
        print("\n📋 Próximo passo:")
        print("Execute uma análise real com a opção 9 para ver se os novos campos aparecem no JSON final")
    else:
        print("⚠️  Alguns campos ainda não estão sendo incluídos")

if __name__ == "__main__":
    main()