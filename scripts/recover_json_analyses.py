#!/usr/bin/env python3
"""
Script para recuperar análises LLM dos arquivos JSON
e atualizar o arquivo principal hashes_no_rpt_purity_with_analysis.csv
"""

import pandas as pd
import json
import glob
import os
from datetime import datetime
import shutil

def load_json_analyses(json_file):
    """Carrega análises de um arquivo JSON"""
    try:
        with open(json_file, 'r') as f:
            data = json.load(f)
        
        analyses = {}
        if 'analyses' in data:
            for analysis in data['analyses']:
                hash_val = analysis.get('hash')
                llm_classification = analysis.get('llm_classification')
                
                if hash_val and llm_classification:
                    analyses[hash_val] = llm_classification
        
        return analyses
    
    except Exception as e:
        print(f"Erro ao processar {json_file}: {e}")
        return {}

def main():
    """Função principal"""
    # Configurações
    base_dir = "/home/marinhofn/tcc/refan"
    main_file = os.path.join(base_dir, "csv", "hashes_no_rpt_purity_with_analysis.csv")
    json_patterns = [
        os.path.join(base_dir, "analises", "*.json"),
        os.path.join(base_dir, "output", "models", "mistral", "analises", "*.json")
    ]
    output_dir = os.path.join(base_dir, "analises_completas")
    
    print("=== Script de Recuperação de Análises LLM (Arquivos JSON) ===")
    
    # Encontrar todos os arquivos JSON
    all_json_files = []
    for pattern in json_patterns:
        files = glob.glob(pattern)
        all_json_files.extend(files)
    
    all_json_files = list(set(all_json_files))  # Remover duplicatas
    all_json_files.sort()
    
    print(f"Encontrados {len(all_json_files)} arquivos JSON:")
    for f in all_json_files[:10]:  # Mostrar apenas os primeiros 10
        print(f"  - {os.path.basename(f)}")
    if len(all_json_files) > 10:
        print(f"  ... e mais {len(all_json_files) - 10} arquivos")
    
    if len(all_json_files) == 0:
        print("Nenhum arquivo JSON encontrado")
        return
    
    # Carregar arquivo principal
    print(f"\\nCarregando arquivo principal...")
    main_df = pd.read_csv(main_file)
    print(f"Arquivo principal: {len(main_df)} registros")
    
    # Contar análises existentes
    existing_analyses = main_df[main_df['llm_analysis'].notna() & (main_df['llm_analysis'] != '')].shape[0]
    print(f"Análises LLM existentes no arquivo principal: {existing_analyses}")
    
    # Coletar todas as análises dos JSONs
    print(f"\\nProcessando arquivos JSON...")
    all_json_analyses = {}
    sources = {}  # Para rastrear de qual arquivo veio cada análise
    
    for json_file in all_json_files:
        print(f"Processando: {os.path.basename(json_file)}")
        
        analyses = load_json_analyses(json_file)
        print(f"  Encontradas {len(analyses)} análises")
        
        # Adicionar análises que ainda não foram coletadas
        new_from_this_file = 0
        for hash_val, llm_classification in analyses.items():
            if hash_val not in all_json_analyses:
                all_json_analyses[hash_val] = llm_classification
                sources[hash_val] = os.path.basename(json_file)
                new_from_this_file += 1
        
        print(f"  Novas análises únicas: {new_from_this_file}")
    
    print(f"\\nTotal de análises únicas coletadas dos JSONs: {len(all_json_analyses)}")
    
    # Verificar quantas são realmente novas para o arquivo principal
    new_for_main = {}
    for hash_val, llm_classification in all_json_analyses.items():
        # Verificar se o hash existe no arquivo principal
        main_row = main_df[main_df['hash'] == hash_val]
        if not main_row.empty:
            current_analysis = main_row.iloc[0]['llm_analysis']
            if pd.isna(current_analysis) or current_analysis == '':
                new_for_main[hash_val] = llm_classification
    
    print(f"Análises novas para o arquivo principal: {len(new_for_main)}")
    
    if len(new_for_main) == 0:
        print("Nenhuma nova análise foi encontrada para o arquivo principal.")
        return
    
    # Fazer backup do arquivo atual
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_path = f"{main_file}.backup_before_json_recovery_{timestamp}"
    shutil.copy2(main_file, backup_path)
    print(f"\\nBackup criado: {backup_path}")
    
    # Atualizar arquivo principal
    updated_count = 0
    for hash_val, llm_classification in new_for_main.items():
        mask = main_df['hash'] == hash_val
        if mask.any():
            main_df.loc[mask, 'llm_analysis'] = llm_classification
            updated_count += 1
    
    # Salvar arquivo atualizado
    main_df.to_csv(main_file, index=False)
    print(f"Arquivo principal atualizado com {updated_count} análises")
    
    # Gerar relatório detalhado
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    report_path = os.path.join(output_dir, f"json_recovery_report_{timestamp}.txt")
    with open(report_path, 'w') as f:
        f.write(f"Relatório de Recuperação de Análises LLM (Arquivos JSON)\\n")
        f.write(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\\n")
        f.write(f"="*60 + "\\n\\n")
        
        f.write(f"Arquivos JSON processados: {len(all_json_files)}\\n")
        f.write(f"Total de análises coletadas: {len(all_json_analyses)}\\n")
        f.write(f"Análises novas para o arquivo principal: {len(new_for_main)}\\n\\n")
        
        if len(new_for_main) > 0:
            f.write("Análises recuperadas:\\n")
            f.write("-" * 60 + "\\n")
            
            for hash_val, llm_classification in new_for_main.items():
                source = sources.get(hash_val, "Unknown")
                f.write(f"Hash: {hash_val}\\n")
                f.write(f"Análise: {llm_classification}\\n")
                f.write(f"Fonte: {source}\\n")
                f.write("-" * 60 + "\\n")
    
    print(f"Relatório detalhado salvo em: {report_path}")
    
    # Verificar estado final
    final_df = pd.read_csv(main_file)
    final_with_analysis = final_df[final_df['llm_analysis'].notna() & (final_df['llm_analysis'] != '')].shape[0]
    final_without_analysis = final_df[final_df['llm_analysis'].isna() | (final_df['llm_analysis'] == '')].shape[0]
    
    print(f"\\nEstado final do arquivo:")
    print(f"Total de registros: {len(final_df)}")
    print(f"Com análise LLM: {final_with_analysis}")
    print(f"Sem análise LLM: {final_without_analysis}")
    print(f"Percentual com análise: {(final_with_analysis/len(final_df))*100:.2f}%")
    
    # Estatísticas das análises por tipo
    if final_with_analysis > 0:
        analysis_counts = final_df[final_df['llm_analysis'].notna() & (final_df['llm_analysis'] != '')]['llm_analysis'].value_counts()
        print(f"\\nDistribuição das análises LLM:")
        for analysis_type, count in analysis_counts.items():
            print(f"  {analysis_type}: {count}")

if __name__ == "__main__":
    main()
