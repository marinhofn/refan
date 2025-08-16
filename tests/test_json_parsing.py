#!/usr/bin/env python3
"""
Teste específico do parser JSON
"""

import json

def test_json_parsing():
    """Testa o parsing do JSON retornado pelo LLM."""
    
    # JSON de exemplo que falhou
    json_str = """{
    "repository": "https://github.com/alibaba/dubbo",
    "commit_hash_before": "91554bc84b8a1f022f6430a8767739673ac60449",
    "commit_hash_current": "003e400b6f9d3d35d264a4aaa6e665ff7a9c237b",
    "refactoring_type": "floss",
    "justification": "The diff contains several functional changes, including method signature modifications, new conditional logic, and exception handling changes. Specifically, there are additions of if statements, try-catch blocks, and modified return types.",
    "technical_evidence": "For example, in the file 'dubbo-common/src/main/java/com/alibaba/dubbo/common/constants/CommonConstants.java', line 104 changes from 'public static final String SERVER_KEY = \"server\";' to 'public static final String SERVER_KEY = \"server_key\";'. This change affects the behavior of the code as it modifies the constant name.",
    "confidence_level": "high",
    "diff_source": "file"
}"""

    print("Testando parsing do JSON...")
    print("JSON a ser testado:")
    print(json_str[:200] + "...")
    
    try:
        result = json.loads(json_str)
        print("✅ JSON válido!")
        print(f"Refactoring type: {result.get('refactoring_type')}")
        print(f"Confidence: {result.get('confidence_level')}")
        return result
    except json.JSONDecodeError as e:
        print(f"❌ Erro no JSON: {e}")
        return None

if __name__ == "__main__":
    test_json_parsing()
