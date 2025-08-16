#!/usr/bin/env python3
"""
Script de teste para gerar visualizações automaticamente.
"""

import sys
from pathlib import Path

# Configurar paths para imports funcionarem quando executado diretamente
if __name__ == "__main__":
    # Adicionar o diretório raiz do projeto ao path
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))


from src.handlers.visualization_handler import VisualizationHandler
from src.utils.colors import *

def test_visualization():
    """Testa a geração de visualizações automaticamente."""
    print(header("TESTE DE VISUALIZAÇÃO INTERATIVA"))
    print("=" * 50)
    
    # Criar handler de visualização
    viz_handler = VisualizationHandler()
    
    if viz_handler.analyzed_data is None or len(viz_handler.analyzed_data) == 0:
        print(error("Nenhum dado encontrado para visualização."))
        return
    
    print(success(f"Dados carregados: {len(viz_handler.analyzed_data)} commits"))
    
    # Gerar dashboard completo (HTML + PNG)
    print(info("Gerando dashboard completo..."))
    result = viz_handler.create_comprehensive_dashboard(save_html=True, save_image=True)
    
    if result:
        print(success(f"Dashboard gerado: {bold(result)}"))
    
    # Mostrar estatísticas
    stats = viz_handler.get_summary_stats()
    print(f"\n{header('ESTATÍSTICAS:')}")
    for key, value in stats.items():
        print(f"{cyan(key)}: {bold(str(value))}")

if __name__ == "__main__":
    test_visualization()
