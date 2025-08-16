#!/usr/bin/env python3
"""
Script para testar a criação da dashboard diretamente
"""

import sys
from pathlib import Path

# Configurar paths para imports funcionarem quando executado diretamente
if __name__ == "__main__":
    # Adicionar o diretório raiz do projeto ao path
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))


from src.handlers.llm_visualization_handler import LLMVisualizationHandler

def main():
    """Cria a dashboard comprehensive diretamente."""
    
    print("🎨 Criando dashboard comprehensive...")
    
    # Inicializar handler
    handler = LLMVisualizationHandler()
    
    try:
        # Criar dashboard
        dashboard_path = handler.create_comprehensive_dashboard()
        
        if dashboard_path:
            print(f"✅ Dashboard criada: {dashboard_path}")
            return dashboard_path
        else:
            print("❌ Erro ao criar dashboard")
            return None
            
    except Exception as e:
        print(f"❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    main()
