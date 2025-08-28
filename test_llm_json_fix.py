#!/usr/bin/env python3
"""
Script de teste para verificar se as melhorias no processamento de JSON do LLM estão funcionando.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.utils.json_parser import extract_json_from_text, _strip_think_blocks

def test_json_parsing():
    """Testa casos problemáticos identificados no json_failures.json"""
    
    print("🧪 Testando melhorias no parsing de JSON...")
    
    # Caso 1: Resposta com tags <think>
    test_case_1 = """
    <think>
    Analyzing the Git diff to classify the refactoring...
    </think>
    
    {
        "repository": "android-async-http",
        "commit_hash_before": "abc123",
        "commit_hash_current": "def456",
        "refactoring_type": "pure",
        "justification": "Simple code reorganization without behavior changes",
        "technical_evidence": "Method moved between classes without logic changes",
        "confidence_level": "high",
        "diff_source": "direct"
    }
    """
    
    # Caso 2: Resposta com texto confuso (como visto nos logs)
    test_case_2 = """
    You are an expert You are an expert You are an expert software engineering analyst
    
    Based on the provided context, I'll analyze this Git diff...
    
    {
        "repository": "test-repo",
        "refactoring_type": "floss",
        "justification": "Added new functionality during restructuring"
    }
    """
    
    # Caso 3: JSON puro (deve funcionar)
    test_case_3 = '''
    {
        "repository": "clean-repo",
        "commit_hash_before": "hash1", 
        "commit_hash_current": "hash2",
        "refactoring_type": "pure",
        "justification": "Clean refactoring analysis",
        "technical_evidence": "Variables renamed only",
        "confidence_level": "high",
        "diff_source": "direct"
    }
    '''
    
    test_cases = [
        ("Resposta com <think> blocks", test_case_1),
        ("Resposta com texto repetitivo", test_case_2), 
        ("JSON puro", test_case_3)
    ]
    
    results = []
    
    for name, test_text in test_cases:
        print(f"\n📋 Testando: {name}")
        print(f"   Texto original: {len(test_text)} chars")
        
        # Testar remoção de think blocks
        cleaned = _strip_think_blocks(test_text)
        print(f"   Após limpeza: {len(cleaned)} chars")
        
        # Testar extração de JSON
        result = extract_json_from_text(test_text)
        
        if result:
            print(f"   ✅ JSON extraído com sucesso")
            print(f"   📊 Campos encontrados: {list(result.keys())}")
            print(f"   🎯 Tipo: {result.get('refactoring_type', 'N/A')}")
            print(f"   📝 Justificativa: {result.get('justification', 'N/A')[:50]}...")
            results.append((name, True, result))
        else:
            print(f"   ❌ Falha na extração de JSON")
            results.append((name, False, None))
    
    # Resumo dos resultados
    print(f"\n🎯 RESUMO DOS TESTES:")
    success_count = sum(1 for _, success, _ in results if success)
    print(f"   Sucessos: {success_count}/{len(results)}")
    
    for name, success, result in results:
        status = "✅" if success else "❌"
        print(f"   {status} {name}")
    
    return results

def test_prompt_improvements():
    """Testa se o novo prompt está correto"""
    print(f"\n📝 Verificando prompt otimizado...")
    
    try:
        with open('configs/PROMPT_OTIMIZADO_ATUAL.txt', 'r', encoding='utf-8') as f:
            prompt = f.read()
            
        print(f"   📏 Tamanho do prompt: {len(prompt)} chars")
        
        # Verificar elementos chave
        key_elements = [
            "ONLY a valid JSON object",
            "No other text before or after", 
            "refactoring_type",
            "justification",
            "technical_evidence"
        ]
        
        missing = []
        for element in key_elements:
            if element not in prompt:
                missing.append(element)
        
        if missing:
            print(f"   ⚠️  Elementos ausentes: {missing}")
        else:
            print(f"   ✅ Todos os elementos chave presentes")
            
        return len(missing) == 0
        
    except Exception as e:
        print(f"   ❌ Erro ao ler prompt: {e}")
        return False

if __name__ == "__main__":
    print("🚀 TESTE DAS MELHORIAS NO PROCESSAMENTO DE LLM\n")
    
    # Executar testes
    json_results = test_json_parsing()
    prompt_ok = test_prompt_improvements()
    
    # Resultado final
    json_success_rate = sum(1 for _, success, _ in json_results if success) / len(json_results)
    
    print(f"\n🏁 RESULTADO FINAL:")
    print(f"   📊 Taxa de sucesso JSON: {json_success_rate:.1%}")
    print(f"   📝 Prompt otimizado: {'✅' if prompt_ok else '❌'}")
    
    if json_success_rate >= 0.8 and prompt_ok:
        print(f"   🎉 Melhorias aplicadas com sucesso!")
        exit_code = 0
    else:
        print(f"   ⚠️  Ainda há problemas a resolver")
        exit_code = 1
    
    print(f"\n💡 Próximos passos:")
    print(f"   1. Executar análise real com poucos hashes para validar")
    print(f"   2. Monitorar logs de falhas JSON")
    print(f"   3. Ajustar prompt se necessário")
    
    sys.exit(exit_code)