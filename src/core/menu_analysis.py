#!/usr/bin/env python3
"""
Menu interativo para análise LLM com diferentes opções
"""

import sys
import os
from pathlib import Path
from datetime import datetime

# Configurar paths para imports funcionarem tanto quando executado diretamente
# quanto através do sistema unificado
if __name__ == "__main__":
    # Se executado diretamente, adicionar o diretório raiz do projeto ao path
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))

from src.analyzers.llm_purity_analyzer import LLMPurityAnalyzer
from src.core.config import get_current_llm_model, list_available_ollama_models, set_llm_model, ensure_model_directories
from src.utils.colors import *

def show_menu():
    """Mostra menu de opções."""
    print(f"\n{header('📋 MENU DE ANÁLISE LLM')}  {dim('[Modelo atual: ' + get_current_llm_model() + ']')}")
    print("1. 🚀 Análise rápida (10 commits)")
    print("2. 📦 Análise de lote (50 commits)")  
    print("3. 🎯 Análise por filtro Purity")
    print("4. 📊 Estatísticas do arquivo")
    print("5. 🔄 Análise completa automática (do início)")
    print("6. 🎨 Abrir visualização")
    print("7. 🤖 Alterar modelo LLM ativo")
    print("8. 🧩 Analisar e gerar CSV por modelo (llm_analysis_csv)")
    print("9. ✨ Analisar hashes TRUE por modelo")
    print("0. ❌ Sair")

def run_complete_analysis_from_start():
    """Executa análise completa começando do primeiro commit."""
    
    print(header("🚀 ANÁLISE COMPLETA - DO INÍCIO"))
    print(header("=" * 50))
    
    # Criar pasta para análises completas
    complete_analysis_dir = "analises_completas"
    os.makedirs(complete_analysis_dir, exist_ok=True)
    
    # Timestamp para arquivo único
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_file = os.path.join(complete_analysis_dir, f"analise_completa_{timestamp}.csv")
    
    print(f"{info('📁 Pasta de saída:')} {complete_analysis_dir}")
    print(f"{info('📄 Arquivo de saída:')} {output_file}")
    
    # Criar analisador com configuração especial
    analyzer = LLMPurityAnalyzer()
    
    # Fazer backup do arquivo atual se existir
    original_file = analyzer.csv_file_path
    if os.path.exists(original_file):
        backup_file = f"{original_file}.backup_complete_{timestamp}"
        import shutil
        shutil.copy2(original_file, backup_file)
        print(f"{info('💾 Backup criado:')} {backup_file}")
    
    # Configurações da análise completa
    BATCH_SIZE = 25  # Lotes menores para análise completa
    total_batches = 0
    total_processed = 0
    total_successful = 0
    
    print(f"\n{warning('⚠️ IMPORTANTE:')}")
    print("   • Esta análise começará do PRIMEIRO commit")
    print("   • Todos os commits serão reprocessados")
    print("   • O arquivo original será salvo como backup")
    print("   • O resultado final será salvo em pasta separada")
    print(f"   • Tamanho do lote: {BATCH_SIZE} commits")
    
    confirm = input(f"\n{warning('Confirma iniciar análise completa? (s/N):')} ").strip().lower()
    if confirm != 's':
        print(info("❌ Análise cancelada"))
        return
    
    # Carregar dados originais para resetar
    try:
        df = analyzer._load_csv_data()
        if df is None:
            print(error("❌ Erro ao carregar dados"))
            return
            
        # Resetar coluna LLM para forçar reprocessamento
        df['llm_analysis'] = ''
        df.to_csv(original_file, index=False)
        
        print(f"{success('🔄 Arquivo resetado para análise completa')}")
        print(f"   Total de commits para analisar: {len(df):,}")
        
    except Exception as e:
        print(error(f"❌ Erro ao resetar arquivo: {e}"))
        return
    
    # Executar análise em lotes
    start_time = datetime.now()
    
    while True:
        print(f"\n{info(f'🔄 Executando lote {total_batches + 1}...')}")
        
        try:
            # Executar lote (skip_analyzed=False para processar tudo)
            stats = analyzer.analyze_commits(
                max_commits=BATCH_SIZE,
                skip_analyzed=False,  # FORÇAR REPROCESSAMENTO
                purity_filter=None
            )
            
            # Atualizar contadores
            batch_processed = stats['total_processed']
            batch_successful = stats['successful_analyses']
            
            total_batches += 1
            total_processed += batch_processed
            total_successful += batch_successful
            
            print(f"\n{success('📊 Estatísticas do Lote:')}")
            print(f"   Processados: {batch_processed}")
            print(f"   Sucessos: {batch_successful}")
            print(f"   Falhas: {batch_processed - batch_successful}")
            print(f"   Taxa: {(batch_successful/batch_processed*100) if batch_processed > 0 else 0:.1f}%")
            
            print(f"\n{info('📈 Totais Acumulados:')}")
            print(f"   Lotes executados: {total_batches}")
            print(f"   Total processado: {total_processed}")
            print(f"   Total sucessos: {total_successful}")
            print(f"   Taxa geral: {(total_successful/total_processed*100) if total_processed > 0 else 0:.1f}%")
            
            # Verificar se terminou
            if batch_processed == 0:
                break
                
            # Pausa entre lotes
            print(f"\n{dim('⏸️ Pausa de 5 segundos entre lotes...')}")
            import time
            time.sleep(5)
            
        except KeyboardInterrupt:
            print(f"\n{warning('⚠️ Análise interrompida pelo usuário')}")
            break
        except Exception as e:
            print(f"\n{error(f'❌ Erro no lote {total_batches + 1}: {e}')}")
            continue
    
    # Finalizar análise
    end_time = datetime.now()
    duration = end_time - start_time
    
    print(f"\n{header('🎉 ANÁLISE COMPLETA FINALIZADA!')}")
    print(f"   Duração total: {duration}")
    print(f"   Total processado: {total_processed:,} commits")
    print(f"   Sucessos: {total_successful:,}")
    print(f"   Falhas: {total_processed - total_successful:,}")
    print(f"   Taxa final: {(total_successful/total_processed*100) if total_processed > 0 else 0:.1f}%")
    
    # Copiar resultado final para pasta de análises completas
    try:
        import shutil
        shutil.copy2(original_file, output_file)
        print(f"\n{success('💾 Resultado salvo em:')} {output_file}")
        
        # Criar relatório da análise
        report_file = os.path.join(complete_analysis_dir, f"relatorio_completo_{timestamp}.txt")
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(f"RELATÓRIO DA ANÁLISE COMPLETA\n")
            f.write(f"=" * 50 + "\n\n")
            f.write(f"Data/Hora Início: {start_time}\n")
            f.write(f"Data/Hora Fim: {end_time}\n")
            f.write(f"Duração Total: {duration}\n\n")
            f.write(f"ESTATÍSTICAS FINAIS:\n")
            f.write(f"Total de lotes: {total_batches}\n")
            f.write(f"Total processado: {total_processed:,} commits\n")
            f.write(f"Total de sucessos: {total_successful:,}\n")
            f.write(f"Total de falhas: {total_processed - total_successful:,}\n")
            f.write(f"Taxa de sucesso: {(total_successful/total_processed*100) if total_processed > 0 else 0:.1f}%\n\n")
            f.write(f"ARQUIVOS GERADOS:\n")
            f.write(f"Resultado CSV: {output_file}\n")
            f.write(f"Backup original: {backup_file}\n")
            
        print(f"{success('📄 Relatório salvo em:')} {report_file}")
        
    except Exception as e:
        print(error(f"❌ Erro ao salvar resultado: {e}"))

def run_filtered_analysis(purity_filter, max_commits=100):
    """Executa análise filtrada."""
    analyzer = LLMPurityAnalyzer()
    
    print(success(f"\n🎯 Analisando commits com Purity={purity_filter}"))
    stats = analyzer.analyze_commits(
        max_commits=max_commits,
        skip_analyzed=True,
        purity_filter=purity_filter
    )
    
    return stats

def show_statistics():
    """Mostra estatísticas do arquivo atual."""
    analyzer = LLMPurityAnalyzer()
    
    try:
        df = analyzer._load_csv_data()
        if df is None:
            print(error("❌ Erro ao carregar dados"))
            return
        
        print(f"\n{header('📊 ESTATÍSTICAS DO ARQUIVO')}")
        print(f"Total de commits: {len(df):,}")
        
        # Estatísticas por Purity
        purity_counts = df['purity_analysis'].value_counts()
        print(f"\n{info('📈 Por classificação Purity:')}")
        for purity, count in purity_counts.items():
            print(f"   {purity}: {count:,} ({count/len(df)*100:.1f}%)")
        
        # Estatísticas por LLM
        llm_counts = df['llm_analysis'].value_counts()
        analyzed_count = len(df) - (df['llm_analysis'].isna().sum() + (df['llm_analysis'] == '').sum())
        
        print(f"\n{info('🤖 Por classificação LLM:')}")
        print(f"   Analisados: {analyzed_count:,} ({analyzed_count/len(df)*100:.1f}%)")
        print(f"   Restantes: {len(df) - analyzed_count:,} ({(len(df) - analyzed_count)/len(df)*100:.1f}%)")
        
        if analyzed_count > 0:
            for llm, count in llm_counts.items():
                if pd.notna(llm) and llm != '':
                    print(f"   {llm}: {count:,}")
        
    except Exception as e:
        print(error(f"❌ Erro: {e}"))

def main():
    """Função principal."""
    
    print(header("🔍 SISTEMA DE ANÁLISE LLM"))
    print(header("=" * 40))
    
    while True:
        show_menu()
        choice = input(f"\n{info('Escolha (0-9):')} ").strip()
        
        if choice == "0":
            print(info("👋 Saindo..."))
            break
            
        elif choice == "1":
            print(success("\n🚀 Análise rápida (10 commits)"))
            analyzer = LLMPurityAnalyzer()
            analyzer.analyze_commits(max_commits=10, skip_analyzed=True)
            
        elif choice == "2":
            print(success("\n📦 Análise de lote (50 commits)"))
            analyzer = LLMPurityAnalyzer()
            analyzer.analyze_commits(max_commits=50, skip_analyzed=True)
            
        elif choice == "3":
            print(f"\n{info('🎯 Filtros disponíveis:')}")
            print("   TRUE  - Commits Purity PURE")
            print("   FALSE - Commits Purity FLOSS") 
            print("   NONE  - Commits sem classificação Purity")
            
            purity_filter = input(f"{info('Filtro (TRUE/FALSE/NONE):')} ").strip().upper()
            
            if purity_filter in ['TRUE', 'FALSE', 'NONE']:
                max_commits = input(f"{info('Quantos commits (padrão 100):')} ").strip()
                max_commits = int(max_commits) if max_commits else 100
                run_filtered_analysis(purity_filter, max_commits)
            else:
                print(error("❌ Filtro inválido"))
                
        elif choice == "4":
            show_statistics()
            
        elif choice == "5":
            confirm = input(f"{warning('⚠️ Análise completa pode levar MUITAS horas. Continuar? (s/N):')} ").strip().lower()
            if confirm == 's':
                run_complete_analysis_from_start()
            
        elif choice == "6":
            print(info("🎨 Abrindo sistema de visualização..."))
            import subprocess
            script_path = Path(__file__).parent.parent.parent / "scripts" / "demos" / "demo_llm_visualization.py"
            subprocess.run([sys.executable, str(script_path)])
        
        elif choice == "7":
            print(info("🔄 Alterar modelo LLM"))
            models = list_available_ollama_models()
            if not models:
                print(error("Nenhum modelo disponível encontrado."))
                continue
            print(info("Modelos detectados:"))
            for idx, m in enumerate(models, 1):
                mark = ' (atual)' if m == get_current_llm_model() else ''
                print(f"  {cyan(str(idx)+'.')} {m}{mark}")
            sel = input(cyan("Escolha o número do modelo (Enter para cancelar): ")).strip()
            if not sel:
                continue
            try:
                idx = int(sel) - 1
                if idx < 0 or idx >= len(models):
                    print(warning("Índice inválido."))
                    continue
                new_model = models[idx]
                set_llm_model(new_model)
                ensure_model_directories()
                print(success(f"Modelo ativo agora: {new_model}"))
            except ValueError:
                print(warning("Entrada inválida."))
            
        elif choice == "8":
            # Opção: executar análise e salvar em CSV específico do modelo
            print(info("🔎 Análise por modelo e geração de CSV separado"))
            models = list_available_ollama_models()
            if not models:
                print(error("Nenhum modelo disponível."))
                continue
            for idx, m in enumerate(models, 1):
                print(f"  {cyan(str(idx)+'.')} {m}")
            sel = input(cyan("Escolha o número do modelo para gerar CSV (Enter para cancelar): ")).strip()
            if not sel:
                continue
            try:
                idx = int(sel) - 1
                if idx < 0 or idx >= len(models):
                    print(warning("Índice inválido."))
                    continue
                chosen_model = models[idx]
                # Preparar CSV de saída no diretório csv/llm_analysis_csv
                from src.core.config import get_model_paths
                safe_name = chosen_model.replace(':', '_')
                out_dir = Path("csv") / "llm_analysis_csv"
                out_dir.mkdir(parents=True, exist_ok=True)
                master_csv = Path("csv") / "floss_hashes_no_rpt_purity_with_analysis.csv"
                target_csv = out_dir / f"{safe_name}_floss_hashes_no_rpt_purity_with_analysis.csv"
                # Se não existir, copiar do master
                if not target_csv.exists():
                    if master_csv.exists():
                        import shutil
                        shutil.copy2(master_csv, target_csv)
                        print(success(f"CSV criado para {chosen_model}: {target_csv}"))
                    else:
                        print(error(f"Arquivo master {master_csv} não encontrado."))
                        continue

                # Instanciar analisador apontando para o CSV do modelo
                from src.analyzers.llm_purity_analyzer import LLMPurityAnalyzer
                analyzer = LLMPurityAnalyzer(model=chosen_model, csv_file_path=str(target_csv))
                n = input(info('Quantos commits analisar (Enter = 100): ')).strip()
                n = int(n) if n else 100
                stats = analyzer.analyze_commits(max_commits=n, skip_analyzed=True)
                print(success(f"Análise concluída para modelo {chosen_model}. Estatísticas: {stats}"))
            except ValueError:
                print(warning("Entrada inválida."))
        
        elif choice == "9":
            # Opção: analisar hashes TRUE e salvar em CSV específico do modelo
            print(info("✨ Análise de hashes TRUE por modelo"))
            models = list_available_ollama_models()
            if not models:
                print(error("Nenhum modelo disponível."))
                continue
            for idx, m in enumerate(models, 1):
                print(f"  {cyan(str(idx)+'.')} {m}")
            sel = input(cyan("Escolha o número do modelo para analisar hashes TRUE (Enter para cancelar): ")).strip()
            if not sel:
                continue
            try:
                idx = int(sel) - 1
                if idx < 0 or idx >= len(models):
                    print(warning("Índice inválido."))
                    continue
                chosen_model = models[idx]
                
                # Preparar CSV de saída no diretório csv/llm_analysis_csv
                safe_name = chosen_model.replace(':', '_')
                out_dir = Path("csv") / "llm_analysis_csv"
                out_dir.mkdir(parents=True, exist_ok=True)
                
                # Usar arquivo TRUE como base
                master_csv = Path("csv") / "true_purity_hashes_with_analysis.csv"
                target_csv = out_dir / f"{safe_name}_true_purity_hashes_with_analysis.csv"
                
                # Se não existir, copiar do master
                if not target_csv.exists():
                    if master_csv.exists():
                        import shutil
                        shutil.copy2(master_csv, target_csv)
                        print(success(f"CSV criado para {chosen_model}: {target_csv}"))
                    else:
                        print(error(f"Arquivo master {master_csv} não encontrado."))
                        continue
                else:
                    print(info(f"Usando CSV existente: {target_csv}"))

                # Instanciar analisador apontando para o CSV do modelo
                from src.analyzers.llm_purity_analyzer import LLMPurityAnalyzer
                analyzer = LLMPurityAnalyzer(model=chosen_model, csv_file_path=str(target_csv))
                
                # Pergunta quantos commits analisar
                n = input(info('Quantos commits analisar (Enter = 100): ')).strip()
                n = int(n) if n else 100
                
                print(success(f"Iniciando análise de {n} hashes TRUE com modelo {chosen_model}..."))
                stats = analyzer.analyze_commits(max_commits=n, skip_analyzed=True)
                
                print(f"\n{success('📊 Análise concluída!')}")
                print(f"   Modelo usado: {chosen_model}")
                print(f"   Arquivo: {target_csv}")
                print(f"   Estatísticas: {stats}")
                
            except ValueError:
                print(warning("Entrada inválida."))
        else:
            print(error("❌ Opção inválida"))

if __name__ == "__main__":
    import pandas as pd
    main()
