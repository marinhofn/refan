#!/usr/bin/env python3
"""
Demonstração focada na análise de dados com AMBAS classificações (Purity + LLM)
Interface específica para trabalhar apenas com commits já classificados por ambos sistemas.
"""

import sys
from pathlib import Path

# Configurar paths para imports funcionarem quando executado diretamente
if __name__ == "__main__":
    # Adicionar o diretório raiz do projeto ao path
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))


import os
import sys
from datetime import datetime
from src.handlers.llm_visualization_handler import LLMVisualizationHandler
from analyze_dual_classifications import DualClassificationAnalyzer

def show_dual_classification_status():
    """Mostra o status dos dados com ambas classificações."""
    
    print("📊 Status dos Dados com Ambas Classificações")
    print("=" * 50)
    
    analyzer = DualClassificationAnalyzer()
    dual_data = analyzer.extract_dual_classified_data()
    
    if dual_data is not None and len(dual_data) > 0:
        print(f"\n✅ Dados disponíveis: {len(dual_data)} commits")
        
        # Mostrar estatísticas detalhadas
        print(f"\n📈 Distribuição Detalhada:")
        
        # Por Purity
        purity_counts = dual_data['purity_analysis'].value_counts()
        print(f"\n🔍 Classificação Purity:")
        for purity, count in purity_counts.items():
            percentage = count / len(dual_data) * 100
            print(f"   {purity:6}: {count:2} commits ({percentage:5.1f}%)")
        
        # Por LLM
        llm_counts = dual_data['llm_analysis'].value_counts()
        print(f"\n🤖 Classificação LLM:")
        for llm, count in llm_counts.items():
            percentage = count / len(dual_data) * 100
            print(f"   {llm:6}: {count:2} commits ({percentage:5.1f}%)")
        
        # Acordos/Desacordos
        dual_data_copy = dual_data.copy()
        dual_data_copy['purity_norm'] = dual_data_copy['purity_analysis'].map({
            'TRUE': 'PURE', 'FALSE': 'FLOSS', 'NONE': 'UNKNOWN'
        })
        dual_data_copy['agreement'] = dual_data_copy['purity_norm'] == dual_data_copy['llm_analysis']
        
        agreements = dual_data_copy['agreement'].sum()
        disagreements = len(dual_data_copy) - agreements
        agreement_rate = agreements / len(dual_data_copy) * 100
        
        print(f"\n🎯 Acordo/Desacordo:")
        print(f"   Acordos:     {agreements:2} commits ({agreement_rate:5.1f}%)")
        print(f"   Desacordos:  {disagreements:2} commits ({100-agreement_rate:5.1f}%)")
        
        return True
    else:
        print("\n❌ Nenhum dado com ambas classificações encontrado")
        print("\n💡 Para gerar dados:")
        print("   1. Execute mais análises LLM: python run_llm_analysis.py")
        print("   2. Depois execute: python analyze_dual_classifications.py")
        return False

def main():
    """Função principal para análise de dados com ambas classificações."""
    
    print("🔍 ANÁLISE DE DADOS COM AMBAS CLASSIFICAÇÕES")
    print("=" * 50)
    
    # Verificar status dos dados
    has_data = show_dual_classification_status()
    
    if not has_data:
        return
    
    # Menu de opções
    while True:
        print(f"\n🎯 Opções de Análise (Dados com Ambas Classificações):")
        print("1. 📊 Gerar novo CSV de comparação")
        print("2. 📈 Criar visualizações específicas")
        print("3. 🎨 Dashboard interativo completo")
        print("4. 📦 Exportar pacote de análise")
        print("5. 📋 Relatório detalhado de desacordos")
        print("6. 🔄 Atualizar dados (re-extrair)")
        print("0. ❌ Sair")
        
        choice = input(f"\nEscolha uma opção (0-6): ").strip()
        
        if choice == "0":
            print("👋 Saindo...")
            break
            
        elif choice == "1":
            print("\n📊 Gerando novo CSV de comparação...")
            analyzer = DualClassificationAnalyzer()
            dual_data = analyzer.extract_dual_classified_data()
            if dual_data is not None:
                csv_file = analyzer.create_comparison_csv(dual_data, include_repository_info=True)
                stats = analyzer.analyze_agreements(dual_data)
                report_file = analyzer.save_analysis_report(stats, csv_file)
                print(f"\n✅ Arquivos gerados:")
                print(f"   📄 CSV: {csv_file}")
                print(f"   📊 Relatório: {report_file}")
                
        elif choice == "2":
            print("\n📈 Criando visualizações específicas...")
            handler = LLMVisualizationHandler()
            try:
                df = handler.load_comparison_data(prefer_dual_classification=True)
                print(f"✅ Dados carregados: {len(df)} comparações")
                
                # Criar visualizações individuais
                timestamp = datetime.now().strftime("%H-%M-%S")
                
                # Agreement overview
                agreement_fig = handler.create_agreement_overview(df)
                agreement_path = f"dual_agreement_chart_{timestamp}.html"
                agreement_fig.write_html(agreement_path)
                print(f"   📊 Gráfico de acordo: {agreement_path}")
                
                # Confusion matrix
                confusion_fig = handler.create_confusion_matrix(df)
                confusion_path = f"dual_confusion_matrix_{timestamp}.html"
                confusion_fig.write_html(confusion_path)
                print(f"   🔄 Matriz de confusão: {confusion_path}")
                
                # Repository analysis
                repo_fig = handler.create_repository_analysis(df)
                repo_path = f"dual_repository_analysis_{timestamp}.html"
                repo_fig.write_html(repo_path)
                print(f"   🏛️ Análise por repositório: {repo_path}")
                
                print(f"\n✅ Visualizações criadas com sucesso!")
                
            except Exception as e:
                print(f"❌ Erro: {e}")
                
        elif choice == "3":
            print("\n🎨 Criando dashboard interativo completo...")
            handler = LLMVisualizationHandler()
            try:
                dashboard_path = handler.create_comprehensive_dashboard()
                if dashboard_path:
                    print(f"✅ Dashboard criado: {dashboard_path}")
                    
                    # Tentar abrir no navegador
                    try:
                        import webbrowser
                        webbrowser.open(f"file://{os.path.abspath(dashboard_path)}")
                        print("🌐 Dashboard aberto no navegador")
                    except:
                        print("💡 Abra o arquivo HTML manualmente no navegador")
                        
            except Exception as e:
                print(f"❌ Erro: {e}")
                
        elif choice == "4":
            print("\n📦 Criando pacote completo de análise...")
            handler = LLMVisualizationHandler()
            try:
                package_path = handler.create_export_package()
                if package_path:
                    print(f"✅ Pacote criado: {package_path}")
                    print(f"📁 Contém dados, visualizações e relatórios completos")
                    
            except Exception as e:
                print(f"❌ Erro: {e}")
                
        elif choice == "5":
            print("\n📋 Analisando padrões de desacordo...")
            handler = LLMVisualizationHandler()
            try:
                df = handler.load_comparison_data(prefer_dual_classification=True)
                
                # Análise detalhada de desacordos
                disagreements = df[~df['agreement']]
                
                print(f"\n🔍 Análise de Desacordos:")
                print(f"   Total de desacordos: {len(disagreements)}")
                print(f"   Taxa de desacordo: {len(disagreements)/len(df)*100:.1f}%")
                
                print(f"\n📊 Padrões de Desacordo:")
                disagreement_patterns = disagreements.groupby(['purity_classification', 'llm_classification']).size()
                for (purity, llm), count in disagreement_patterns.items():
                    print(f"   Purity:{purity:7} → LLM:{llm:5} : {count} casos")
                
                # Salvar detalhes dos desacordos
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                disagreements_file = f"disagreements_analysis_{timestamp}.csv"
                disagreements.to_csv(disagreements_file, index=False)
                print(f"\n✅ Detalhes salvos em: {disagreements_file}")
                
            except Exception as e:
                print(f"❌ Erro: {e}")
                
        elif choice == "6":
            print("\n🔄 Atualizando dados...")
            show_dual_classification_status()
            
        else:
            print("❌ Opção inválida")

if __name__ == "__main__":
    main()
