#!/usr/bin/env python3
"""
Script para verificar se a dashboard está funcionando corretamente
"""

import sys
from pathlib import Path

# Configurar paths para imports funcionarem quando executado diretamente
if __name__ == "__main__":
    # Adicionar o diretório raiz do projeto ao path
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))


import os
import webbrowser
from src.handlers.llm_visualization_handler import LLMVisualizationHandler

def test_dashboard():
    """Testa a criação e abertura da dashboard."""
    
    print("🔍 Testando Dashboard LLM vs Purity")
    print("=" * 50)
    
    # Criar handler
    handler = LLMVisualizationHandler()
    
    try:
        # Criar dashboard
        dashboard_path = handler.create_comprehensive_dashboard()
        
        if dashboard_path and os.path.exists(dashboard_path):
            print(f"✅ Dashboard criada com sucesso: {dashboard_path}")
            
            # Verificar tamanho do arquivo
            size_bytes = os.path.getsize(dashboard_path)
            size_kb = size_bytes / 1024
            print(f"📄 Tamanho do arquivo: {size_kb:.1f} KB")
            
            # Verificar se contém emojis
            with open(dashboard_path, 'r', encoding='utf-8') as f:
                content = f.read()
                emoji_count = content.count('class="emoji"')
                print(f"😀 Emojis encontrados: {emoji_count}")
                
                # Verificar UTF-8
                if 'charset="UTF-8"' in content:
                    print("✅ Encoding UTF-8 configurado")
                else:
                    print("❌ Encoding UTF-8 não encontrado")
                
                # Verificar filtros
                if 'Apply Filters' in content:
                    print("✅ Botão Apply Filters presente")
                else:
                    print("❌ Botão Apply Filters não encontrado")
                    
                # Verificar dados corretos
                if 'hashes_no_rpt_purity_with_analysis.csv' in content:
                    print("✅ Usando arquivo de dados correto")
                else:
                    print("❌ Arquivo de dados incorreto")
            
            # Tentar abrir no navegador
            try:
                webbrowser.open(f"file://{os.path.abspath(dashboard_path)}")
                print("🌐 Dashboard aberta no navegador")
            except Exception as e:
                print(f"⚠️ Não foi possível abrir no navegador: {e}")
                print(f"💡 Abra manualmente: file://{os.path.abspath(dashboard_path)}")
            
            return True
            
        else:
            print("❌ Erro ao criar dashboard")
            return False
            
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

if __name__ == "__main__":
    test_dashboard()
