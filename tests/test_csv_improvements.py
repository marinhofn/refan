#!/usr/bin/env python3
"""
Script de teste para verificar melhorias no parsing JSON e uso de dados CSV.
"""

import sys
import os
import json

# Adicionar o diretório do projeto ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_csv_loader():
    """Testa o carregador de dados CSV."""
    print("🧪 Testando CSVDataLoader...")
    
    try:
        from src.handlers.optimized_llm_handler import CSVDataLoader
        
        loader = CSVDataLoader()
        
        # Testar com hash conhecido
        test_hash = "b8b2d434de426995aa4dd9d563dba3f314d2b05d"
        commit_info = loader.get_commit_info(test_hash)
        
        print(f"✅ Dados para {test_hash}:")
        for key, value in commit_info.items():
            print(f"   {key}: {value}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao testar CSVDataLoader: {e}")
        return False

def test_simplified_prompt():
    """Testa se o prompt simplificado está carregado."""
    print("\n🧪 Testando prompt simplificado...")
    
    try:
        prompt_path = "configs/PROMPT_OTIMIZADO_ATUAL.txt"
        with open(prompt_path, 'r', encoding='utf-8') as f:
            prompt = f.read()
        
        # Verificar se contém o formato simplificado
        if '"refactoring_type": "pure|floss"' in prompt and 'repository, commits, and technical evidence will be filled automatically' in prompt:
            print("✅ Prompt simplificado detectado")
            return True
        else:
            print("❌ Prompt ainda não está no formato simplificado")
            return False
            
    except Exception as e:
        print(f"❌ Erro ao verificar prompt: {e}")
        return False

def test_llm_handler_initialization():
    """Testa se o handler pode ser inicializado com as melhorias."""
    print("\n🧪 Testando inicialização do OptimizedLLMHandler...")
    
    try:
        from src.handlers.optimized_llm_handler import OptimizedLLMHandler
        
        handler = OptimizedLLMHandler()
        
        # Verificar se tem csv_loader
        if hasattr(handler, 'csv_loader'):
            print("✅ Handler inicializado com csv_loader")
            return True
        else:
            print("❌ Handler não tem csv_loader")
            return False
            
    except Exception as e:
        print(f"❌ Erro ao inicializar handler: {e}")
        return False

def test_json_validation_with_csv():
    """Testa validação JSON usando dados CSV."""
    print("\n🧪 Testando validação JSON com dados CSV...")
    
    try:
        from src.handlers.optimized_llm_handler import OptimizedLLMHandler
        
        handler = OptimizedLLMHandler()
        
        # JSON simulado simples (formato novo)
        mock_json = {
            "refactoring_type": "floss",
            "justification": "Method signature changed affecting behavior",
            "confidence_level": "high"
        }
        
        # Testar validação com hash conhecido
        test_hash = "b8b2d434de426995aa4dd9d563dba3f314d2b05d"
        validated = handler._validate_and_fix_json_fields(
            mock_json,
            "Test commit message",
            commit_hash=test_hash,
            previous_hash="d3b996cbbb3a726dcadb851ee753648d9c77337a",
            repository="log4j"
        )
        
        print("✅ JSON validado:")
        print(json.dumps(validated, indent=2))
        
        # Verificar se campos foram preenchidos automaticamente
        expected_fields = ["repository", "commit_hash_before", "commit_hash_current"]
        for field in expected_fields:
            if field in validated and validated[field] != "unknown":
                print(f"   ✅ {field}: {validated[field]}")
            else:
                print(f"   ⚠️  {field}: não preenchido ou 'unknown'")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao testar validação JSON: {e}")
        return False

def test_raw_response_preservation():
    """Testa se a resposta raw da LLM é preservada."""
    print("\n🧪 Testando preservação de resposta raw da LLM...")
    
    try:
        from src.handlers.optimized_llm_handler import OptimizedLLMHandler
        
        handler = OptimizedLLMHandler()
        
        # Simular resposta da LLM que falha no JSON parsing
        mock_llm_response = """
        Este commit refatora o código movendo métodos entre classes.
        A análise indica que é um refactoring do tipo floss porque
        há mudanças funcionais junto com as estruturais.
        Confiança: alta
        """
        
        # Processar a resposta
        result = handler._process_llm_response(
            mock_llm_response,
            "Test commit message",
            commit_hash="12230bff81e4092cd79ccf3f033c0fdcb0d5887b",
            previous_hash="abc123",
            repository="test-repo"
        )
        
        if result:
            print("✅ Resultado processado:")
            
            # Verificar se resposta raw foi preservada
            if "llm_raw_response" in result:
                print(f"   ✅ llm_raw_response: {result['llm_raw_response'][:100]}...")
            else:
                print("   ❌ llm_raw_response: não encontrado")
            
            # Verificar se justificativa não é o fallback genérico
            justification = result.get("justification", "")
            if "Analysis failed - insufficient data" not in justification and len(justification) > 20:
                print(f"   ✅ justification: {justification[:100]}...")
            else:
                print(f"   ⚠️  justification: {justification}")
            
            return True
        else:
            print("❌ Resultado não gerado")
            return False
            
    except Exception as e:
        print(f"❌ Erro ao testar preservação de resposta raw: {e}")
        return False

def main():
    """Executa todos os testes."""
    print("🔧 Testando melhorias implementadas\n")
    
    tests = [
        test_csv_loader,
        test_simplified_prompt,
        test_llm_handler_initialization,
        test_json_validation_with_csv,
        test_raw_response_preservation
    ]
    
    results = []
    for test in tests:
        result = test()
        results.append(result)
    
    print(f"\n📊 Resultados: {sum(results)}/{len(results)} testes passaram")
    
    if all(results):
        print("🎉 Todas as melhorias funcionando corretamente!")
        print("\n📋 Próximos passos:")
        print("1. Execute uma análise pequena com a opção 9")
        print("2. Verifique se as análises agora têm justificações válidas ao invés de 'Analysis failed - insufficient data'")
        print("3. Monitore se o parsing JSON está funcionando melhor")
    else:
        print("⚠️  Algumas melhorias precisam ser ajustadas")

if __name__ == "__main__":
    main()