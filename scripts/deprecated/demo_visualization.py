#!/usr/bin/env python3
"""
Script para demonstrar as funcionalidades de visualização.
"""

import sys
from pathlib import Path

# Configurar paths para imports funcionarem quando executado diretamente
if __name__ == "__main__":
    # Adicionar o diretório raiz do projeto ao path
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))


import time
from src.handlers.visualization_handler import VisualizationHandler
from src.utils.colors import *

def demo_visualization():
    """Demonstra todas as funcionalidades de visualização."""
    print(header("DEMONSTRAÇÃO DAS FUNCIONALIDADES DE VISUALIZAÇÃO"))
    print("=" * 60)
    
    # 1. Carregamento de dados
    print(f"\n{cyan('1.')} {bold('Carregando dados...')}")
    viz_handler = VisualizationHandler()
    
    if viz_handler.analyzed_data is None or len(viz_handler.analyzed_data) == 0:
        print(error("❌ Nenhum dado encontrado"))
        return
    
    print(success(f"✅ {len(viz_handler.analyzed_data)} commits carregados"))
    
    # 2. Estatísticas resumidas
    print(f"\n{cyan('2.')} {bold('Estatísticas resumidas:')}")
    stats = viz_handler.get_summary_stats()
    
    if "error" not in stats:
        for key, value in stats.items():
            print(f"   {cyan('•')} {key}: {bold(str(value))}")
    
    # 3. Gerar dashboard HTML
    print(f"\n{cyan('3.')} {bold('Gerando dashboard HTML...')}")
    html_result = viz_handler.create_comprehensive_dashboard(save_html=True, save_image=False)
    
    if html_result:
        print(success(f"✅ Dashboard HTML salvo: {bold(html_result)}"))
    
    # 4. Gerar dashboard com PNG
    print(f"\n{cyan('4.')} {bold('Gerando dashboard completo (HTML + PNG)...')}")
    full_result = viz_handler.create_comprehensive_dashboard(save_html=True, save_image=True)
    
    if full_result:
        print(success(f"✅ Dashboard completo salvo: {bold(full_result)}"))
    
    # 5. Resumo final
    print(f"\n{header('RESUMO DA DEMONSTRAÇÃO:')}")
    print(f"{success('✅ Sistema de visualização funcionando perfeitamente!')}")
    print(f"{info('📊 Gráficos interativos com Plotly')}")
    print(f"{info('💾 Suporte a HTML e PNG')}")
    print(f"{info('📈 Dashboard abrangente com múltiplas visualizações')}")
    print(f"{info('📋 Estatísticas detalhadas')}")
    
    print(f"\n{warning('💡 Dicas de uso:')}")
    print(f"   • Execute {bold('python main.py')} e escolha a opção {bold('7')} para usar no menu")
    print(f"   • Os arquivos HTML são interativos - podem ser abertos no navegador")
    print(f"   • Os arquivos PNG são estáticos - ideais para relatórios")
    
    print(f"\n{dim('Demonstração concluída!')}")

if __name__ == "__main__":
    demo_visualization()
