#!/usr/bin/env python3
"""
Script Simples para Análise de Dados com Ambas Classificações
Foco exclusivo nos commits já classificados por Purity E LLM
"""

import sys
from pathlib import Path

# Configurar paths para imports funcionarem quando executado diretamente
if __name__ == "__main__":
    # Adicionar o diretório raiz do projeto ao path
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))


import pandas as pd
import os
from datetime import datetime

def show_summary():
    """Mostra resumo dos dados disponíveis."""
    
    print("📊 RESUMO DOS DADOS COM AMBAS CLASSIFICAÇÕES")
    print("=" * 50)
    
    # Carregar dados principais
    df = pd.read_csv("csv/hashes_no_rpt_purity_with_analysis.csv")
    
    # Filtrar dados com ambas classificações
    both_classified = df[
        (df['purity_analysis'].notna()) & 
        (df['llm_analysis'].notna()) & 
        (df['llm_analysis'] != '') & 
        (df['llm_analysis'] != 'FAILED') &
        (df['llm_analysis'] != 'ERROR')
    ]
    
    total = len(df)
    classified = len(both_classified)
    
    print(f"📈 Status Geral:")
    print(f"   Total de commits: {total:,}")
    print(f"   Com ambas classificações: {classified}")
    print(f"   Percentual pronto para análise: {classified/total*100:.1f}%")
    
    if classified > 0:
        # Análise de acordo/desacordo
        both_classified_copy = both_classified.copy()
        both_classified_copy['purity_norm'] = both_classified_copy['purity_analysis'].map({
            'TRUE': 'PURE', 'FALSE': 'FLOSS', 'NONE': 'UNKNOWN'
        })
        both_classified_copy['agreement'] = (
            both_classified_copy['purity_norm'] == both_classified_copy['llm_analysis']
        )
        
        agreements = both_classified_copy['agreement'].sum()
        disagreements = classified - agreements
        agreement_rate = agreements / classified * 100
        
        print(f"\n🎯 Análise de Concordância:")
        print(f"   Acordos: {agreements} ({agreement_rate:.1f}%)")
        print(f"   Desacordos: {disagreements} ({100-agreement_rate:.1f}%)")
        
        # Top padrões de desacordo
        print(f"\n❌ Principais Padrões de Desacordo:")
        disagreements_data = both_classified_copy[~both_classified_copy['agreement']]
        patterns = disagreements_data.groupby(['purity_analysis', 'llm_analysis']).size().sort_values(ascending=False)
        
        for (purity, llm), count in patterns.head(3).items():
            print(f"   Purity:{purity} → LLM:{llm}: {count} casos")
    
    return classified > 0

def quick_analysis():
    """Análise rápida e criação de arquivos."""
    
    print("\n🔄 Executando análise rápida...")
    
    # Executar análise dual
    os.system("python analyze_dual_classifications.py")
    
    print("\n✅ Análise completa! Arquivos criados:")
    print("   📄 CSV de comparação")
    print("   📊 Relatório JSON")
    
def create_visualizations():
    """Cria visualizações dos dados."""
    
    print("\n🎨 Criando visualizações...")
    
    try:
        from src.handlers.llm_visualization_handler import LLMVisualizationHandler
        
        handler = LLMVisualizationHandler()
        
        # Dashboard completo
        dashboard_path = handler.create_comprehensive_dashboard()
        print(f"✅ Dashboard criado: {dashboard_path}")
        
        # Visualizações individuais
        df = handler.load_comparison_data(prefer_dual_classification=True)
        timestamp = datetime.now().strftime("%H-%M-%S")
        
        # Agreement chart
        agreement_fig = handler.create_agreement_overview(df)
        agreement_path = f"focus_agreement_{timestamp}.html"
        agreement_fig.write_html(agreement_path)
        
        # Confusion matrix
        confusion_fig = handler.create_confusion_matrix(df)
        confusion_path = f"focus_confusion_{timestamp}.html"
        confusion_fig.write_html(confusion_path)
        
        print(f"✅ Gráficos individuais:")
        print(f"   📊 Acordo/Desacordo: {agreement_path}")
        print(f"   🔄 Matriz de Confusão: {confusion_path}")
        
    except Exception as e:
        print(f"❌ Erro na visualização: {e}")

def analyze_disagreements():
    """Analisa casos de desacordo em detalhes."""
    
    print("\n🔍 ANÁLISE DETALHADA DE DESACORDOS")
    print("=" * 40)
    
    # Carregar dados duais
    dual_files = [f for f in os.listdir("csv") if f.startswith("dual_classification_comparison")]
    if not dual_files:
        print("❌ Execute primeiro a análise dual: python analyze_dual_classifications.py")
        return
    
    latest_file = max(dual_files, key=lambda f: os.path.getctime(os.path.join("csv", f)))
    df = pd.read_csv(os.path.join("csv", latest_file))
    
    # Filtrar desacordos
    disagreements = df[~df['agreement']]
    
    print(f"📊 Estatísticas de Desacordo:")
    print(f"   Total de desacordos: {len(disagreements)}")
    print(f"   Taxa de desacordo: {len(disagreements)/len(df)*100:.1f}%")
    
    # Padrões mais comuns
    print(f"\n📈 Padrões de Desacordo:")
    patterns = disagreements.groupby(['purity_classification', 'llm_classification']).size().sort_values(ascending=False)
    
    for (purity, llm), count in patterns.items():
        percentage = count / len(disagreements) * 100
        print(f"   {purity:6} → {llm:5}: {count:2} casos ({percentage:5.1f}%)")
    
    # Exemplos específicos
    print(f"\n🔍 Exemplos de Desacordos:")
    for (purity, llm), count in patterns.head(2).items():
        print(f"\n   Caso: Purity={purity} vs LLM={llm}")
        examples = disagreements[
            (disagreements['purity_classification'] == purity) & 
            (disagreements['llm_classification'] == llm)
        ].head(2)
        
        for _, row in examples.iterrows():
            commit_short = row['commit_hash'][:8]
            repo = row.get('project_name', 'unknown')
            print(f"     • {commit_short}... ({repo})")

def main():
    """Menu principal simplificado."""
    
    print("🎯 ANÁLISE FOCADA - DADOS COM AMBAS CLASSIFICAÇÕES")
    print("=" * 55)
    
    # Mostrar status
    has_data = show_summary()
    
    if not has_data:
        print(f"\n💡 Para gerar dados com ambas classificações:")
        print("   1. Execute: python run_llm_analysis.py --max-commits 50")
        print("   2. Depois: python analyze_dual_classifications.py")
        return
    
    print(f"\n🚀 Ações Disponíveis:")
    print("1. 📊 Gerar análise completa")
    print("2. 🎨 Criar visualizações")  
    print("3. 🔍 Analisar desacordos")
    print("4. 📦 Pacote completo")
    
    choice = input(f"\nEscolha (1-4): ").strip()
    
    if choice == "1":
        quick_analysis()
    elif choice == "2":
        create_visualizations()
    elif choice == "3":
        analyze_disagreements()
    elif choice == "4":
        quick_analysis()
        create_visualizations()
        print(f"\n🎉 Pacote completo criado!")
    else:
        print("❌ Opção inválida")

if __name__ == "__main__":
    main()
