#!/usr/bin/env python3
"""
Script para testar e corrigir o JSON recebido do LLM
"""

import json
import re

def fix_json_quotes(json_str):
    """
    Corrige aspas não escapadas dentro de strings JSON.
    """
    # Encontrar strings que contêm aspas não escapadas
    # Padrão: "field": "value with "unescaped" quotes"
    
    # Primeiro, encontrar todos os campos de string
    pattern = r'"([^"]+)":\s*"([^"]*(?:"[^"]*)*[^"]*)"'
    
    def fix_quotes_in_match(match):
        field = match.group(1)
        value = match.group(2)
        
        # Escapar aspas dentro do valor
        fixed_value = value.replace('"', '\\"')
        return f'"{field}": "{fixed_value}"'
    
    # Aplicar correção
    fixed_json = re.sub(pattern, fix_quotes_in_match, json_str)
    return fixed_json

def test_json_fix():
    """Testa a correção do JSON."""
    
    # JSON problemático da resposta mais recente
    problematic_json = """{
    "repository": "https://github.com/alibaba/dubbo",
    "commit_hash_before": "91554bc84b8a1f022f6430a8767739673ac60449",
    "commit_hash_current": "003e400b6f9d3d35d264a4aaa6e665ff7a9c237b",
    "refactoring_type": "floss",
    "justification": "The diff contains several functional changes, including method signature modifications, new conditional logic, and exception handling changes. Specifically, there are additions of if statements, try-catch blocks, and modified return types.",
    "technical_evidence": "For example, in the file 'dubbo-common/src/main/java/com/alibaba/dubbo/common/constants/CommonConstants.java', line 104 changes from 'public static final String SERVER_KEY = "server";' to 'public static final String SERVER_KEY = "server_key";'. This change affects the behavior of the code as it modifies the constant name.",
    "confidence_level": "high",
    "diff_source": "file"
}"""

    print("JSON original:")
    print(problematic_json[:300] + "...")
    
    try:
        result = json.loads(problematic_json)
        print("✅ JSON original é válido!")
        return result
    except json.JSONDecodeError as e:
        print(f"❌ JSON original inválido: {e}")
        
        print("\nTentando corrigir...")
        fixed_json = fix_json_quotes(problematic_json)
        
        try:
            result = json.loads(fixed_json)
            print("✅ JSON corrigido é válido!")
            print(f"Refactoring type: {result.get('refactoring_type')}")
            return result
        except json.JSONDecodeError as e2:
            print(f"❌ Correção falhou: {e2}")
            return None

if __name__ == "__main__":
    test_json_fix()
