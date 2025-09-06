#!/usr/bin/env python3
"""
Script para testar e monitorar a performance do DeepSeek
"""

import os
import time
import sys
from pathlib import Path

# Adicionar src ao path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.handlers.optimized_llm_handler import OptimizedLLMHandler
from src.core.config import set_llm_model
from src.utils.colors import *

def test_deepseek_performance():
    """Testa a performance do DeepSeek com múltiplas análises"""
    
    print(header("🧪 TESTE DE PERFORMANCE DO DEEPSEEK"))
    
    # Configurar para usar DeepSeek
    models_available = ["deepseek-r1:8b", "deepseek-r1:1.5b"]
    
    # Tentar encontrar um modelo DeepSeek disponível
    selected_model = None
    for model in models_available:
        try:
            import subprocess
            result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
            if model in result.stdout:
                selected_model = model
                break
        except:
            pass
    
    if not selected_model:
        print(error("❌ Nenhum modelo DeepSeek encontrado. Modelos disponíveis:"))
        os.system("ollama list")
        return
    
    print(success(f"✅ Usando modelo: {selected_model}"))
    set_llm_model(selected_model)
    
    # Criar handler otimizado
    handler = OptimizedLLMHandler()
    
    # Diff de teste (simples)
    test_diff = """diff --git a/src/example.py b/src/example.py
index 1234567..abcdefg 100644
--- a/src/example.py
+++ b/src/example.py
@@ -1,10 +1,10 @@
 def calculate_sum(a, b):
-    result = a + b
-    return result
+    return a + b
 
 def process_data(data):
-    processed = []
-    for item in data:
-        processed.append(item * 2)
-    return processed
+    return [item * 2 for item in data]
 
 class Calculator:
     def add(self, x, y):
         return x + y"""
    
    # Realizar múltiplos testes
    print(info("🔄 Executando 10 análises para monitorar performance..."))
    print(dim("(Monitoramento DeepSeek ativo - deve ver mensagens de tracking)"))
    
    durations = []
    for i in range(10):
        print(f"\n{dim(f'--- Análise {i+1}/10 ---')}")
        
        start_time = time.time()
        
        result = handler.analyze_commit(
            repository="test/repo",
            commit1="abc123",
            commit2="def456", 
            commit_message=f"Test commit {i+1}: Refactor code structure",
            diff=test_diff,
            show_prompt=False
        )
        
        end_time = time.time()
        duration = end_time - start_time
        durations.append(duration)
        
        if result:
            print(success(f"✅ Análise {i+1} concluída em {duration:.1f}s - Tipo: {result.get('refactoring_type', 'N/A')}"))
        else:
            print(error(f"❌ Análise {i+1} falhou em {duration:.1f}s"))
        
        # Pausa pequena entre análises
        time.sleep(1)
    
    # Análise dos resultados
    print(f"\n{header('📊 RESULTADOS DO TESTE')}")
    print(f"Modelo testado: {selected_model}")
    print(f"Total de análises: {len(durations)}")
    print(f"Tempo médio: {sum(durations)/len(durations):.1f}s")
    print(f"Tempo mínimo: {min(durations):.1f}s")
    print(f"Tempo máximo: {max(durations):.1f}s")
    
    # Detectar degradação
    first_half = durations[:5]
    second_half = durations[5:]
    avg_first = sum(first_half) / len(first_half)
    avg_second = sum(second_half) / len(second_half)
    
    if avg_second > avg_first * 1.5:
        print(warning(f"⚠️  DEGRADAÇÃO DETECTADA: {avg_first:.1f}s → {avg_second:.1f}s (+{((avg_second/avg_first-1)*100):.0f}%)"))
    else:
        print(success(f"✅ Performance estável: {avg_first:.1f}s → {avg_second:.1f}s"))
    
    # Timeline detalhada
    print(f"\n{dim('Timeline detalhada:')}")
    for i, duration in enumerate(durations, 1):
        status = "🔴" if duration > avg_first * 2 else "🟡" if duration > avg_first * 1.5 else "🟢"
        print(f"  {status} Análise {i:2d}: {duration:5.1f}s")

if __name__ == "__main__":
    test_deepseek_performance()