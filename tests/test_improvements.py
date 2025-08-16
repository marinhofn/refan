#!/usr/bin/env python3
"""
Script para testar as melhorias implementadas no sistema.
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

from src.handlers.purity_handler import PurityHandler
from src.handlers.llm_handler import LLMHandler
from src.utils.colors import *

def test_purity_data_cleaning():
    """Testa a limpeza de dados do Purity."""
    print(header("TESTE 1: LIMPEZA DE DADOS DO PURITY"))
    
    purity_handler = PurityHandler()
    
    # Testar carregamento e limpeza
    if purity_handler.load_purity_data():
        print(success("✅ Dados carregados e limpos com sucesso"))
        
        # Verificar dados únicos
        commits = purity_handler.get_all_purity_commits(limit=10)
        if commits:
            print(success(f"✅ Obtidos {len(commits)} commits processados"))
            
            # Mostrar estatísticas
            floss_count = sum(1 for c in commits if c['type'] == 'floss')
            pure_count = sum(1 for c in commits if c['type'] == 'pure')
            conflict_count = sum(1 for c in commits if c.get('had_classification_conflict', False))
            
            print(info(f"Tipos encontrados: {floss_count} floss, {pure_count} pure"))
            if conflict_count > 0:
                print(warning(f"Conflitos resolvidos: {conflict_count}"))
            
            return True
        else:
            print(error("❌ Falha ao obter commits"))
            return False
    else:
        print(error("❌ Falha ao carregar dados"))
        return False

def test_llm_json_extraction():
    """Testa a extração robusta de JSON do LLM."""
    print(header("TESTE 2: EXTRAÇÃO ROBUSTA DE JSON"))
    
    llm_handler = LLMHandler()
    
    # Simular diferentes tipos de resposta problemática
    test_responses = [
        # Resposta com JSON válido
        '```json\n{"repository": "test", "commit_hash_current": "abc123", "refactoring_type": "pure", "justification": "Test"}\n```',
        
        # Resposta com texto antes do JSON
        'This is a pure refactoring because it only changes structure.\n\n{"repository": "test", "commit_hash_current": "abc123", "refactoring_type": "pure", "justification": "Only structural changes"}',
        
        # Resposta sem JSON válido, mas com palavras-chave
        'This commit represents pure refactoring with no behavioral changes. The changes are purely structural.',
        
        # Resposta com JSON malformado
        '{"repository": "test", "refactoring_type": "floss", "justification": "Contains bug fixes',
        
        # Resposta muito confusa
        'The changes seem to be related to code improvement and some modifications...'
    ]
    
    commit_data = {
        'repository': 'test-repo',
        'commit_hash_before': 'before123',
        'commit_hash_current': 'current123',
        'commit_message': 'Test commit',
        'diff': 'test diff content'
    }
    
    successful_extractions = 0
    
    for i, response in enumerate(test_responses, 1):
        print(progress(f"Testando resposta {i}..."))
        
        # Usar método de extração diretamente
        result = llm_handler._extract_json_from_response(response, commit_data)
        
        if result:
            print(success(f"✅ Extração {i} bem-sucedida"))
            print(dim(f"   Tipo: {result.get('refactoring_type', 'N/A')}"))
            successful_extractions += 1
        else:
            # Testar fallback
            fallback = llm_handler._create_fallback_result(response, commit_data)
            if fallback:
                print(warning(f"⚠️ Extração {i} via fallback"))
                print(dim(f"   Tipo: {fallback.get('refactoring_type', 'N/A')}"))
                successful_extractions += 1
            else:
                print(error(f"❌ Extração {i} falhou completamente"))
    
    success_rate = (successful_extractions / len(test_responses)) * 100
    print(info(f"Taxa de sucesso: {success_rate:.1f}% ({successful_extractions}/{len(test_responses)})"))
    
    return successful_extractions >= 4  # Esperamos pelo menos 4/5 sucessos

def test_field_validation():
    """Testa a validação e preenchimento de campos."""
    print(header("TESTE 3: VALIDAÇÃO DE CAMPOS"))
    
    llm_handler = LLMHandler()
    
    # Teste com dados incompletos
    incomplete_result = {
        'refactoring_type': 'pure',
        # Faltando outros campos
    }
    
    commit_data = {
        'repository': 'test-repo',
        'commit_hash_before': 'before123',
        'commit_hash_current': 'current123',
        'commit_message': 'Test commit'
    }
    
    validated = llm_handler._ensure_required_fields(incomplete_result, commit_data)
    
    required_fields = ['repository', 'commit_hash_before', 'commit_hash_current', 'refactoring_type', 'justification']
    
    all_present = all(field in validated and validated[field] for field in required_fields)
    
    if all_present:
        print(success("✅ Todos os campos obrigatórios foram preenchidos"))
        return True
    else:
        missing = [field for field in required_fields if field not in validated or not validated[field]]
        print(error(f"❌ Campos faltando: {missing}"))
        return False

def run_all_tests():
    """Executa todos os testes."""
    print(header("EXECUTANDO TESTES DAS MELHORIAS"))
    
    tests = [
        ("Limpeza de dados Purity", test_purity_data_cleaning),
        ("Extração robusta JSON", test_llm_json_extraction),
        ("Validação de campos", test_field_validation)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{progress('=' * 50)}")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(error(f"Erro no teste '{test_name}': {e}"))
            results.append((test_name, False))
    
    # Resumo final
    print(f"\n{header('=' * 50)}")
    print(header("RESUMO DOS TESTES"))
    print(f"{header('=' * 50)}")
    
    passed = 0
    for test_name, result in results:
        status = success("✅ PASSOU") if result else error("❌ FALHOU")
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    total = len(results)
    print(f"\n{info(f'Resultado final: {passed}/{total} testes passaram')}")
    
    if passed == total:
        print(success("🎉 Todas as melhorias estão funcionando!"))
    else:
        print(warning("⚠️ Algumas melhorias precisam de ajustes"))

if __name__ == "__main__":
    run_all_tests()
