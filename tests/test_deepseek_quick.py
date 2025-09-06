#!/usr/bin/env python3
"""
Teste rápido das otimizações DeepSeek
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.handlers.optimized_llm_handler import OptimizedOllamaAdapter
from src.core.config import set_llm_model

def test_deepseek_quick():
    print("🧪 Teste rápido DeepSeek")
    
    # Configurar DeepSeek
    set_llm_model("deepseek-r1:8b")
    
    # Criar adaptador
    adapter = OptimizedOllamaAdapter("http://localhost:11434/api/generate", "deepseek-r1:8b")
    
    # Verificar se as otimizações estão ativas
    print(f"Modelo: {adapter.model}")
    print(f"DeepSeek detectado: {'deepseek' in adapter.model.lower()}")
    print(f"Contador de análises: {adapter._analysis_count}")
    
    # Fazer 3 requisições simples
    for i in range(3):
        print(f"\n--- Teste {i+1} ---")
        response = adapter.complete("Say OK", attempts=1)
        print(f"Resposta: {response}")
        print(f"Análises realizadas: {adapter._analysis_count}")

if __name__ == "__main__":
    test_deepseek_quick()