#!/usr/bin/env python3
"""
Script para testar as correções implementadas.
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
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.handlers.data_handler import DataHandler
from src.analyzers.optimized_llm_handler import OptimizedLLMHandler
from src.utils.colors import *

def test_deduplication():
    """Testa a deduplicação de commits."""
    print(f"\n{header('TESTE 1: DEDUPLICAÇÃO DE COMMITS')}")
    
    data_handler = DataHandler()
    
    # Carregar dados
    if not data_handler.load_data():
        print(error("Falha ao carregar dados"))
        return False
    
    print(f"{info('Dados originais carregados:')} {len(data_handler.data)} registros")
    
    # Verificar duplicatas antes da filtragem
    print(f"\n{warning('Verificando duplicatas no dataset original...')}")
    stats = data_handler.check_dataset_duplicates()
    
    # Aplicar filtros
    if not data_handler.filter_data():
        print(error("Falha ao filtrar dados"))
        return False
    
    print(f"{success('Dados após filtragem:')} {len(data_handler.filtered_data)} registros")
    
    # Verificar se há duplicatas nos dados filtrados
    if len(data_handler.filtered_data['commit2'].unique()) == len(data_handler.filtered_data):
        print(success("✅ Deduplicação funcionando - nenhuma duplicata encontrada nos dados filtrados"))
        return True
    else:
        duplicates = len(data_handler.filtered_data) - len(data_handler.filtered_data['commit2'].unique())
        print(error(f"❌ Ainda há {duplicates} duplicatas nos dados filtrados"))
        return False

def test_json_failure_handling():
    """Testa o tratamento de falhas JSON."""
    print(f"\n{header('TESTE 2: TRATAMENTO DE FALHAS JSON')}")
    
    llm_handler = OptimizedLLMHandler()
    
    # Simular falha JSON
    test_commit_hash = "test123456789"
    test_repository = "https://github.com/test/repo"
    test_commit_message = "Teste de commit"
    test_llm_response = "Esta é uma resposta inválida do LLM sem JSON válido"
    test_error_msg = "Teste de falha JSON"
    
    print(f"{info('Simulando falha JSON...')}")
    
    # Remover arquivo de falhas se existir para teste limpo
    if os.path.exists(llm_handler.failures_file):
        os.remove(llm_handler.failures_file)
    
    # Simular salvamento de falha
    llm_handler.save_json_failure(
        commit_hash=test_commit_hash,
        repository=test_repository, 
        commit_message=test_commit_message,
        raw_response=test_llm_response,
        error_msg=test_error_msg
    )
    
    # Verificar se arquivo foi criado
    if os.path.exists(llm_handler.failures_file):
        print(success(f"✅ Arquivo de falhas criado: {llm_handler.failures_file}"))
        
        # Verificar conteúdo
        import json
        try:
            with open(llm_handler.failures_file, 'r') as f:
                failures = json.load(f)
            
            if len(failures) == 1 and failures[0]['commit_hash'] == test_commit_hash:
                print(success("✅ Falha JSON salva corretamente"))
                
                # Limpar arquivo de teste
                os.remove(llm_handler.failures_file)
                return True
            else:
                print(error("❌ Conteúdo do arquivo de falhas incorreto"))
                return False
        except Exception as e:
            print(error(f"❌ Erro ao ler arquivo de falhas: {e}"))
            return False
    else:
        print(error("❌ Arquivo de falhas não foi criado"))
        return False

def main():
    """Executa todos os testes."""
    print(f"{header('EXECUTANDO TESTES DAS CORREÇÕES IMPLEMENTADAS')}")
    
    test_results = []
    
    # Teste 1: Deduplicação
    test_results.append(test_deduplication())
    
    # Teste 2: Tratamento de falhas JSON
    test_results.append(test_json_failure_handling())
    
    # Resumo dos testes
    print(f"\n{header('RESUMO DOS TESTES')}")
    passed = sum(test_results)
    total = len(test_results)
    
    print(f"{info('Testes executados:')} {total}")
    print(f"{success('Testes aprovados:')} {passed}")
    print(f"{error('Testes falharam:')} {total - passed}")
    
    if passed == total:
        print(f"\n{success('🎉 TODOS OS TESTES PASSARAM!')}")
        print(f"{info('As correções foram implementadas com sucesso:')}")
        print(f"  • Deduplicação de commits por commit2")
        print(f"  • Tratamento e salvamento de falhas JSON")
    else:
        print(f"\n{error('❌ ALGUNS TESTES FALHARAM')}")
        print(f"{warning('Verifique as implementações e tente novamente.')}")

if __name__ == "__main__":
    main()
