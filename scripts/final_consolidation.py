#!/usr/bin/env python3
"""
Script final para recuperar análises da pasta analises_completas
e consolidar todas as análises disponíveis
"""

import pandas as pd
import glob
import os
from datetime import datetime
import shutil

def main():
    """Função principal"""
    # Configurações
    base_dir = "/home/marinhofn/tcc/refan"
    main_file = os.path.join(base_dir, "csv", "hashes_no_rpt_purity_with_analysis.csv")
    complete_analysis_file = os.path.join(base_dir, "analises_completas", "analise_completa_2025-08-15_07-30-41.csv")
    output_dir = os.path.join(base_dir, "analises_completas")
    
    print("=== Script Final de Consolidação de Análises LLM ===")
    
    # Verificar se o arquivo de análise completa existe
    if not os.path.exists(complete_analysis_file):
        print(f"ERRO: Arquivo de análise completa não encontrado: {complete_analysis_file}")
        return
    
    # Carregar arquivo principal
    print(f"Carregando arquivo principal...")
    main_df = pd.read_csv(main_file)
    print(f"Arquivo principal: {len(main_df)} registros")
    
    # Contar análises existentes
    existing_analyses = main_df[main_df['llm_analysis'].notna() & (main_df['llm_analysis'] != '')].shape[0]
    print(f"Análises LLM existentes no arquivo principal: {existing_analyses}")
    
    # Carregar arquivo de análise completa
    print(f"\\nCarregando arquivo de análise completa...")
    complete_df = pd.read_csv(complete_analysis_file)
    print(f"Arquivo de análise completa: {len(complete_df)} registros")
    
    # Contar análises no arquivo completo
    complete_analyses = complete_df[complete_df['llm_analysis'].notna() & (complete_df['llm_analysis'] != '')].shape[0]
    print(f"Análises LLM no arquivo completo: {complete_analyses}")
    
    # Comparar e identificar diferenças
    print(f"\\nComparando arquivos...")
    
    # Criar dicionário das análises do arquivo completo
    complete_analysis_dict = {}
    for _, row in complete_df.iterrows():
        if pd.notna(row['llm_analysis']) and row['llm_analysis'] != '':
            complete_analysis_dict[row['hash']] = row['llm_analysis']
    
    # Verificar quais análises são novas para o arquivo principal
    new_analyses = {}
    updated_analyses = {}
    
    for hash_val, llm_analysis in complete_analysis_dict.items():
        # Verificar se o hash existe no arquivo principal
        main_row = main_df[main_df['hash'] == hash_val]
        if not main_row.empty:
            current_analysis = main_row.iloc[0]['llm_analysis']
            if pd.isna(current_analysis) or current_analysis == '':
                new_analyses[hash_val] = llm_analysis
            elif current_analysis != llm_analysis:
                updated_analyses[hash_val] = {
                    'old': current_analysis,
                    'new': llm_analysis
                }
    
    print(f"Análises novas encontradas: {len(new_analyses)}")
    print(f"Análises diferentes encontradas: {len(updated_analyses)}")
    
    if len(new_analyses) == 0 and len(updated_analyses) == 0:
        print("Nenhuma diferença encontrada. O arquivo principal já está atualizado.")
        return
    
    # Fazer backup do arquivo atual
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_path = f"{main_file}.backup_before_final_consolidation_{timestamp}"
    shutil.copy2(main_file, backup_path)
    print(f"\\nBackup criado: {backup_path}")
    
    # Aplicar atualizações
    total_updates = 0
    
    # Aplicar novas análises
    for hash_val, llm_analysis in new_analyses.items():
        mask = main_df['hash'] == hash_val
        if mask.any():
            main_df.loc[mask, 'llm_analysis'] = llm_analysis
            total_updates += 1
    
    # Aplicar análises atualizadas (se houver)
    for hash_val, analyses in updated_analyses.items():
        mask = main_df['hash'] == hash_val
        if mask.any():
            main_df.loc[mask, 'llm_analysis'] = analyses['new']
            total_updates += 1
    
    # Salvar arquivo atualizado
    main_df.to_csv(main_file, index=False)
    print(f"Arquivo principal atualizado com {total_updates} mudanças")
    
    # Gerar relatório final
    report_path = os.path.join(output_dir, f"final_consolidation_report_{timestamp}.txt")
    with open(report_path, 'w') as f:
        f.write(f"Relatório de Consolidação Final de Análises LLM\\n")
        f.write(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\\n")
        f.write(f"="*60 + "\\n\\n")
        
        f.write(f"Arquivo principal: {main_file}\\n")
        f.write(f"Arquivo de referência: {complete_analysis_file}\\n\\n")
        
        f.write(f"Novas análises aplicadas: {len(new_analyses)}\\n")
        f.write(f"Análises atualizadas: {len(updated_analyses)}\\n")
        f.write(f"Total de mudanças: {total_updates}\\n\\n")
        
        if len(new_analyses) > 0:
            f.write("NOVAS ANÁLISES:\\n")
            f.write("-" * 50 + "\\n")
            for hash_val, llm_analysis in new_analyses.items():
                f.write(f"Hash: {hash_val}\\n")
                f.write(f"Análise: {llm_analysis}\\n")
                f.write("-" * 50 + "\\n")
        
        if len(updated_analyses) > 0:
            f.write("\\nANÁLISES ATUALIZADAS:\\n")
            f.write("-" * 50 + "\\n")
            for hash_val, analyses in updated_analyses.items():
                f.write(f"Hash: {hash_val}\\n")
                f.write(f"Análise anterior: {analyses['old']}\\n")
                f.write(f"Nova análise: {analyses['new']}\\n")
                f.write("-" * 50 + "\\n")
    
    print(f"Relatório salvo em: {report_path}")
    
    # Verificar estado final
    final_df = pd.read_csv(main_file)
    final_with_analysis = final_df[final_df['llm_analysis'].notna() & (final_df['llm_analysis'] != '')].shape[0]
    final_without_analysis = final_df[final_df['llm_analysis'].isna() | (final_df['llm_analysis'] == '')].shape[0]
    
    print(f"\\n=== ESTADO FINAL ===")
    print(f"Total de registros: {len(final_df)}")
    print(f"Com análise LLM: {final_with_analysis}")
    print(f"Sem análise LLM: {final_without_analysis}")
    print(f"Percentual com análise: {(final_with_analysis/len(final_df))*100:.2f}%")
    
    # Distribuição das análises por tipo
    if final_with_analysis > 0:
        analysis_counts = final_df[final_df['llm_analysis'].notna() & (final_df['llm_analysis'] != '')]['llm_analysis'].value_counts()
        print(f"\\nDistribuição das análises LLM:")
        for analysis_type, count in analysis_counts.items():
            print(f"  {analysis_type}: {count}")
            
    print(f"\\n=== RESUMO DA RECUPERAÇÃO ===")
    print(f"A análise de 24+ horas parece ter resultado em apenas {final_with_analysis} análises completas.")
    print(f"Infelizmente, a maioria das análises não foi salva nos arquivos de backup.")
    print(f"O sistema provavelmente teve problemas durante a execução que impediram")
    print(f"o salvamento das análises da LLM no arquivo principal.")

if __name__ == "__main__":
    main()
