#!/usr/bin/env python3
"""
Script para recuperar análises da LLM dos arquivos de backup
e atualizar o arquivo principal hashes_no_rpt_purity_with_analysis.csv

Este script:
1. Lê o arquivo principal atual
2. Examina todos os arquivos de backup
3. Extrai análises da LLM que estão presentes nos backups mas ausentes no arquivo principal
4. Atualiza o arquivo principal com as análises recuperadas
5. Gera relatório das recuperações feitas
"""

import pandas as pd
import glob
import os
from datetime import datetime
import shutil

def load_main_file(main_path):
    """Carrega o arquivo principal"""
    print(f"Carregando arquivo principal: {main_path}")
    df = pd.read_csv(main_path)
    print(f"Arquivo principal carregado com {len(df)} registros")
    
    # Contar análises LLM existentes
    llm_with_analysis = df[df['llm_analysis'].notna() & (df['llm_analysis'] != '')].shape[0]
    llm_without_analysis = df[df['llm_analysis'].isna() | (df['llm_analysis'] == '')].shape[0]
    
    print(f"Análises LLM existentes: {llm_with_analysis}")
    print(f"Análises LLM faltantes: {llm_without_analysis}")
    
    return df

def scan_backup_files(backup_pattern):
    """Escaneia todos os arquivos de backup"""
    backup_files = glob.glob(backup_pattern)
    backup_files.sort()  # Ordenar por nome (que inclui timestamp)
    
    print(f"Encontrados {len(backup_files)} arquivos de backup")
    return backup_files

def extract_llm_analyses_from_backup(backup_path):
    """Extrai análises LLM de um arquivo de backup"""
    try:
        df_backup = pd.read_csv(backup_path)
        
        # Filtrar apenas registros com análise LLM
        df_with_llm = df_backup[df_backup['llm_analysis'].notna() & (df_backup['llm_analysis'] != '')]
        
        return df_with_llm[['hash', 'llm_analysis']]
    
    except Exception as e:
        print(f"Erro ao processar backup {backup_path}: {e}")
        return pd.DataFrame(columns=['hash', 'llm_analysis'])

def recover_analyses(main_df, backup_files):
    """Recupera análises dos arquivos de backup"""
    print("\nIniciando recuperação de análises...")
    
    # Criar dicionário com as análises existentes no arquivo principal
    existing_analyses = {}
    for _, row in main_df.iterrows():
        if pd.notna(row['llm_analysis']) and row['llm_analysis'] != '':
            existing_analyses[row['hash']] = row['llm_analysis']
    
    print(f"Análises existentes no arquivo principal: {len(existing_analyses)}")
    
    # Dicionário para armazenar novas análises encontradas
    recovered_analyses = {}
    recovery_sources = {}  # Para rastrear de qual backup veio cada análise
    
    # Processar cada arquivo de backup
    for i, backup_path in enumerate(backup_files):
        print(f"Processando backup {i+1}/{len(backup_files)}: {os.path.basename(backup_path)}")
        
        backup_analyses = extract_llm_analyses_from_backup(backup_path)
        
        if len(backup_analyses) == 0:
            continue
            
        print(f"  Encontradas {len(backup_analyses)} análises neste backup")
        
        # Verificar quais análises são novas
        new_count = 0
        for _, row in backup_analyses.iterrows():
            hash_val = row['hash']
            llm_analysis = row['llm_analysis']
            
            # Se não existe no arquivo principal e não foi ainda recuperada
            if hash_val not in existing_analyses and hash_val not in recovered_analyses:
                # Verificar se o hash existe no arquivo principal (mas sem análise)
                if hash_val in main_df['hash'].values:
                    recovered_analyses[hash_val] = llm_analysis
                    recovery_sources[hash_val] = os.path.basename(backup_path)
                    new_count += 1
        
        if new_count > 0:
            print(f"  Recuperadas {new_count} novas análises deste backup")
    
    print(f"\nTotal de análises recuperadas: {len(recovered_analyses)}")
    return recovered_analyses, recovery_sources

def update_main_file(main_df, recovered_analyses, main_path):
    """Atualiza o arquivo principal com as análises recuperadas"""
    print(f"\nAtualizando arquivo principal...")
    
    # Fazer backup do arquivo atual
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_path = f"{main_path}.backup_before_recovery_{timestamp}"
    shutil.copy2(main_path, backup_path)
    print(f"Backup do arquivo atual salvo em: {backup_path}")
    
    # Atualizar DataFrame
    updated_count = 0
    for hash_val, llm_analysis in recovered_analyses.items():
        mask = main_df['hash'] == hash_val
        if mask.any():
            main_df.loc[mask, 'llm_analysis'] = llm_analysis
            updated_count += 1
    
    # Salvar arquivo atualizado
    main_df.to_csv(main_path, index=False)
    print(f"Arquivo principal atualizado com {updated_count} análises recuperadas")
    
    return updated_count

def generate_recovery_report(recovered_analyses, recovery_sources, output_dir):
    """Gera relatório da recuperação"""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    report_path = os.path.join(output_dir, f"recovery_report_{timestamp}.txt")
    
    with open(report_path, 'w') as f:
        f.write(f"Relatório de Recuperação de Análises LLM\n")
        f.write(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"="*50 + "\n\n")
        
        f.write(f"Total de análises recuperadas: {len(recovered_analyses)}\n\n")
        
        if len(recovered_analyses) > 0:
            f.write("Detalhes das análises recuperadas:\n")
            f.write("-" * 40 + "\n")
            
            for hash_val, llm_analysis in recovered_analyses.items():
                source = recovery_sources.get(hash_val, "Unknown")
                f.write(f"Hash: {hash_val}\n")
                f.write(f"Análise: {llm_analysis}\n")
                f.write(f"Fonte: {source}\n")
                f.write("-" * 40 + "\n")
    
    print(f"Relatório salvo em: {report_path}")
    return report_path

def main():
    """Função principal"""
    # Configurações
    base_dir = "/home/marinhofn/tcc/refan"
    main_file = os.path.join(base_dir, "csv", "hashes_no_rpt_purity_with_analysis.csv")
    backup_pattern = os.path.join(base_dir, "csv", "hashes_no_rpt_purity_with_analysis.csv.backup_*")
    output_dir = os.path.join(base_dir, "analises_completas")
    
    print("=== Script de Recuperação de Análises LLM ===")
    print(f"Diretório base: {base_dir}")
    print(f"Arquivo principal: {main_file}")
    print(f"Padrão de backup: {backup_pattern}")
    
    # Verificar se arquivos existem
    if not os.path.exists(main_file):
        print(f"ERRO: Arquivo principal não encontrado: {main_file}")
        return
    
    # Carregar arquivo principal
    main_df = load_main_file(main_file)
    
    # Escanear arquivos de backup
    backup_files = scan_backup_files(backup_pattern)
    
    if len(backup_files) == 0:
        print("ERRO: Nenhum arquivo de backup encontrado")
        return
    
    # Recuperar análises
    recovered_analyses, recovery_sources = recover_analyses(main_df, backup_files)
    
    if len(recovered_analyses) == 0:
        print("Nenhuma análise nova foi encontrada nos backups.")
        return
    
    # Atualizar arquivo principal
    updated_count = update_main_file(main_df, recovered_analyses, main_file)
    
    # Gerar relatório
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    report_path = generate_recovery_report(recovered_analyses, recovery_sources, output_dir)
    
    # Estatísticas finais
    print(f"\n=== RESUMO DA RECUPERAÇÃO ===")
    print(f"Análises recuperadas: {len(recovered_analyses)}")
    print(f"Arquivos de backup processados: {len(backup_files)}")
    print(f"Relatório salvo em: {report_path}")
    
    # Verificar estado final
    final_df = pd.read_csv(main_file)
    final_with_analysis = final_df[final_df['llm_analysis'].notna() & (final_df['llm_analysis'] != '')].shape[0]
    final_without_analysis = final_df[final_df['llm_analysis'].isna() | (final_df['llm_analysis'] == '')].shape[0]
    
    print(f"\nEstado final do arquivo:")
    print(f"Total de registros: {len(final_df)}")
    print(f"Com análise LLM: {final_with_analysis}")
    print(f"Sem análise LLM: {final_without_analysis}")

if __name__ == "__main__":
    main()
