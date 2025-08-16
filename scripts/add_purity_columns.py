#!/usr/bin/env python3
"""
Script para adicionar colunas de análise de pureza ao arquivo hashes_no_rpt_purity.csv
"""

import pandas as pd
import csv

def process_purity_data():
    print("Processando dados de pureza...")
    
    # Primeiro, vamos processar o arquivo purity de forma mais robusta
    purity_data = {}
    
    try:
        with open('csv/puritychecker_detailed_classification.csv', 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        print(f"Total de linhas no arquivo purity: {len(lines)}")
        
        # Processar linha por linha
        for i, line in enumerate(lines[1:], 1):  # Pular cabeçalho
            if i % 10000 == 0:
                print(f"Processando linha {i}...")
            
            # Dividir por ponto e vírgula
            parts = line.strip().split(';')
            
            if len(parts) >= 3:
                try:
                    commit_hash = parts[1]
                    purity_value = parts[2]
                    
                    if commit_hash and commit_hash != 'None':
                        if commit_hash not in purity_data:
                            purity_data[commit_hash] = []
                        
                        # Limpar o valor de pureza
                        if purity_value.lower() == 'true':
                            purity_data[commit_hash].append(True)
                        elif purity_value.lower() == 'false':
                            purity_data[commit_hash].append(False)
                        elif purity_value.lower() == 'none':
                            purity_data[commit_hash].append(None)
                
                except Exception as e:
                    if i < 10:  # Mostrar apenas os primeiros erros
                        print(f"Erro na linha {i}: {e} - Linha: {line[:100]}...")
    
    except Exception as e:
        print(f"Erro ao ler arquivo: {e}")
        return
    
    print(f"Hashes únicos encontrados no arquivo purity: {len(purity_data)}")
    
    # Determinar a classificação final para cada hash
    final_classifications = {}
    
    for commit_hash, values in purity_data.items():
        # Se houver pelo menos um FALSE, classificar como FALSE
        if False in values:
            final_classifications[commit_hash] = "FALSE"
        # Se houver apenas TRUEs, classificar como TRUE
        elif True in values and False not in values:
            final_classifications[commit_hash] = "TRUE"
        # Se houver apenas Nones, classificar como NONE
        elif all(v is None for v in values):
            final_classifications[commit_hash] = "NONE"
        # Caso misto True/None sem False
        elif True in values and None in values and False not in values:
            final_classifications[commit_hash] = "TRUE"
        else:
            final_classifications[commit_hash] = "UNKNOWN"
    
    print("Distribuição das classificações finais:")
    classification_counts = {}
    for classification in final_classifications.values():
        classification_counts[classification] = classification_counts.get(classification, 0) + 1
    
    for classification, count in classification_counts.items():
        print(f"  {classification}: {count}")
    
    # Agora processar o arquivo de hashes
    print("\nProcessando arquivo de hashes...")
    
    # Ler hashes
    hashes_df = pd.read_csv('csv/hashes_no_rpt_purity.csv')
    print(f"Hashes a processar: {len(hashes_df)}")
    
    # Adicionar colunas
    hashes_df['purity_analysis'] = ''
    hashes_df['llm_analysis'] = ''
    
    # Preencher coluna de pureza
    matches = 0
    for idx, row in hashes_df.iterrows():
        hash_value = row['hash']
        if hash_value in final_classifications:
            hashes_df.at[idx, 'purity_analysis'] = final_classifications[hash_value]
            matches += 1
        else:
            hashes_df.at[idx, 'purity_analysis'] = 'NOT_FOUND'
    
    print(f"Matches encontrados: {matches}/{len(hashes_df)}")
    
    # Salvar arquivo atualizado
    output_file = 'csv/hashes_no_rpt_purity_with_analysis.csv'
    hashes_df.to_csv(output_file, index=False)
    
    print(f"\nArquivo salvo como: {output_file}")
    
    # Mostrar estatísticas finais
    print("\nEstatísticas finais:")
    analysis_counts = hashes_df['purity_analysis'].value_counts()
    print(analysis_counts)
    
    # Mostrar alguns exemplos
    print("\nPrimeiros 10 registros:")
    print(hashes_df.head(10)[['hash', 'purity_analysis', 'llm_analysis']])
    
    return hashes_df

if __name__ == "__main__":
    result_df = process_purity_data()
