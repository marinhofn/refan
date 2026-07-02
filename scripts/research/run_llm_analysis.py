#!/usr/bin/env python3
"""
Script principal para análise LLM dos commits de refatoramento.
Demonstra todas as funcionalidades implementadas.
"""

import sys
from pathlib import Path

# Configurar paths para imports funcionarem quando executado diretamente
if __name__ == "__main__":
    # Adicionar o diretório raiz do projeto ao path
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))


from src.analyzers.llm_purity_analyzer import LLMPurityAnalyzer
import json
import argparse

def main():
    """Função principal com interface de linha de comando."""
    
    parser = argparse.ArgumentParser(description="Análise LLM de Commits de Refatoramento")
    parser.add_argument('--action', choices=['analyze', 'summary', 'test'], 
                       default='analyze', help='Ação a executar')
    parser.add_argument('--max-commits', type=int, 
                       help='Número máximo de commits para analisar')
    parser.add_argument('--purity-filter', choices=['TRUE', 'FALSE', 'NONE'],
                       help='Filtrar por classificação Purity')
    parser.add_argument('--include-analyzed', action='store_true',
                       help='Incluir commits já analisados')
    
    args = parser.parse_args()
    
    # Criar analisador
    analyzer = LLMPurityAnalyzer()
    
    if args.action == 'summary':
        print_summary(analyzer)
    elif args.action == 'test':
        test_analyzer(analyzer)
    else:  # analyze
        run_analysis(analyzer, args)

def print_summary(analyzer):
    """Imprime resumo das análises existentes."""
    print("📊 RESUMO DAS ANÁLISES EXISTENTES")
    print("=" * 50)
    
    summary = analyzer.get_analysis_summary()
    if not summary:
        print("❌ Erro ao gerar resumo")
        return
    
    print(f"📈 Total de hashes: {summary['total_hashes']:,}")
    print(f"✅ Análises concluídas: {summary['completed_analyses']:,}")
    print(f"⏳ Análises pendentes: {summary['pending_analyses']:,}")
    
    print(f"\n📋 DISTRIBUIÇÃO PURITY:")
    for category, count in summary['purity_distribution'].items():
        percentage = (count / summary['total_hashes']) * 100
        print(f"  {category}: {count:,} ({percentage:.1f}%)")
    
    print(f"\n🤖 DISTRIBUIÇÃO LLM:")
    for category, count in summary['llm_distribution'].items():
        percentage = (count / summary['total_hashes']) * 100
        print(f"  {category}: {count:,} ({percentage:.1f}%)")
    
    if summary['completed_analyses'] > 0:
        print(f"\n🎯 ANÁLISE CRUZADA (Purity vs LLM):")
        cross_data = summary['cross_analysis']
        if 'All' in cross_data:
            del cross_data['All']  # Remover totais
        
        for purity_cat, llm_data in cross_data.items():
            if isinstance(llm_data, dict) and 'All' in llm_data:
                del llm_data['All']  # Remover totais
                print(f"  Purity {purity_cat}:")
                for llm_cat, count in llm_data.items():
                    if count > 0:
                        print(f"    → LLM {llm_cat}: {count}")

def test_analyzer(analyzer):
    """Executa teste básico do analisador."""
    print("🧪 TESTE DO ANALISADOR")
    print("=" * 30)
    
    stats = analyzer.analyze_commits(max_commits=1, skip_analyzed=True)
    
    print(f"📋 RESULTADOS:")
    print(f"  Processados: {stats['total_processed']}")
    print(f"  Sucessos: {stats['successful_analyses']}")
    print(f"  Falhas: {stats['failed_analyses']}")
    print(f"  Taxa de sucesso: {(stats['successful_analyses']/max(stats['total_processed'],1)*100):.1f}%")

def run_analysis(analyzer, args):
    """Executa análise com os parâmetros especificados."""
    print("🚀 INICIANDO ANÁLISE LLM")
    print("=" * 40)
    
    # Configurar parâmetros
    skip_analyzed = not args.include_analyzed
    
    if args.max_commits:
        print(f"📊 Analisando até {args.max_commits} commits")
    else:
        print("📊 Analisando TODOS os commits disponíveis")
    
    if args.purity_filter:
        print(f"🔍 Filtro Purity: {args.purity_filter}")
    
    if skip_analyzed:
        print("⏭️ Pulando commits já analisados")
    
    # Executar análise
    stats = analyzer.analyze_commits(
        max_commits=args.max_commits,
        skip_analyzed=skip_analyzed,
        purity_filter=args.purity_filter
    )
    
    # Imprimir resumo final
    print(f"\n🎯 ANÁLISE CONCLUÍDA!")
    success_rate = (stats['successful_analyses'] / max(stats['total_processed'], 1)) * 100
    print(f"Taxa de sucesso: {success_rate:.1f}%")

def interactive_mode():
    """Modo interativo para o usuário escolher opções."""
    analyzer = LLMPurityAnalyzer()
    
    while True:
        print("\n" + "="*60)
        print("🤖 LLM PURITY ANALYZER - MENU PRINCIPAL")
        print("="*60)
        print("1. 📊 Ver resumo das análises")
        print("2. 🧪 Testar com 1 commit")
        print("3. 🔢 Analisar N commits")
        print("4. 🌟 Analisar TODOS os commits")
        print("5. 🎯 Analisar apenas commits FALSE do Purity")
        print("6. ✅ Analisar apenas commits TRUE do Purity")
        print("7. ❓ Analisar apenas commits NONE do Purity")
        print("0. 🚪 Sair")
        
        try:
            choice = input("\n👉 Escolha uma opção (0-7): ").strip()
            
            if choice == "0":
                print("👋 Saindo...")
                break
            elif choice == "1":
                print_summary(analyzer)
            elif choice == "2":
                test_analyzer(analyzer)
            elif choice == "3":
                try:
                    n = int(input("Quantos commits analisar? "))
                    if n > 0:
                        analyzer.analyze_commits(max_commits=n)
                    else:
                        print("❌ Número deve ser positivo")
                except ValueError:
                    print("❌ Por favor, digite um número válido")
            elif choice == "4":
                confirm = input("⚠️ Isso pode demorar muito tempo. Confirma? (s/N): ").lower()
                if confirm == 's':
                    analyzer.analyze_commits()
                else:
                    print("❌ Operação cancelada")
            elif choice == "5":
                analyzer.analyze_commits(purity_filter="FALSE")
            elif choice == "6":
                analyzer.analyze_commits(purity_filter="TRUE")
            elif choice == "7":
                analyzer.analyze_commits(purity_filter="NONE")
            else:
                print("❌ Opção inválida")
                
        except KeyboardInterrupt:
            print("\n\n👋 Interrompido pelo usuário. Saindo...")
            break
        except Exception as e:
            print(f"❌ Erro: {str(e)}")

if __name__ == "__main__":
    import sys
    
    # Se não há argumentos da linha de comando, usar modo interativo
    if len(sys.argv) == 1:
        interactive_mode()
    else:
        main()
