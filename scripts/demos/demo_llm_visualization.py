#!/usr/bin/env python3
"""
Script de demonstração e teste das funcionalidades de visualização LLM avançadas.
Inclui barra de progresso, exportação múltipla e dashboard interativo.
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

def main():
    """Função principal para demonstração das funcionalidades."""
    
    print("🔍 LLM Analysis Visualization Demo")
    print("=" * 50)
    
    # Verificar se existem dados para análise
    handler = LLMVisualizationHandler()
    
    try:
        # Carregar dados
        print("\n📊 Loading analysis data...")
        df = handler.load_comparison_data()
        sessions = handler.load_analysis_sessions()
        
        print(f"✅ Loaded {len(df)} comparison records")
        print(f"✅ Found {len(sessions)} analysis sessions")
        
        # Mostrar estatísticas básicas
        print(f"\n📈 Quick Statistics:")
        print(f"   • Total comparisons: {len(df):,}")
        print(f"   • Agreement rate: {(df['agreement'].mean() * 100):.1f}%")
        print(f"   • Repositories: {df['repository'].nunique()}")
        print(f"   • Purity PURE: {(df['purity_classification'] == 'PURE').sum()}")
        print(f"   • LLM PURE: {(df['llm_classification'] == 'PURE').sum()}")
        
        # Menu de opções
        while True:
            print(f"\n🎯 Available Options:")
            print("1. Create Comprehensive Dashboard")
            print("2. Create Progress Dashboard")
            print("3. Export Data (Multiple Formats)")
            print("4. Create Individual Visualizations")
            print("5. Show Session Timeline")
            print("6. Export All & Create Dashboard")
            print("7. Create Complete Export Package")
            print("0. Exit")
            
            choice = input("\nChoose option (0-7): ").strip()
            
            if choice == "0":
                print("👋 Exiting...")
                break
                
            elif choice == "1":
                print("\n🎨 Creating comprehensive dashboard...")
                dashboard_path = handler.create_comprehensive_dashboard()
                if dashboard_path:
                    print(f"✅ Dashboard created: {dashboard_path}")
                    
                    # Tentar abrir no navegador
                    try:
                        import webbrowser
                        webbrowser.open(f"file://{os.path.abspath(dashboard_path)}")
                        print("🌐 Dashboard opened in browser")
                    except:
                        print("💡 Open the HTML file manually in your browser")
                        
            elif choice == "2":
                print("\n📊 Creating progress dashboard...")
                progress_fig = handler.create_progress_dashboard()
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                progress_path = f"progress_dashboard_{timestamp}.html"
                progress_fig.write_html(progress_path)
                print(f"✅ Progress dashboard saved: {progress_path}")
                
            elif choice == "3":
                print("\n💾 Exporting data in multiple formats...")
                exported = handler.export_analysis_data()
                if exported:
                    print("✅ Export completed:")
                    for format_type, path in exported.items():
                        print(f"   📄 {format_type.upper()}: {path}")
                        
            elif choice == "4":
                print("\n🎨 Creating individual visualizations...")
                
                # Agreement overview
                agreement_fig = handler.create_agreement_overview(df)
                agreement_path = f"agreement_chart_{datetime.now().strftime('%H-%M-%S')}.html"
                agreement_fig.write_html(agreement_path)
                print(f"   ✅ Agreement chart: {agreement_path}")
                
                # Confusion matrix
                confusion_fig = handler.create_confusion_matrix(df)
                confusion_path = f"confusion_matrix_{datetime.now().strftime('%H-%M-%S')}.html"
                confusion_fig.write_html(confusion_path)
                print(f"   ✅ Confusion matrix: {confusion_path}")
                
                # Repository analysis
                repo_fig = handler.create_repository_analysis(df)
                repo_path = f"repository_analysis_{datetime.now().strftime('%H-%M-%S')}.html"
                repo_fig.write_html(repo_path)
                print(f"   ✅ Repository analysis: {repo_path}")
                
            elif choice == "5":
                print("\n⏱️ Creating session timeline...")
                timeline_fig = handler.create_timeline_analysis(sessions)
                timeline_path = f"session_timeline_{datetime.now().strftime('%H-%M-%S')}.html"
                timeline_fig.write_html(timeline_path)
                print(f"✅ Timeline chart: {timeline_path}")
                
            elif choice == "6":
                print("\n🚀 Complete export and dashboard creation...")
                
                # Export data
                exported = handler.export_analysis_data()
                
                # Create dashboard
                dashboard_path = handler.create_comprehensive_dashboard()
                
                # Create summary
                print("\n📋 Complete Export Summary:")
                print("Data Exports:")
                for format_type, path in exported.items():
                    print(f"   📄 {format_type.upper()}: {path}")
                    
                if dashboard_path:
                    print(f"\n🎨 Dashboard: {dashboard_path}")
                    
                    # Try to open dashboard
                    try:
                        import webbrowser
                        webbrowser.open(f"file://{os.path.abspath(dashboard_path)}")
                        print("🌐 Dashboard opened in browser")
                    except:
                        print("💡 Open the HTML file manually to view the dashboard")
                        
                print("\n✨ All files ready for sharing and analysis!")
                
            elif choice == "7":
                print("\n📦 Creating complete export package...")
                package_path = handler.create_export_package()
                
                if package_path:
                    print(f"\n✅ Complete package created: {package_path}/")
                    print("\n📋 Package contents:")
                    print("   📊 Data files (CSV, JSON, Excel)")
                    print("   🎨 Interactive HTML dashboard")
                    print("   📈 Individual chart files")
                    print("   📄 README with instructions")
                    print("\n💡 This package contains everything needed for sharing and analysis!")
                else:
                    print("❌ Failed to create export package")
                
            else:
                print("❌ Invalid option. Please choose 0-7.")
                
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        print("\n💡 Possible solutions:")
        print("   1. Run LLM analysis first to generate comparison data")
        print("   2. Check if CSV files exist in the csv/ directory")
        print("   3. Verify that analysis sessions were saved in analises/ directory")
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        print("\n🔍 Debug information:")
        traceback.print_exc()

def show_file_structure():
    """Mostra a estrutura de arquivos relacionados à análise."""
    
    print("\n📁 Current file structure:")
    
    # Check CSV files
    print("\n📊 CSV Files:")
    csv_dir = "csv"
    if os.path.exists(csv_dir):
        for file in os.listdir(csv_dir):
            if "purity" in file.lower() or "llm" in file.lower():
                file_path = os.path.join(csv_dir, file)
                size = os.path.getsize(file_path) / 1024  # KB
                print(f"   📄 {file} ({size:.1f} KB)")
    else:
        print("   ❌ CSV directory not found")
    
    # Check analysis files
    print("\n📈 Analysis Sessions:")
    analysis_dir = "analises"
    if os.path.exists(analysis_dir):
        analysis_files = [f for f in os.listdir(analysis_dir) if f.endswith('.json')]
        for file in analysis_files[-5:]:  # Show last 5
            file_path = os.path.join(analysis_dir, file)
            size = os.path.getsize(file_path) / 1024  # KB
            print(f"   📄 {file} ({size:.1f} KB)")
        if len(analysis_files) > 5:
            print(f"   ... and {len(analysis_files) - 5} more files")
    else:
        print("   ❌ Analysis directory not found")

if __name__ == "__main__":
    # Show file structure first
    show_file_structure()
    
    # Run main demo
    main()
