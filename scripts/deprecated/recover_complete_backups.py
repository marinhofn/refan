#!/usr/bin/env python3
"""
Script especializado para recuperar análises LLM dos backups "complete"
Estes arquivos parecem ter análises mais completas
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
    complete_pattern = os.path.join(base_dir, "csv", "*backup_complete*")
    output_dir = os.path.join(base_dir, "analises_completas")
    
    print("=== Script de Recuperação de Análises LLM (Backups Complete) ===")
    
    # Encontrar arquivos de backup "complete"
    complete_files = glob.glob(complete_pattern)
    complete_files.sort()
    
    print(f"Encontrados {len(complete_files)} arquivos de backup 'complete':")
    for f in complete_files:
        print(f"  - {os.path.basename(f)}")
    
    if len(complete_files) == 0:
        print("Nenhum arquivo de backup 'complete' encontrado")
        return
    
    # Carregar arquivo principal
    print(f"\nCarregando arquivo principal...")
    main_df = pd.read_csv(main_file)
    print(f"Arquivo principal: {len(main_df)} registros")
    
    # Contar análises existentes
    existing_analyses = main_df[main_df['llm_analysis'].notna() & (main_df['llm_analysis'] != '')].shape[0]
    print(f"Análises LLM existentes no arquivo principal: {existing_analyses}")
    
    # Processar cada arquivo complete
    all_recovered = {}
    
    for complete_file in complete_files:
        print(f"\nProcessando: {os.path.basename(complete_file)}")
        
        try:
            df_complete = pd.read_csv(complete_file)
            print(f"  Registros no backup: {len(df_complete)}")
            
            # Filtrar apenas registros com análise LLM não vazia
            df_with_llm = df_complete[df_complete['llm_analysis'].notna() & (df_complete['llm_analysis'] != '')]
            print(f"  Registros com análise LLM: {len(df_with_llm)}")
            
            # Verificar quantas são novas
            new_count = 0
            for _, row in df_with_llm.iterrows():
                hash_val = row['hash']
                llm_analysis = row['llm_analysis']
                
                # Verificar se o hash existe no arquivo principal mas sem análise
                main_row = main_df[main_df['hash'] == hash_val]
                if not main_row.empty:
                    current_analysis = main_row.iloc[0]['llm_analysis']
                    if pd.isna(current_analysis) or current_analysis == '':
                        all_recovered[hash_val] = llm_analysis
                        new_count += 1
            
            print(f"  Novas análises recuperadas: {new_count}")
            
        except Exception as e:
            print(f"  ERRO ao processar {complete_file}: {e}")
    
    print(f"\n=== RESUMO ===")
    print(f"Total de análises únicas recuperadas: {len(all_recovered)}")
    
    if len(all_recovered) == 0:
        print("Nenhuma nova análise foi encontrada.")
        return
    
    # Fazer backup do arquivo atual
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_path = f"{main_file}.backup_before_complete_recovery_{timestamp}"
    shutil.copy2(main_file, backup_path)
    print(f"Backup criado: {backup_path}")
    
    # Atualizar arquivo principal
    updated_count = 0
    for hash_val, llm_analysis in all_recovered.items():
        mask = main_df['hash'] == hash_val
        if mask.any():
            main_df.loc[mask, 'llm_analysis'] = llm_analysis
            updated_count += 1
    
    # Salvar arquivo atualizado
    main_df.to_csv(main_file, index=False)
    print(f"Arquivo principal atualizado com {updated_count} análises")
    
    # Gerar relatório detalhado
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    report_path = os.path.join(output_dir, f"complete_recovery_report_{timestamp}.txt")
    with open(report_path, 'w') as f:
        f.write(f"Relatório de Recuperação de Análises LLM (Backups Complete)\n")
        f.write(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"="*60 + "\n\n")
        
        f.write(f"Arquivos processados:\n")
        for complete_file in complete_files:
            f.write(f"  - {os.path.basename(complete_file)}\n")
        
        f.write(f"\nTotal de análises recuperadas: {len(all_recovered)}\n\n")
        
        if len(all_recovered) > 0:
            f.write("Análises recuperadas:\n")
            f.write("-" * 50 + "\n")
            
            for hash_val, llm_analysis in all_recovered.items():
                f.write(f"Hash: {hash_val}\n")
                f.write(f"Análise: {llm_analysis}\n")
                f.write("-" * 50 + "\n")
    
    print(f"Relatório detalhado salvo em: {report_path}")
    
    # Verificar estado final
    final_df = pd.read_csv(main_file)
    final_with_analysis = final_df[final_df['llm_analysis'].notna() & (final_df['llm_analysis'] != '')].shape[0]
    final_without_analysis = final_df[final_df['llm_analysis'].isna() | (final_df['llm_analysis'] == '')].shape[0]
    
    print(f"\nEstado final do arquivo:")
    print(f"Total de registros: {len(final_df)}")
    print(f"Com análise LLM: {final_with_analysis}")
    print(f"Sem análise LLM: {final_without_analysis}")
    print(f"Percentual com análise: {(final_with_analysis/len(final_df))*100:.2f}%")

if __name__ == "__main__":
    main()
